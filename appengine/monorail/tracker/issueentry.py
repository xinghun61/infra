# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlet that implements the entry of new issues."""

import difflib
import logging
import string
import time

from businesslogic import work_env
from features import hotlist_helpers
from features import notify
from framework import actionlimit
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import permissions
from framework import servlet
from framework import template_helpers
from framework import urls
from third_party import ezt
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers
from tracker import tracker_views


PLACEHOLDER_SUMMARY = 'Enter one-line summary'


class IssueEntry(servlet.Servlet):
  """IssueEntry shows a page with a simple form to enter a new issue."""

  _PAGE_TEMPLATE = 'tracker/issue-entry-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ISSUES
  _CAPTCHA_ACTION_TYPES = [actionlimit.ISSUE_COMMENT]

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(IssueEntry, self).AssertBasePermission(mr)
    if not self.CheckPerm(mr, permissions.CREATE_ISSUE):
      raise permissions.PermissionException(
          'User is not allowed to enter an issue')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    with mr.profiler.Phase('getting config'):
      config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    # In addition to checking perms, we adjust some default field values for
    # project members.
    is_member = framework_bizobj.UserIsInProject(
        mr.project, mr.auth.effective_ids)
    page_perms = self.MakePagePerms(
        mr, None,
        permissions.CREATE_ISSUE,
        permissions.SET_STAR,
        permissions.EDIT_ISSUE,
        permissions.EDIT_ISSUE_SUMMARY,
        permissions.EDIT_ISSUE_STATUS,
        permissions.EDIT_ISSUE_OWNER,
        permissions.EDIT_ISSUE_CC)

    wkp = _SelectTemplate(mr.template_name, config, is_member)

    if wkp.summary:
      initial_summary = wkp.summary
      initial_summary_must_be_edited = wkp.summary_must_be_edited
    else:
      initial_summary = PLACEHOLDER_SUMMARY
      initial_summary_must_be_edited = True

    if wkp.status:
      initial_status = wkp.status
    elif is_member:
      initial_status = 'Accepted'
    else:
      initial_status = 'New'  # not offering meta, only used in hidden field.

    component_paths = []
    for component_id in wkp.component_ids:
      component_paths.append(
          tracker_bizobj.FindComponentDefByID(component_id, config).path)
    initial_components = ', '.join(component_paths)

    if wkp.owner_id:
      initial_owner = framework_views.MakeUserView(
          mr.cnxn, self.services.user, wkp.owner_id)
    elif wkp.owner_defaults_to_member and page_perms.EditIssue:
      initial_owner = mr.auth.user_view
    else:
      initial_owner = None

    if initial_owner:
      initial_owner_name = initial_owner.email
      owner_avail_state = initial_owner.avail_state
      owner_avail_message_short = initial_owner.avail_message_short
    else:
      initial_owner_name = ''
      owner_avail_state = None
      owner_avail_message_short = None

    # Check whether to allow attachments from the entry page
    allow_attachments = tracker_helpers.IsUnderSoftAttachmentQuota(mr.project)

    config_view = tracker_views.ConfigView(mr, self.services, config)
    # If the user followed a link that specified the template name, make sure
    # that it is also in the menu as the current choice.
    for template_view in config_view.templates:
      if template_view.name == mr.template_name:
        template_view.can_view = ezt.boolean(True)

    offer_templates = len(list(
        tmpl for tmpl in config_view.templates if tmpl.can_view)) > 1
    restrict_to_known = config.restrict_to_known
    field_name_set = {fd.field_name.lower() for fd in config.field_defs
                      if not fd.is_deleted}  # TODO(jrobbins): restrictions
    link_or_template_labels = mr.GetListParam('labels', wkp.labels)
    labels = [lab for lab in link_or_template_labels
              if not tracker_bizobj.LabelIsMaskedByField(lab, field_name_set)]

    field_user_views = tracker_views.MakeFieldUserViews(
        mr.cnxn, wkp, self.services.user)
    field_views = [
        tracker_views.MakeFieldValueView(
            fd, config, link_or_template_labels, [], wkp.field_values,
            field_user_views)
        # TODO(jrobbins): field-level view restrictions, display options
        for fd in config.field_defs
        if not fd.is_deleted]

    page_data = {
        'issue_tab_mode': 'issueEntry',
        'initial_summary': initial_summary,
        'template_summary': initial_summary,
        'clear_summary_on_click': ezt.boolean(
            initial_summary_must_be_edited and
            'initial_summary' not in mr.form_overrides),
        'must_edit_summary': ezt.boolean(initial_summary_must_be_edited),

        'initial_description': wkp.content,
        'template_name': wkp.name,
        'component_required': ezt.boolean(wkp.component_required),
        'initial_status': initial_status,
        'initial_owner': initial_owner_name,
        'owner_avail_state': owner_avail_state,
        'owner_avail_message_short': owner_avail_message_short,
        'initial_components': initial_components,
        'initial_cc': '',
        'initial_blocked_on': '',
        'initial_blocking': '',
        'initial_hotlists': '',
        'labels': labels,
        'fields': field_views,

        'any_errors': ezt.boolean(mr.errors.AnyErrors()),
        'page_perms': page_perms,
        'allow_attachments': ezt.boolean(allow_attachments),
        'max_attach_size': template_helpers.BytesKbOrMb(
            framework_constants.MAX_POST_BODY_SIZE),

        'offer_templates': ezt.boolean(offer_templates),
        'config': config_view,

        'restrict_to_known': ezt.boolean(restrict_to_known),
        'is_member': ezt.boolean(is_member),
        }

    return page_data

  def GatherHelpData(self, mr, page_data):
    """Return a dict of values to drive on-page user help.

    Args:
      mr: commonly used info parsed from the request.
      page_data: Dictionary of base and page template data.

    Returns:
      A dict of values to drive on-page user help, to be added to page_data.
    """
    help_data = super(IssueEntry, self).GatherHelpData(mr, page_data)
    dismissed = []
    if mr.auth.user_pb:
      dismissed = mr.auth.user_pb.dismissed_cues
    is_privileged_domain_user = framework_bizobj.IsPriviledgedDomainUser(
        mr.auth.user_pb.email)
    if (mr.auth.user_id and
        'privacy_click_through' not in dismissed):
      help_data['cue'] = 'privacy_click_through'
    elif (mr.auth.user_id and
        'code_of_conduct' not in dismissed):
      help_data['cue'] = 'code_of_conduct'

    help_data.update({
        'is_privileged_domain_user': ezt.boolean(is_privileged_domain_user),
        })
    return help_data

  def ProcessFormData(self, mr, post_data):
    """Process the issue entry form.

    Args:
      mr: commonly used info parsed from the request.
      post_data: The post_data dict for the current request.

    Returns:
      String URL to redirect the user to after processing.
    """
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    parsed = tracker_helpers.ParseIssueRequest(
        mr.cnxn, post_data, self.services, mr.errors, mr.project_name)
    bounce_labels = parsed.labels[:]
    bounce_fields = tracker_views.MakeBounceFieldValueViews(
        parsed.fields.vals, config)
    field_helpers.ShiftEnumFieldsIntoLabels(
        parsed.labels, parsed.labels_remove, parsed.fields.vals,
        parsed.fields.vals_remove, config)
    field_values = field_helpers.ParseFieldValues(
        mr.cnxn, self.services.user, parsed.fields.vals, config)

    labels = _DiscardUnusedTemplateLabelPrefixes(parsed.labels)
    component_ids = tracker_helpers.LookupComponentIDs(
        parsed.components.paths, config, mr.errors)

    reporter_id = mr.auth.user_id
    self.CheckCaptcha(mr, post_data)

    if not parsed.summary.strip() or parsed.summary == PLACEHOLDER_SUMMARY:
      mr.errors.summary = 'Summary is required'

    if not parsed.comment.strip():
      mr.errors.comment = 'A description is required'

    if len(parsed.comment) > tracker_constants.MAX_COMMENT_CHARS:
      mr.errors.comment = 'Comment is too long'
    if len(parsed.summary) > tracker_constants.MAX_SUMMARY_CHARS:
      mr.errors.summary = 'Summary is too long'

    if _MatchesTemplate(parsed.comment, config):
      mr.errors.comment = 'Template must be filled out.'

    if parsed.users.owner_id is None:
      mr.errors.owner = 'Invalid owner username'
    else:
      valid, msg = tracker_helpers.IsValidIssueOwner(
          mr.cnxn, mr.project, parsed.users.owner_id, self.services)
      if not valid:
        mr.errors.owner = msg

    if None in parsed.users.cc_ids:
      mr.errors.cc = 'Invalid Cc username'

    field_helpers.ValidateCustomFields(
        mr, self.services, field_values, config, mr.errors)

    hotlist_pbs = ProcessParsedHotlistRefs(
        mr, self.services, parsed.hotlists.hotlist_refs)

    if not mr.errors.AnyErrors():
      with work_env.WorkEnv(mr, self.services) as we:
        try:
          if parsed.attachments:
            new_bytes_used = tracker_helpers.ComputeNewQuotaBytesUsed(
                mr.project, parsed.attachments)
            we.UpdateProject(
              mr.project.project_id, attachment_bytes_used=new_bytes_used)

          template_content = ''
          for wkp in config.templates:
            if wkp.name == parsed.template_name:
              template_content = wkp.content
          marked_comment = _MarkupDescriptionOnInput(
              parsed.comment, template_content)
          has_star = 'star' in post_data and post_data['star'] == '1'

          issue = we.CreateIssue(
              mr.project_id, parsed.summary, parsed.status,
              parsed.users.owner_id, parsed.users.cc_ids, labels, field_values,
              component_ids, marked_comment, blocked_on=parsed.blocked_on.iids,
              blocking=parsed.blocking.iids, attachments=parsed.attachments)

          if has_star:
            we.StarIssue(issue, True)

          if hotlist_pbs:
            hotlist_ids = {hotlist.hotlist_id for hotlist in hotlist_pbs}
            issue_tuple = (issue.issue_id, mr.auth.user_id, int(time.time()),
                           '')
            self.services.features.AddIssueToHotlists(
                mr.cnxn, hotlist_ids, issue_tuple)

        except tracker_helpers.OverAttachmentQuota:
          mr.errors.attachments = 'Project attachment quota exceeded.'

      counts = {actionlimit.ISSUE_COMMENT: 1,
                actionlimit.ISSUE_ATTACHMENT: len(parsed.attachments)}
      self.CountRateLimitedActions(mr, counts)

    if mr.errors.AnyErrors():
      component_required = False
      for wkp in config.templates:
        if wkp.name == parsed.template_name:
          component_required = wkp.component_required
      self.PleaseCorrect(
          mr, initial_summary=parsed.summary, initial_status=parsed.status,
          initial_owner=parsed.users.owner_username,
          initial_cc=', '.join(parsed.users.cc_usernames),
          initial_components=', '.join(parsed.components.paths),
          initial_comment=parsed.comment, labels=bounce_labels,
          fields=bounce_fields,
          initial_blocked_on=parsed.blocked_on.entered_str,
          initial_blocking=parsed.blocking.entered_str,
          initial_hotlists=parsed.hotlists.entered_str,
          component_required=ezt.boolean(component_required))
      return

    # Initial description is comment 0.
    notify.PrepareAndSendIssueChangeNotification(
        issue.issue_id, mr.request.host, reporter_id, 0)

    notify.PrepareAndSendIssueBlockingNotification(
        issue.issue_id, mr.request.host, parsed.blocked_on.iids, reporter_id)

    # format a redirect url
    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ISSUE_DETAIL, id=issue.local_id)

