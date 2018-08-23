# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlet that implements the entry of new issues."""

import collections
import difflib
import logging
import string
import time

from businesslogic import work_env
from features import hotlist_helpers
from features import send_notifications
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
from tracker import template_helpers as issue_tmpl_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers
from tracker import tracker_views
from proto import tracker_pb2

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

    template = self._GetTemplate(mr.cnxn, config, mr.template_name, is_member)

    if template.summary:
      initial_summary = template.summary
      initial_summary_must_be_edited = template.summary_must_be_edited
    else:
      initial_summary = PLACEHOLDER_SUMMARY
      initial_summary_must_be_edited = True

    if template.status:
      initial_status = template.status
    elif is_member:
      initial_status = 'Accepted'
    else:
      initial_status = 'New'  # not offering meta, only used in hidden field.

    component_paths = []
    for component_id in template.component_ids:
      component_paths.append(
          tracker_bizobj.FindComponentDefByID(component_id, config).path)
    initial_components = ', '.join(component_paths)

    if template.owner_id:
      initial_owner = framework_views.MakeUserView(
          mr.cnxn, self.services.user, template.owner_id)
    elif template.owner_defaults_to_member and page_perms.EditIssue:
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

    config_view = tracker_views.ConfigView(mr, self.services, config, template)
    # If the user followed a link that specified the template name, make sure
    # that it is also in the menu as the current choice.
    # TODO(jeffcarp): Unit test this.
    config_view.template_view.can_view = ezt.boolean(True)

    # TODO(jeffcarp): Unit test this.
    offer_templates = len(config_view.template_names) > 1
    restrict_to_known = config.restrict_to_known
    field_name_set = {fd.field_name.lower() for fd in config.field_defs
                      if not fd.is_deleted}  # TODO(jrobbins): restrictions
    link_or_template_labels = mr.GetListParam('labels', template.labels)
    labels = [lab for lab in link_or_template_labels
              if not tracker_bizobj.LabelIsMaskedByField(lab, field_name_set)]

    approval_ids = [av.approval_id for av in template.approval_values]
    field_user_views = tracker_views.MakeFieldUserViews(
        mr.cnxn, template, self.services.user)
    field_views = tracker_views.MakeAllFieldValueViews(
        config, link_or_template_labels, [], template.field_values,
        field_user_views, parent_approval_ids=approval_ids)

    # TODO(jrobbins): remove "or []" after next release.
    (prechecked_approvals, required_approval_ids,
     phases) = issue_tmpl_helpers.GatherApprovalsPageData(
         template.approval_values or [], template.phases, config)
    approvals = [view for view in field_views if view.field_id in
                 approval_ids]
    approval_subfields_present = any(
        fv.field_def.approval_id in approval_ids for fv in field_views)
    phase_fields_present = any(
        fv.field_def.is_phase_field for fv in field_views) and any(
            phase.name for phase in phases)

    page_data = {
        'issue_tab_mode': 'issueEntry',
        'initial_summary': initial_summary,
        'template_summary': initial_summary,
        'clear_summary_on_click': ezt.boolean(
            initial_summary_must_be_edited and
            'initial_summary' not in mr.form_overrides),
        'must_edit_summary': ezt.boolean(initial_summary_must_be_edited),

        'initial_description': template.content,
        'template_name': template.name,
        'component_required': ezt.boolean(template.component_required),
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
        # The following are necessary for displaying phases that come with
        # this template. These are read-only.
        'allow_edit': ezt.boolean(False),
        'initial_phases': phases,
        'approvals': approvals,
        'prechecked_approvals': prechecked_approvals,
        'required_approval_ids': required_approval_ids,
        'approval_subfields_present': ezt.boolean(approval_subfields_present),
        'phase_fields_present': ezt.boolean(phase_fields_present),
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

    is_member = framework_bizobj.UserIsInProject(
        mr.project, mr.auth.effective_ids)
    template = self._GetTemplate(
        mr.cnxn, config, post_data.get('template_name'), is_member)

    (approval_values,
     phases) = issue_tmpl_helpers.FilterApprovalsAndPhases(
         template.approval_values or [], template.phases, config)

    field_values = field_helpers.ParseFieldValues(
        mr.cnxn, self.services.user, parsed.fields.vals, config,
        phase_ids=[phase.phase_id for phase in phases])

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

    if _MatchesTemplate(parsed.comment, template):
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
            # TODO(jrobbins): Make quota be calculated and stored as
            # part of applying the comment.
            self.services.project.UpdateProject(
                mr.cnxn, mr.project.project_id,
                attachment_bytes_used=new_bytes_used)

          marked_description = tracker_helpers.MarkupDescriptionOnInput(
              parsed.comment, template.content)
          has_star = 'star' in post_data and post_data['star'] == '1'

          if approval_values:
            _AttachDefaultApprovers(config, approval_values)

          issue, comment = we.CreateIssue(
              mr.project_id, parsed.summary, parsed.status,
              parsed.users.owner_id, parsed.users.cc_ids, labels, field_values,
              component_ids, marked_description,
              blocked_on=parsed.blocked_on.iids,
              blocking=parsed.blocking.iids, attachments=parsed.attachments,
              approval_values=approval_values, phases=phases)

          if has_star:
            we.StarIssue(issue, True)

          if hotlist_pbs:
            hotlist_ids = {hotlist.hotlist_id for hotlist in hotlist_pbs}
            issue_tuple = (issue.issue_id, mr.auth.user_id, int(time.time()),
                           '')
            self.services.features.AddIssueToHotlists(
                mr.cnxn, hotlist_ids, issue_tuple, self.services.issue,
                self.services.chart)

        except tracker_helpers.OverAttachmentQuota:
          mr.errors.attachments = 'Project attachment quota exceeded.'

      counts = {actionlimit.ISSUE_COMMENT: 1,
                actionlimit.ISSUE_ATTACHMENT: len(parsed.attachments)}
      self.CountRateLimitedActions(mr, counts)

    mr.template_name = parsed.template_name
    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr, initial_summary=parsed.summary, initial_status=parsed.status,
          initial_owner=parsed.users.owner_username,
          initial_cc=', '.join(parsed.users.cc_usernames),
          initial_components=', '.join(parsed.components.paths),
          initial_comment=parsed.comment, labels=bounce_labels,
          fields=bounce_fields, template_name=parsed.template_name,
          initial_blocked_on=parsed.blocked_on.entered_str,
          initial_blocking=parsed.blocking.entered_str,
          initial_hotlists=parsed.hotlists.entered_str,
          component_required=ezt.boolean(template.component_required))
      return

    send_notifications.PrepareAndSendIssueChangeNotification(
        issue.issue_id, mr.request.host, reporter_id, comment_id=comment.id)

    send_notifications.PrepareAndSendIssueBlockingNotification(
        issue.issue_id, mr.request.host, parsed.blocked_on.iids, reporter_id)

    # format a redirect url
    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ISSUE_DETAIL, id=issue.local_id)

  def _GetTemplate(self, cnxn, config, template_name, is_member):
    """Tries to fetch template by name and implements default template logic
    if not found."""
    template = None
    if template_name:
      template_name = template_name.replace('+', ' ')
      template = self.services.template.GetTemplateByName(cnxn,
          template_name, config.project_id)

    if not template:
      if is_member:
        template_id = config.default_template_for_developers
      else:
        template_id = config.default_template_for_users
      template = self.services.template.GetTemplateById(cnxn, template_id)
      # If the default templates were deleted, load all and pick the first one.
      if not template:
        templates = self.services.template.GetProjectTemplates(cnxn,
            config.project_id)
        assert len(templates) > 0, 'Project has no templates!'
        template = templates[0]

    return template


def _AttachDefaultApprovers(config, approval_values):
  approval_defs_by_id = {ad.approval_id: ad for ad in config.approval_defs}
  for av in approval_values:
    ad = approval_defs_by_id.get(av.approval_id)
    if ad:
      av.approver_ids = ad.approver_ids[:]
    else:
      logging.info('ApprovalDef with approval_id %r could not be found',
          av.approval_id)


def _MatchesTemplate(content, template):
  content = content.strip(string.whitespace)
  template_content = template.content.strip(string.whitespace)
  diff = difflib.unified_diff(content.splitlines(),
      template_content.splitlines())
  return len('\n'.join(diff)) == 0


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