def _MatchesTemplate(content, config):
    content = content.strip(string.whitespace)
    for template in config.templates:
      template_content = template.content.strip(string.whitespace)
      diff = difflib.unified_diff(content.splitlines(),
          template_content.splitlines())
      if len('\n'.join(diff)) == 0:
        return True
    return False


def _MarkupDescriptionOnInput(content, tmpl_text):
  """Return HTML for the content of an issue description or comment.

  Args:
    content: the text sumbitted by the user, any user-entered markup
             has already been escaped.
    tmpl_text: the initial text that was put into the textarea.

  Returns:
    The description content text with template lines highlighted.
  """
  tmpl_lines = tmpl_text.split('\n')
  tmpl_lines = [pl.strip() for pl in tmpl_lines if pl.strip()]

  entered_lines = content.split('\n')
  marked_lines = [_MarkupDescriptionLineOnInput(line, tmpl_lines)
                  for line in entered_lines]
  return '\n'.join(marked_lines)


def _MarkupDescriptionLineOnInput(line, tmpl_lines):
  """Markup one line of an issue description that was just entered.

  Args:
    line: string containing one line of the user-entered comment.
    tmpl_lines: list of strings for the text of the template lines.

  Returns:
    The same user-entered line, or that line highlighted to
    indicate that it came from the issue template.
  """
  for tmpl_line in tmpl_lines:
    if line.startswith(tmpl_line):
      return '<b>' + tmpl_line + '</b>' + line[len(tmpl_line):]

  return line


def _DiscardUnusedTemplateLabelPrefixes(labels):
  """Drop any labels that end in '-?'.

  Args:
    labels: a list of label strings.

  Returns:
    A list of the same labels, but without any that end with '-?'.
    Those label prefixes in the new issue templates are intended to
    prompt the user to enter some label with that prefix, but if
    nothing is entered there, we do not store anything.
  """
  return [lab for lab in labels
          if not lab.endswith('-?')]


def _SelectTemplate(requested_template_name, config, is_member):
  """Return the template to show to the user in this situation.

  Args:
    requested_template_name: name of template requested by user, or None.
    config: ProjectIssueConfig for this project.
    is_member: True if user is a project member.

  Returns:
    A Template PB with info needed to populate the issue entry form.
  """
  if requested_template_name:
    for template in config.templates:
      if requested_template_name == template.name:
        return template
    logging.info('Issue template name %s not found', requested_template_name)

  # No template was specified, or it was not found, so go with a default.
  if is_member:
    default_id = config.default_template_for_developers
  else:
    default_id = config.default_template_for_users

  # Newly created projects have no default templates specified, use hard-coded
  # positions of the templates that are defined in tracker_constants.
  if default_id == 0:
    if is_member:
      return config.templates[0]
    elif len(config.templates) > 1:
      return config.templates[1]

  # This project has a relevant default template ID that we can use.
  for template in config.templates:
    if template.template_id == default_id:
      return template

  # If it was not found, just go with a template that we know exists.
  return config.templates[0]


def ProcessParsedHotlistRefs(mr, services, parsed_hotlist_refs):
  """Process a list of ParsedHotlistRefs, returning referenced hotlists.

  This function validates the given ParsedHotlistRefs using four checks; if all
  of them succeed, then it returns the corresponding hotlist protobuf objects.
  If any of them fail, it sets the appropriate error string in mr.errors, and
  returns an empty list.

  Args:
    mr: the MonorailRequest object
    services: the service manager
    parsed_hotlist_refs: a list of ParsedHotlistRef objects

  Returns:
    on valid input, a list of hotlist protobuf objects
    if a check fails (and the input is thus considered invalid), an empty list

  Side-effects:
    if any of the checks fails, set mr.errors.hotlists to a descriptive error
  """
  # Pre-processing; common pieces used by functions later.
  user_hotlist_pbs = services.features.GetHotlistsByUserID(
      mr.cnxn, mr.auth.user_id)
  user_hotlist_owners_ids = {hotlist.owner_ids[0]
      for hotlist in user_hotlist_pbs}
  user_hotlist_owners_to_emails = services.user.LookupUserEmails(
      mr.cnxn, user_hotlist_owners_ids)
  user_hotlist_emails_to_owners = {v: k
      for k, v in user_hotlist_owners_to_emails.iteritems()}
  user_hotlist_refs_to_pbs = {
      hotlist_helpers.HotlistRef(hotlist.owner_ids[0], hotlist.name): hotlist
      for hotlist in user_hotlist_pbs }
  short_refs = list()
  full_refs = list()
  for parsed_ref in parsed_hotlist_refs:
    if parsed_ref.user_email is None:
      short_refs.append(parsed_ref)
    else:
      full_refs.append(parsed_ref)

  invalid_names = hotlist_helpers.InvalidParsedHotlistRefsNames(
      parsed_hotlist_refs, user_hotlist_pbs)
  if invalid_names:
    mr.errors.hotlists = (
        'You have no hotlist(s) named: %s' % ', '.join(invalid_names))
    return []

  ambiguous_names = hotlist_helpers.AmbiguousShortrefHotlistNames(
      short_refs, user_hotlist_pbs)
  if ambiguous_names:
    mr.errors.hotlists = (
        'Ambiguous hotlist(s) specified: %s' % ', '.join(ambiguous_names))
    return []

  # At this point, all refs' named hotlists are guaranteed to exist, and
  # short refs are guaranteed to be unambiguous;
  # therefore, short refs are also valid.
  short_refs_hotlist_names = {sref.hotlist_name for sref in short_refs}
  shortref_valid_pbs = [hotlist for hotlist in user_hotlist_pbs
      if hotlist.name in short_refs_hotlist_names]

  invalid_emails = hotlist_helpers.InvalidParsedHotlistRefsEmails(
      full_refs, user_hotlist_emails_to_owners)
  if invalid_emails:
    mr.errors.hotlists = (
        'You have no hotlist(s) owned by: %s' % ', '.join(invalid_emails))
    return []

  fullref_valid_pbs, invalid_refs = (
      hotlist_helpers.GetHotlistsOfParsedHotlistFullRefs(
        full_refs, user_hotlist_emails_to_owners, user_hotlist_refs_to_pbs))
  if invalid_refs:
    invalid_refs_readable = [':'.join(parsed_ref)
        for parsed_ref in invalid_refs]
    mr.errors.hotlists = (
        'Not in your hotlist(s): %s' % ', '.join(invalid_refs_readable))
    return []

  hotlist_pbs = shortref_valid_pbs + fullref_valid_pbs

  return hotlist_pbs
