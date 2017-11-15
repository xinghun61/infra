# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the issue detail page and related forms.

Summary of classes:
  IssueDetail: Show one issue in detail w/ all metadata and comments, and
               process additional comments or metadata changes on it.
  SetStarForm: Record the user's desire to star or unstar an issue.
  FlagSpamForm: Record the user's desire to report the issue as spam.
"""

import httplib
import logging
import time
from third_party import ezt

import settings
from businesslogic import work_env
from features import features_bizobj
from features import notify
from features import hotlist_helpers
from features import hotlist_views
from framework import actionlimit
from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import jsonfeed
from framework import paginate
from framework import permissions
from framework import servlet
from framework import servlet_helpers
from framework import sorting
from framework import sql
from framework import template_helpers
from framework import urls
from framework import xsrf
from proto import user_pb2
from services import features_svc
from services import issue_svc
from services import tracker_fulltext
from tracker import field_helpers
from tracker import issuepeek
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers
from tracker import tracker_views


class IssueDetail(issuepeek.IssuePeek):
  """IssueDetail is a page that shows the details of one issue."""

  _PAGE_TEMPLATE = 'tracker/issue-detail-page.ezt'
  _MISSING_ISSUE_PAGE_TEMPLATE = 'tracker/issue-missing-page.ezt'
  _MAIN_TAB_MODE = issuepeek.IssuePeek.MAIN_TAB_ISSUES
  _CAPTCHA_ACTION_TYPES = [actionlimit.ISSUE_COMMENT]
  _ALLOW_VIEWING_DELETED = True

  def __init__(self, request, response, **kwargs):
    super(IssueDetail, self).__init__(request, response, **kwargs)
    self.missing_issue_template = template_helpers.MonorailTemplate(
        self._TEMPLATE_PATH + self._MISSING_ISSUE_PAGE_TEMPLATE)

  def GetTemplate(self, page_data):
    """Return a custom 404 page for skipped issue local IDs."""
    if page_data.get('http_response_code', httplib.OK) == httplib.NOT_FOUND:
      return self.missing_issue_template
    else:
      return servlet.Servlet.GetTemplate(self, page_data)

  def _GetMissingIssuePageData(
      self, mr, issue_deleted=False, issue_missing=False,
      issue_not_specified=False, issue_not_created=False,
      moved_to_project_name=None, moved_to_id=None,
      local_id=None, page_perms=None, delete_form_token=None):
    if not page_perms:
      # Make a default page perms.
      page_perms = self.MakePagePerms(mr, None, granted_perms=None)
      page_perms.CreateIssue = False
    return {
        'issue_tab_mode': 'issueDetail',
        'http_response_code': httplib.NOT_FOUND,
        'issue_deleted': ezt.boolean(issue_deleted),
        'issue_missing': ezt.boolean(issue_missing),
        'issue_not_specified': ezt.boolean(issue_not_specified),
        'issue_not_created': ezt.boolean(issue_not_created),
        'moved_to_project_name': moved_to_project_name,
        'moved_to_id': moved_to_id,
        'local_id': local_id,
        'page_perms': page_perms,
        'delete_form_token': delete_form_token,
     }

  def _GetFlipper(self, mr, issue):
    """Decides which flipper class to use.

    Args:
      mr: commonly used info parsed from the request.
      issue: the issue of the current page.

    Returns:
      The appropriate _Flipper object
    """
    # do not assign self.hotlist_id to hotlist_id until we are
    # sure the hotlist/issue pair is valid.
    # pylint: disable=attribute-defined-outside-init
    self.hotlist_id = None
    hotlist_id = mr.GetIntParam('hotlist_id')
    if hotlist_id:
      try:
        hotlist = self.services.features.GetHotlist(
            mr.cnxn, hotlist_id)
      except features_svc.NoSuchHotlistException:
        pass
      else:
        if (features_bizobj.IssueIsInHotlist(hotlist, issue.issue_id) and
            permissions.CanViewHotlist(mr.auth.effective_ids, hotlist)):
          self.hotlist_id = hotlist_id
          return _HotlistFlipper(mr, self.services, issue, hotlist)

    # if not hotlist/hotlist_id return a _TrackerFlipper
    return _TrackerFlipper(mr, self.services, issue)

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    with work_env.WorkEnv(mr, self.services) as we:
      config = we.GetProjectConfig(mr.project_id)

      if mr.local_id is None:
        return self._GetMissingIssuePageData(mr, issue_not_specified=True)
      try:
        issue = we.GetIssueByLocalID(
            mr.project_id, mr.local_id, use_cache=False)
      except issue_svc.NoSuchIssueException:
        issue = None

      # Show explanation of skipped issue local IDs or deleted issues.
      if issue is None or issue.deleted:
        missing = mr.local_id <= self.services.issue.GetHighestLocalID(
            mr.cnxn, mr.project_id)
        if missing or (issue and issue.deleted):
          moved_to_ref = self.services.issue.GetCurrentLocationOfMovedIssue(
              mr.cnxn, mr.project_id, mr.local_id)
          moved_to_project_id, moved_to_id = moved_to_ref
          if moved_to_project_id is not None:
            moved_to_project = we.GetProject(moved_to_project_id)
            moved_to_project_name = moved_to_project.project_name
          else:
            moved_to_project_name = None

          if issue:
            granted_perms = tracker_bizobj.GetGrantedPerms(
                issue, mr.auth.effective_ids, config)
          else:
            granted_perms = None
          page_perms = self.MakePagePerms(
              mr, issue,
              permissions.DELETE_ISSUE, permissions.CREATE_ISSUE,
              granted_perms=granted_perms)
          return self._GetMissingIssuePageData(
              mr,
              issue_deleted=ezt.boolean(issue is not None),
              issue_missing=ezt.boolean(issue is None and missing),
              moved_to_project_name=moved_to_project_name,
              moved_to_id=moved_to_id,
              local_id=mr.local_id,
              page_perms=page_perms,
              delete_form_token=xsrf.GenerateToken(
                  mr.auth.user_id, '/p/%s%s.do' % (
                      mr.project_name, urls.ISSUE_DELETE_JSON)))
        else:
          # Issue is not "missing," moved, or deleted, it is just non-existent.
          return self._GetMissingIssuePageData(mr, issue_not_created=True)

      star_cnxn = sql.MonorailConnection()
      star_promise = framework_helpers.Promise(
          we.IsIssueStarred, issue, cnxn=star_cnxn)

    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, mr.auth.effective_ids, config)

    page_perms = self.MakePagePerms(
        mr, issue,
        permissions.CREATE_ISSUE,
        permissions.FLAG_SPAM,
        permissions.VERDICT_SPAM,
        permissions.SET_STAR,
        permissions.EDIT_ISSUE,
        permissions.EDIT_ISSUE_SUMMARY,
        permissions.EDIT_ISSUE_STATUS,
        permissions.EDIT_ISSUE_OWNER,
        permissions.EDIT_ISSUE_CC,
        permissions.DELETE_ISSUE,
        permissions.ADD_ISSUE_COMMENT,
        permissions.DELETE_OWN,
        permissions.DELETE_ANY,
        permissions.VIEW_INBOUND_MESSAGES,
        granted_perms=granted_perms)

    issue_spam_promise = None
    issue_spam_hist_promise = None

    if page_perms.FlagSpam:
      issue_spam_cnxn = sql.MonorailConnection()
      issue_spam_promise = framework_helpers.Promise(
          self.services.spam.LookupIssueFlaggers, issue_spam_cnxn,
          issue.issue_id)

    if page_perms.VerdictSpam:
      issue_spam_hist_cnxn = sql.MonorailConnection()
      issue_spam_hist_promise = framework_helpers.Promise(
          self.services.spam.LookupIssueVerdictHistory, issue_spam_hist_cnxn,
          [issue.issue_id])

    with mr.profiler.Phase('finishing getting comments and pagination'):
      (descriptions, visible_comments,
       cmnt_pagination) = self._PaginatePartialComments(mr, issue)

    users_involved_in_issue = tracker_bizobj.UsersInvolvedInIssues([issue])
    users_involved_in_comment_list = tracker_bizobj.UsersInvolvedInCommentList(
        descriptions + visible_comments)
    with mr.profiler.Phase('making user views'):
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, users_involved_in_issue,
          users_involved_in_comment_list)
      framework_views.RevealAllEmailsToMembers(mr, users_by_id)

    issue_flaggers, comment_flaggers = [], {}
    if issue_spam_promise:
      issue_flaggers, comment_flaggers = issue_spam_promise.WaitAndGetValue()

    (issue_view, description_views,
     comment_views) = self._MakeIssueAndCommentViews(
         mr, issue, users_by_id, descriptions, visible_comments, config,
         issue_flaggers, comment_flaggers)

    with mr.profiler.Phase('getting starring info'):
      starred = star_promise.WaitAndGetValue()
      star_cnxn.Close()
      permit_edit = permissions.CanEditIssue(
          mr.auth.effective_ids, mr.perms, mr.project, issue,
          granted_perms=granted_perms)
      page_perms.EditIssue = ezt.boolean(permit_edit)
      permit_edit_cc = self.CheckPerm(
          mr, permissions.EDIT_ISSUE_CC, art=issue, granted_perms=granted_perms)
      discourage_plus_one = not (starred or permit_edit or permit_edit_cc)

    # Check whether to allow attachments from the details page
    allow_attachments = tracker_helpers.IsUnderSoftAttachmentQuota(mr.project)
    flipper = self._GetFlipper(mr, issue)
    if flipper.is_hotlist_flipper:
      mr.ComputeColSpec(flipper.hotlist)
    else:
      mr.ComputeColSpec(config)
    back_to_list_url = _ComputeBackToListURL(
        mr, issue, config, self.hotlist_id, self.services)
    restrict_to_known = config.restrict_to_known
    field_name_set = {fd.field_name.lower() for fd in config.field_defs
                      if not fd.is_deleted}  # TODO(jrobbins): restrictions
    non_masked_labels = tracker_bizobj.NonMaskedLabels(
        issue.labels, field_name_set)

    component_paths = []
    for comp_id in issue.component_ids:
      cd = tracker_bizobj.FindComponentDefByID(comp_id, config)
      if cd:
        component_paths.append(cd.path)
      else:
        logging.warn(
            'Issue %r has unknown component %r', issue.issue_id, comp_id)
    initial_components = ', '.join(component_paths)

    after_issue_update = tracker_constants.DEFAULT_AFTER_ISSUE_UPDATE
    if mr.auth.user_pb:
      after_issue_update = mr.auth.user_pb.after_issue_update

    prevent_restriction_removal = (
        mr.project.only_owners_remove_restrictions and
        not framework_bizobj.UserOwnsProject(
            mr.project, mr.auth.effective_ids))

    offer_issue_copy_move = True
    for lab in tracker_bizobj.GetLabels(issue):
      if lab.lower().startswith('restrict-'):
        offer_issue_copy_move = False

    previous_locations = self.GetPreviousLocations(mr, issue)

    spam_verdict_history = []
    if issue_spam_hist_promise:
      issue_spam_hist = issue_spam_hist_promise.WaitAndGetValue()

      spam_verdict_history = [template_helpers.EZTItem(
          created=verdict['created'].isoformat(),
          is_spam=verdict['is_spam'],
          reason=verdict['reason'],
          user_id=verdict['user_id'],
          classifier_confidence=verdict['classifier_confidence'],
          overruled=verdict['overruled'],
          ) for verdict in issue_spam_hist]

    # get hotlists that contain the current issue
    issue_hotlists = self.services.features.GetHotlistsByIssueID(
        mr.cnxn, issue.issue_id)
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user, features_bizobj.UsersInvolvedInHotlists(
            issue_hotlists))

    issue_hotlist_views = [hotlist_views.HotlistView(
        hotlist_pb, mr.auth, mr.auth.user_id, users_by_id,
        self.services.hotlist_star.IsItemStarredBy(
            mr.cnxn, hotlist_pb.hotlist_id, mr.auth.user_id)
    ) for hotlist_pb in self.services.features.GetHotlistsByIssueID(
        mr.cnxn, issue.issue_id)]

    visible_issue_hotlist_views = [view for view in issue_hotlist_views if
                                   view.visible]

    (user_issue_hotlist_views, involved_users_issue_hotlist_views,
     remaining_issue_hotlist_views) = _GetBinnedHotlistViews(
         visible_issue_hotlist_views, users_involved_in_issue)

    user_remaining_hotlists = [hotlist for hotlist in
                      self.services.features.GetHotlistsByUserID(
                          mr.cnxn, mr.auth.user_id) if
                      hotlist not in issue_hotlists]

    is_member = framework_bizobj.UserIsInProject(
        mr.project, mr.auth.effective_ids)

    return {
        'issue_tab_mode': 'issueDetail',
        'issue': issue_view,
        'title_summary': issue_view.summary,  # used in <head><title>
        'first_description': description_views[0],
        'descriptions': description_views,
        'num_descriptions': len(description_views),
        'multiple_descriptions': ezt.boolean(len(description_views) > 1),
        'comments': comment_views,
        'num_detail_rows': len(comment_views) + 4,
        'noisy': ezt.boolean(tracker_helpers.IsNoisy(
            len(comment_views), issue.star_count)),
        'link_rel_canonical': framework_helpers.FormatCanonicalURL(mr, ['id']),

        'flipper': flipper,
        'flipper_hotlist_id': self.hotlist_id,
        'cmnt_pagination': cmnt_pagination,
        'searchtip': 'You can jump to any issue by number',
        'starred': ezt.boolean(starred),
        'discourage_plus_one': ezt.boolean(discourage_plus_one),
        'pagegen': str(long(time.time() * 1000000)),
        'attachment_form_token': xsrf.GenerateToken(
            mr.auth.user_id, '/p/%s%s.do' % (
                mr.project_name, urls.ISSUE_ATTACHMENT_DELETION_JSON)),
        'delComment_form_token': xsrf.GenerateToken(
            mr.auth.user_id, '/p/%s%s.do' % (
                mr.project_name, urls.ISSUE_COMMENT_DELETION_JSON)),
       'delete_form_token': xsrf.GenerateToken(
            mr.auth.user_id, '/p/%s%s.do' % (
                mr.project_name, urls.ISSUE_DELETE_JSON)),
        'flag_spam_token': xsrf.GenerateToken(
            mr.auth.user_id, '/p/%s%s.do' % (
                mr.project_name, urls.ISSUE_FLAGSPAM_JSON)),
        'set_star_token': xsrf.GenerateToken(
            mr.auth.user_id, '/p/%s%s.do' % (
                mr.project_name, urls.ISSUE_SETSTAR_JSON)),

        # For deep linking and input correction after a failed submit.
        'initial_summary': issue_view.summary,
        'initial_comment': '',
        'initial_status': issue_view.status.name,
        'initial_owner': issue_view.owner.email,
        'initial_cc': ', '.join([pb.email for pb in issue_view.cc]),
        'initial_blocked_on': issue_view.blocked_on_str,
        'initial_blocking': issue_view.blocking_str,
        'initial_merge_into': issue_view.merged_into_str,
        'labels': non_masked_labels,
        'initial_components': initial_components,
        'fields': issue_view.fields,

        'any_errors': ezt.boolean(mr.errors.AnyErrors()),
        'allow_attachments': ezt.boolean(allow_attachments),
        'max_attach_size': template_helpers.BytesKbOrMb(
            framework_constants.MAX_POST_BODY_SIZE),
        'colspec': mr.col_spec,
        'back_to_list_url': back_to_list_url,
        'restrict_to_known': ezt.boolean(restrict_to_known),
        'after_issue_update': int(after_issue_update),  # TODO(jrobbins): str
        'prevent_restriction_removal': ezt.boolean(
            prevent_restriction_removal),
        'offer_issue_copy_move': ezt.boolean(offer_issue_copy_move),
        'statuses_offer_merge': config.statuses_offer_merge,
        'page_perms': page_perms,
        'previous_locations': previous_locations,
        'spam_verdict_history': spam_verdict_history,

        # For adding issue to user's hotlists
        'user_remaining_hotlists': user_remaining_hotlists,
        # For showing hotlists that contain this issue
        'user_issue_hotlists': user_issue_hotlist_views,
        'involved_users_issue_hotlists': involved_users_issue_hotlist_views,
        'remaining_issue_hotlists': remaining_issue_hotlist_views,

        'is_member': ezt.boolean(is_member),
    }

  def GatherHelpData(self, mr, page_data):
    """Return a dict of values to drive on-page user help.

    Args:
      mr: commonly used info parsed from the request.
      page_data: Dictionary of base and page template data.

    Returns:
      A dict of values to drive on-page user help, to be added to page_data.
    """
    help_data = super(IssueDetail, self).GatherHelpData(mr, page_data)
    dismissed = []
    if mr.auth.user_pb:
      dismissed = mr.auth.user_pb.dismissed_cues
    is_privileged_domain_user = framework_bizobj.IsPriviledgedDomainUser(
        mr.auth.user_pb.email)
    # Check if the user's query is just the ID of an existing issue.
    # If so, display a "did you mean to search?" cue card.
    jump_local_id = None
    any_availibility_message = False
    iv = page_data.get('issue')
    if iv:
      participant_views = (
          [iv.owner, iv.derived_owner] + iv.cc + iv.derived_cc)
      any_availibility_message = any(
          pv.avail_message for pv in participant_views
          if pv and pv.user_id)

    if (mr.auth.user_id and
        'privacy_click_through' not in dismissed):
      help_data['cue'] = 'privacy_click_through'
    elif (mr.auth.user_id and
        'code_of_conduct' not in dismissed):
      help_data['cue'] = 'code_of_conduct'
    elif (tracker_constants.JUMP_RE.match(mr.query) and
          'search_for_numbers' not in dismissed):
      jump_local_id = int(mr.query)
      help_data['cue'] = 'search_for_numbers'
    elif (any_availibility_message and
          'availibility_msgs' not in dismissed):
      help_data['cue'] = 'availibility_msgs'

    help_data.update({
        'is_privileged_domain_user': ezt.boolean(is_privileged_domain_user),
        'jump_local_id': jump_local_id,
        })
    return help_data

  # TODO(sheyang): Support comments incremental loading in API
  def _PaginatePartialComments(self, mr, issue):
    """Load and paginate the visible comments for the given issue."""
    abbr_comment_rows = self.services.issue.GetAbbrCommentsForIssue(
          mr.cnxn, issue.issue_id)
    if not abbr_comment_rows:
      return [], [], None

    comments = abbr_comment_rows[1:]
    all_comment_ids = [row[0] for row in comments]

    pagination_url = '%s?id=%d' % (urls.ISSUE_DETAIL, issue.local_id)
    pagination = paginate.VirtualPagination(
        mr, len(all_comment_ids),
        framework_constants.DEFAULT_COMMENTS_PER_PAGE,
        list_page_url=pagination_url,
        count_up=False, start_param='cstart', num_param='cnum',
        max_num=settings.max_comments_per_page)
    if pagination.last == 1 and pagination.start == len(all_comment_ids):
      pagination.visible = ezt.boolean(False)

    visible_comment_ids = all_comment_ids[pagination.last - 1:pagination.start]
    visible_comment_seqs = range(pagination.last, pagination.start + 1)
    visible_comments = self.services.issue.GetCommentsByID(
          mr.cnxn, visible_comment_ids, visible_comment_seqs)

    # TODO(lukasperaza): update first comments to is_description=TRUE
    # so [abbr_comment_rows[0][0]] can be removed
    description_ids = list(set([abbr_comment_rows[0][0]] +
                           [row[0] for row in abbr_comment_rows if row[3]]))
    description_seqs = [0]
    for i, abbr_comment in enumerate(comments):
      if abbr_comment[3]:
        description_seqs.append(i + 1)
    # TODO(lukasperaza): only get descriptions which haven't been deleted
    descriptions = self.services.issue.GetCommentsByID(
          mr.cnxn, description_ids, description_seqs)

    for i, desc in enumerate(descriptions):
      desc.description_num = str(i + 1)
    visible_descriptions = [d for d in descriptions
                            if d.id in visible_comment_ids]
    desc_comments = [d for d in visible_comments if d.id in description_ids]
    for i, comment in enumerate(desc_comments):
      comment.description_num = visible_descriptions[i].description_num

    return descriptions, visible_comments, pagination


  def _ValidateOwner(self, mr, post_data_owner, parsed_owner_id,
                     original_issue_owner_id):
    """Validates that the issue's owner was changed and is a valid owner.

    Args:
      mr: Commonly used info parsed from the request.
      post_data_owner: The owner as specified in the request's data.
      parsed_owner_id: The owner_id from the request.
      original_issue_owner_id: The original owner id of the issue.

    Returns:
      String error message if the owner fails validation else returns None.
    """
    parsed_owner_valid, msg = tracker_helpers.IsValidIssueOwner(
        mr.cnxn, mr.project, parsed_owner_id, self.services)
    if not parsed_owner_valid:
      # Only fail validation if the user actually changed the email address.
      original_issue_owner = self.services.user.LookupUserEmail(
          mr.cnxn, original_issue_owner_id)
      if post_data_owner != original_issue_owner:
        return msg
      else:
        # The user did not change the owner, thus do not fail validation.
        # See https://bugs.chromium.org/p/monorail/issues/detail?id=28 for
        # more details.
        pass

  def _ValidateCC(self, cc_ids, cc_usernames):
    """Validate cc list."""
    if None in cc_ids:
      invalid_cc = [cc_name for cc_name, cc_id in zip(cc_usernames, cc_ids)
                    if cc_id is None]
      return 'Invalid Cc username: %s' % ', '.join(invalid_cc)

  def ProcessFormData(self, mr, post_data):
    """Process the posted issue update form.

    Args:
      mr: commonly used info parsed from the request.
      post_data: The post_data dict for the current request.

    Returns:
      String URL to redirect the user to after processing.
    """
    with work_env.WorkEnv(mr, self.services) as we:
      issue = we.GetIssueByLocalID(
          mr.project_id, mr.local_id, use_cache=False)

    # Check that the user is logged in; anon users cannot update issues.
    if not mr.auth.user_id:
      logging.info('user was not logged in, cannot update issue')
      raise permissions.PermissionException(
          'User must be logged in to update an issue')

    # Check that the user has permission to add a comment, and to enter
    # metadata if they are trying to do that.
    if not self.CheckPerm(mr, permissions.ADD_ISSUE_COMMENT,
                          art=issue):
      logging.info('user has no permission to add issue comment')
      raise permissions.PermissionException(
          'User has no permission to comment on issue')

    parsed = tracker_helpers.ParseIssueRequest(
        mr.cnxn, post_data, self.services, mr.errors, issue.project_name)
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    bounce_labels = parsed.labels[:]
    bounce_fields = tracker_views.MakeBounceFieldValueViews(
        parsed.fields.vals, config)
    field_helpers.ShiftEnumFieldsIntoLabels(
        parsed.labels, parsed.labels_remove,
        parsed.fields.vals, parsed.fields.vals_remove, config)
    field_values = field_helpers.ParseFieldValues(
        mr.cnxn, self.services.user, parsed.fields.vals, config)

    component_ids = tracker_helpers.LookupComponentIDs(
        parsed.components.paths, config, mr.errors)

    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, mr.auth.effective_ids, config)
    # We process edits iff the user has permission, and the form
    # was generated including the editing fields.
    permit_edit = (
        permissions.CanEditIssue(
            mr.auth.effective_ids, mr.perms, mr.project, issue,
            granted_perms=granted_perms) and
        'fields_not_offered' not in post_data)
    page_perms = self.MakePagePerms(
        mr, issue,
        permissions.CREATE_ISSUE,
        permissions.EDIT_ISSUE_SUMMARY,
        permissions.EDIT_ISSUE_STATUS,
        permissions.EDIT_ISSUE_OWNER,
        permissions.EDIT_ISSUE_CC,
        granted_perms=granted_perms)
    page_perms.EditIssue = ezt.boolean(permit_edit)

    if not permit_edit:
      if not _FieldEditPermitted(
          parsed.labels, parsed.blocked_on.entered_str,
          parsed.blocking.entered_str, parsed.summary,
          parsed.status, parsed.users.owner_id,
          parsed.users.cc_ids, page_perms):
        raise permissions.PermissionException(
            'User lacks permission to edit fields')

    page_generation_time = long(post_data['pagegen'])
    reporter_id = mr.auth.user_id
    self.CheckCaptcha(mr, post_data)

    error_msg = self._ValidateOwner(
        mr, post_data.get('owner', '').strip(), parsed.users.owner_id,
        issue.owner_id)
    if error_msg:
      mr.errors.owner = error_msg

    error_msg = self._ValidateCC(
        parsed.users.cc_ids, parsed.users.cc_usernames)
    if error_msg:
      mr.errors.cc = error_msg

    if len(parsed.comment) > tracker_constants.MAX_COMMENT_CHARS:
      mr.errors.comment = 'Comment is too long'
    logging.info('parsed.summary is %r', parsed.summary)
    if len(parsed.summary) > tracker_constants.MAX_SUMMARY_CHARS:
      mr.errors.summary = 'Summary is too long'

    old_owner_id = tracker_bizobj.GetOwnerId(issue)

    orig_merged_into_iid = issue.merged_into
    merge_into_iid = issue.merged_into
    merge_into_text, merge_into_issue = tracker_helpers.ParseMergeFields(
        mr.cnxn, self.services, mr.project_name, post_data,
        parsed.status, config, issue, mr.errors)
    if merge_into_issue:
      merge_into_iid = merge_into_issue.issue_id
      merge_into_project = self.services.project.GetProjectByName(
          mr.cnxn, merge_into_issue.project_name)
      merge_allowed = tracker_helpers.IsMergeAllowed(
          merge_into_issue, mr, self.services)

      new_starrers = tracker_helpers.GetNewIssueStarrers(
          mr.cnxn, self.services, issue.issue_id, merge_into_iid)

    # For any fields that the user does not have permission to edit, use
    # the current values in the issue rather than whatever strings were parsed.
    labels = parsed.labels
    summary = parsed.summary
    is_description = parsed.is_description
    status = parsed.status
    owner_id = parsed.users.owner_id
    cc_ids = parsed.users.cc_ids
    blocked_on_iids = [iid for iid in parsed.blocked_on.iids
                       if iid != issue.issue_id]
    blocking_iids = [iid for iid in parsed.blocking.iids
                     if iid != issue.issue_id]
    dangling_blocked_on_refs = [tracker_bizobj.MakeDanglingIssueRef(*ref)
                                for ref in parsed.blocked_on.dangling_refs]
    dangling_blocking_refs = [tracker_bizobj.MakeDanglingIssueRef(*ref)
                              for ref in parsed.blocking.dangling_refs]
    if not permit_edit:
      is_description = False
      labels = issue.labels
      field_values = issue.field_values
      component_ids = issue.component_ids
      blocked_on_iids = issue.blocked_on_iids
      blocking_iids = issue.blocking_iids
      dangling_blocked_on_refs = issue.dangling_blocked_on_refs
      dangling_blocking_refs = issue.dangling_blocking_refs
      merge_into_iid = issue.merged_into
      if not page_perms.EditIssueSummary:
        summary = issue.summary
      if not page_perms.EditIssueStatus:
        status = issue.status
      if not page_perms.EditIssueOwner:
        owner_id = issue.owner_id
      if not page_perms.EditIssueCc:
        cc_ids = issue.cc_ids

    field_helpers.ValidateCustomFields(
        mr, self.services, field_values, config, mr.errors)

    orig_blocked_on = issue.blocked_on_iids
    if not mr.errors.AnyErrors():
      with work_env.WorkEnv(mr, self.services) as we:
        try:
          if parsed.attachments:
            new_bytes_used = tracker_helpers.ComputeNewQuotaBytesUsed(
                mr.project, parsed.attachments)
            we.UpdateProject(
                mr.project.project_id, attachment_bytes_used=new_bytes_used)

          # Store everything we got from the form.  If the user lacked perms
          # any attempted edit would be a no-op because of the logic above.
          amendments, _ = self.services.issue.ApplyIssueComment(
            mr.cnxn, self.services,
            mr.auth.user_id, mr.project_id, mr.local_id, summary, status,
            owner_id, cc_ids, labels, field_values, component_ids,
            blocked_on_iids, blocking_iids, dangling_blocked_on_refs,
            dangling_blocking_refs, merge_into_iid,
            page_gen_ts=page_generation_time, comment=parsed.comment,
            is_description=is_description, attachments=parsed.attachments,
            kept_attachments=parsed.kept_attachments if is_description else [])
          self.services.project.UpdateRecentActivity(
              mr.cnxn, mr.project.project_id)

          # Also update the Issue PB we have in RAM so that the correct
          # CC list will be used for an issue merge.
          # TODO(jrobbins): refactor the call above to: 1. compute the updates
          # and update the issue PB in RAM, then 2. store the updated issue.
          issue.cc_ids = cc_ids
          issue.labels = labels

        except tracker_helpers.OverAttachmentQuota:
          mr.errors.attachments = 'Project attachment quota exceeded.'

      if (merge_into_issue and merge_into_iid != orig_merged_into_iid and
          merge_allowed):
        tracker_helpers.AddIssueStarrers(
            mr.cnxn, self.services, mr,
            merge_into_iid, merge_into_project, new_starrers)
        merge_comment = tracker_helpers.MergeCCsAndAddComment(
            self.services, mr, issue, merge_into_project, merge_into_issue)
      elif merge_into_issue:
        merge_comment = None
        logging.info('merge denied: target issue %s not modified',
                     merge_into_iid)
      # TODO(jrobbins): distinguish between EditIssue and
      # AddIssueComment and do just the part that is allowed.
      # And, give feedback in the source issue if any part of the
      # merge was not allowed.  Maybe use AJAX to check as the
      # user types in the issue local ID.

      counts = {actionlimit.ISSUE_COMMENT: 1,
                actionlimit.ISSUE_ATTACHMENT: len(parsed.attachments)}
      self.CountRateLimitedActions(mr, counts)

    copy_to_project = CheckCopyIssueRequest(
        self.services, mr, issue, post_data.get('more_actions') == 'copy',
        post_data.get('copy_to'), mr.errors)
    move_to_project = CheckMoveIssueRequest(
        self.services, mr, issue, post_data.get('more_actions') == 'move',
        post_data.get('move_to'), mr.errors)

    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr, initial_summary=parsed.summary,
          initial_status=parsed.status,
          initial_owner=parsed.users.owner_username,
          initial_cc=', '.join(parsed.users.cc_usernames),
          initial_components=', '.join(parsed.components.paths),
          initial_comment=parsed.comment,
          labels=bounce_labels, fields=bounce_fields,
          initial_blocked_on=parsed.blocked_on.entered_str,
          initial_blocking=parsed.blocking.entered_str,
          initial_merge_into=merge_into_text)
      return

    send_email = 'send_email' in post_data or not permit_edit

    moved_to_project_name_and_local_id = None
    copied_to_project_name_and_local_id = None
    if move_to_project:
      moved_to_project_name_and_local_id = self.HandleCopyOrMove(
          mr.cnxn, mr, move_to_project, issue, send_email, move=True)
    elif copy_to_project:
      copied_to_project_name_and_local_id = self.HandleCopyOrMove(
          mr.cnxn, mr, copy_to_project, issue, send_email, move=False)

    # TODO(sheyang): use global issue id in case the issue gets moved again
    # before the task gets processed
    if amendments or parsed.comment.strip() or parsed.attachments:
      cmnts = self.services.issue.GetCommentsForIssue(mr.cnxn, issue.issue_id)
      notify.PrepareAndSendIssueChangeNotification(
          issue.issue_id, mr.request.host, reporter_id, len(cmnts) - 1,
          send_email=send_email, old_owner_id=old_owner_id)

    if merge_into_issue and merge_allowed and merge_comment:
      cmnts = self.services.issue.GetCommentsForIssue(
          mr.cnxn, merge_into_issue.issue_id)
      notify.PrepareAndSendIssueChangeNotification(
          merge_into_issue.issue_id, mr.request.host, reporter_id,
          len(cmnts) - 1, send_email=send_email)

    if permit_edit:
      # Only users who can edit metadata could have edited blocking.
      blockers_added, blockers_removed = framework_helpers.ComputeListDeltas(
          orig_blocked_on, blocked_on_iids)
      delta_blockers = blockers_added + blockers_removed
      notify.PrepareAndSendIssueBlockingNotification(
          issue.issue_id, mr.request.host,
          delta_blockers, reporter_id, send_email=send_email)
      # We don't send notification emails to newly blocked issues: either they
      # know they are blocked, or they don't care and can be fixed anyway.
      # This is the same behavior as the issue entry page.

    after_issue_update = _DetermineAndSetAfterIssueUpdate(
        self.services, mr, post_data)
    return _Redirect(
        mr, post_data, issue.local_id, config,
        moved_to_project_name_and_local_id,
        copied_to_project_name_and_local_id, after_issue_update)

  def HandleCopyOrMove(self, cnxn, mr, dest_project, issue, send_email, move):
    """Handle Requests dealing with copying or moving an issue between projects.

    Args:
      cnxn: connection to the database.
      mr: commonly used info parsed from the request.
      dest_project: The project protobuf we are moving the issue to.
      issue: The issue protobuf being moved.
      send_email: True to send email for these actions.
      move: Whether this is a move request. The original issue will not exist if
            this is True.

    Returns:
      A tuple of (project_id, local_id) of the newly copied / moved issue.
    """
    old_text_ref = 'issue %s:%s' % (issue.project_name, issue.local_id)
    if move:
      tracker_fulltext.UnindexIssues([issue.issue_id])
      moved_back_iids = self.services.issue.MoveIssues(
          cnxn, dest_project, [issue], self.services.user)
      ret_project_name_and_local_id = (issue.project_name, issue.local_id)
      new_text_ref = 'issue %s:%s' % ret_project_name_and_local_id
      if issue.issue_id in moved_back_iids:
        content = 'Moved %s back to %s again.' % (old_text_ref, new_text_ref)
      else:
        content = 'Moved %s to now be %s.' % (old_text_ref, new_text_ref)
      comment = self.services.issue.CreateIssueComment(
          mr.cnxn, issue, mr.auth.user_id, content, amendments=[
              tracker_bizobj.MakeProjectAmendment(dest_project.project_name)])
    else:
      copied_issues = self.services.issue.CopyIssues(
          cnxn, dest_project, [issue], self.services.user, mr.auth.user_id)
      copied_issue = copied_issues[0]
      ret_project_name_and_local_id = (copied_issue.project_name,
                                       copied_issue.local_id)
      new_text_ref = 'issue %s:%s' % ret_project_name_and_local_id

      # Add comment to the copied issue.
      old_issue_content = 'Copied %s to %s' % (old_text_ref, new_text_ref)
      self.services.issue.CreateIssueComment(
          mr.cnxn, issue, mr.auth.user_id, old_issue_content)

      # Add comment to the newly created issue.
      # Add project amendment only if the project changed.
      amendments = []
      if issue.project_id != copied_issue.project_id:
        amendments.append(
            tracker_bizobj.MakeProjectAmendment(dest_project.project_name))
      new_issue_content = 'Copied %s from %s' % (new_text_ref, old_text_ref)
      comment = self.services.issue.CreateIssueComment(
          mr.cnxn, copied_issue,
          mr.auth.user_id, new_issue_content, amendments=amendments)

    tracker_fulltext.IndexIssues(
        mr.cnxn, [issue], self.services.user, self.services.issue,
        self.services.config)

    if send_email:
      logging.info('TODO(jrobbins): send email for a move? or combine? %r',
                   comment)

    return ret_project_name_and_local_id


def _DetermineAndSetAfterIssueUpdate(services, mr, post_data):
  after_issue_update = tracker_constants.DEFAULT_AFTER_ISSUE_UPDATE
  if 'after_issue_update' in post_data:
    after_issue_update = user_pb2.IssueUpdateNav(
        int(post_data['after_issue_update'][0]))
    if after_issue_update != mr.auth.user_pb.after_issue_update:
      logging.info('setting after_issue_update to %r', after_issue_update)
      services.user.UpdateUserSettings(
          mr.cnxn, mr.auth.user_id, mr.auth.user_pb,
          after_issue_update=after_issue_update)

  return after_issue_update


def _Redirect(
    mr, post_data, local_id, config, moved_to_project_name_and_local_id,
    copied_to_project_name_and_local_id, after_issue_update):
  """Prepare a redirect URL for the issuedetail servlets.

  Args:
    mr: common information parsed from the HTTP request.
    post_data: The post_data dict for the current request.
    local_id: int Issue ID for the current request.
    config: The ProjectIssueConfig pb for the current request.
    moved_to_project_name_and_local_id: tuple containing the project name the
      issue was moved to and the local id in that project.
    copied_to_project_name_and_local_id: tuple containing the project name the
      issue was copied to and the local id in that project.
    after_issue_update: User preference on where to go next.

  Returns:
    String URL to redirect the user to after processing.
  """
  mr.can = int(post_data['can'])
  mr.query = post_data['q']
  mr.col_spec = post_data['colspec']
  mr.sort_spec = post_data['sort']
  mr.group_by_spec = post_data['groupby']
  mr.start = int(post_data['start'])
  mr.num = int(post_data['num'])
  mr.local_id = local_id

  # format a redirect url
  next_id = post_data.get('next_id', '')
  next_project = post_data.get('next_project', '')
  hotlist_id = post_data.get('hotlist_id', None)
  url = _ChooseNextPage(
      mr, local_id, config, moved_to_project_name_and_local_id,
      copied_to_project_name_and_local_id, after_issue_update, next_id,
      next_project=next_project, hotlist_id=hotlist_id)
  logging.debug('Redirecting user to: %s', url)
  return url


def _ComputeBackToListURL(mr, issue, config, hotlist_id, services):
  """Construct a URL to return the user to the place that they came from."""
  if hotlist_id:
    hotlist = services.features.GetHotlistByID(mr.cnxn, hotlist_id)
    return hotlist_helpers.GetURLOfHotlist(mr.cnxn, hotlist, services.user)
  back_to_list_url = None
  if not tracker_constants.JUMP_RE.match(mr.query):
    back_to_list_url = tracker_helpers.FormatIssueListURL(
        mr, config, cursor='%s:%d' % (issue.project_name, issue.local_id))

  return back_to_list_url


def _FieldEditPermitted(
    labels, blocked_on_str, blocking_str, summary, status, owner_id, cc_ids,
    page_perms):
  """Check permissions on editing individual form fields.

  This check is only done if the user does not have the overall
  EditIssue perm.  If the user edited any field that they do not have
  permission to edit, then they could have forged a post, or maybe
  they had a valid form open in a browser tab while at the same time
  their perms in the project were reduced.  Either way, the servlet
  gives them a BadRequest HTTP error and makes them go back and try
  again.

  TODO(jrobbins): It would be better to show a custom error page that
  takes the user back to the issue with a new page load rather than
  having the user use the back button.

  Args:
    labels: list of label values parsed from the form.
    blocked_on_str: list of blocked-on values parsed from the form.
    blocking_str: list of blocking values parsed from the form.
    summary: issue summary string parsed from the form.
    status: issue status string parsed from the form.
    owner_id: issue owner user ID parsed from the form and looked up.
    cc_ids: list of user IDs for Cc'd users parsed from the form.
    page_perms: object with fields for permissions the current user
        has on the current issue.

  Returns:
    True if there was no permission violation.  False if the user tried
    to edit something that they do not have permission to edit.
  """
  if labels or blocked_on_str or blocking_str:
    logging.info('user has no permission to edit issue metadata')
    return False

  if summary and not page_perms.EditIssueSummary:
    logging.info('user has no permission to edit issue summary field')
    return False

  if status and not page_perms.EditIssueStatus:
    logging.info('user has no permission to edit issue status field')
    return False

  if owner_id and not page_perms.EditIssueOwner:
    logging.info('user has no permission to edit issue owner field')
    return False

  if cc_ids and not page_perms.EditIssueCc:
    logging.info('user has no permission to edit issue cc field')
    return False

  return True


def _ChooseNextPage(
    mr, local_id, config, moved_to_project_name_and_local_id,
    copied_to_project_name_and_local_id, after_issue_update, next_id,
    next_project=None, hotlist_id=None):
  """Choose the next page to show the user after an issue update.

  Args:
    mr: information parsed from the request.
    local_id: int Issue ID of the issue that was updated.
    config: project issue config object.
    moved_to_project_name_and_local_id: tuple containing the project name the
      issue was moved to and the local id in that project.
    copied_to_project_name_and_local_id: tuple containing the project name the
      issue was copied to and the local id in that project.
    after_issue_update: user pref on where to go next.
    next_id: string local ID of next issue at the time the form was generated.
    next_project: project name of the next issue's project, None if next
      issue's project is the same as the current's project (before any changes)
    hotlist_id: optional hotlist_id for when an issue is visited via a hotlist

  Returns:
    String absolute URL of next page to view.
  """
  issue_ref_str = '%s:%d' % (mr.project_name, local_id)
  if next_project is None:
    next_project = mr.project_name
  kwargs = {
    'ts': int(time.time()),
    'cursor': issue_ref_str,
  }
  if moved_to_project_name_and_local_id:
    kwargs['moved_to_project'] = moved_to_project_name_and_local_id[0]
    kwargs['moved_to_id'] = moved_to_project_name_and_local_id[1]
  elif copied_to_project_name_and_local_id:
    kwargs['copied_from_id'] = local_id
    kwargs['copied_to_project'] = copied_to_project_name_and_local_id[0]
    kwargs['copied_to_id'] = copied_to_project_name_and_local_id[1]
  else:
    kwargs['updated'] = local_id
  # if issue is being visited via a hotlist and it gets moved to another
  # project, going to issue list should mean going to hotlistissues list.
  issue_kwargs = {}
  if hotlist_id:
    url = framework_helpers.FormatAbsoluteURL(
        mr, '/u/%s/hotlists/%s' % (mr.auth.user_id, hotlist_id),
        include_project=False, **kwargs)
    issue_kwargs['hotlist_id'] = hotlist_id
  else:
    url = tracker_helpers.FormatIssueListURL(
        mr, config, **kwargs)

  if after_issue_update == user_pb2.IssueUpdateNav.STAY_SAME_ISSUE:
    # If it was a move request then will have to switch to the new project to
    # stay on the same issue.
    if moved_to_project_name_and_local_id:
      mr.project_name = moved_to_project_name_and_local_id[0]
    issue_kwargs['id'] = local_id
    url = framework_helpers.FormatAbsoluteURL(
        mr, urls.ISSUE_DETAIL, **issue_kwargs)
  elif after_issue_update == user_pb2.IssueUpdateNav.NEXT_IN_LIST:
    if next_id:
      issue_kwargs['id'] = next_id
      url = framework_helpers.FormatAbsoluteURL(
          mr, urls.ISSUE_DETAIL, project_name=next_project, **issue_kwargs)

  return url


class SetStarForm(jsonfeed.JsonFeed):
  """Star or unstar the specified issue for the logged in user."""

  def AssertBasePermission(self, mr):
    super(SetStarForm, self).AssertBasePermission(mr)
    issue = self.services.issue.GetIssueByLocalID(
        mr.cnxn, mr.project_id, mr.local_id)
    if not self.CheckPerm(mr, permissions.SET_STAR, art=issue):
      raise permissions.PermissionException(
          'You are not allowed to star issues')
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, mr.auth.effective_ids, config)
    permit_view = permissions.CanViewIssue(
        mr.auth.effective_ids, mr.perms, mr.project, issue,
        granted_perms=granted_perms)
    if not permit_view:
      logging.warning('Issue is %r', issue)
      raise permissions.PermissionException(
          'User is not allowed to view this issue, so cannot star it')

  def HandleRequest(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    with work_env.WorkEnv(mr, self.services) as we:
      # Because we will modify issues, load from DB rather than cache.
      issue = we.GetIssueByLocalID(mr.project_id, mr.local_id, use_cache=False)
      we.StarIssue(issue, mr.starred)

    return {
        'starred': bool(mr.starred),
        }


def _ShouldShowFlipper(mr, services):
  """Return True if we should show the flipper."""

  # Check if the user entered a specific issue ID of an existing issue.
  if tracker_constants.JUMP_RE.match(mr.query):
    return False

  # Check if the user came directly to an issue without specifying any
  # query or sort.  E.g., through crbug.com.  Generating the issue ref
  # list can be too expensive in projects that have a large number of
  # issues.  The all and open issues cans are broad queries, other
  # canned queries should be narrow enough to not need this special
  # treatment.
  if (not mr.query and not mr.sort_spec and
      mr.can in [tracker_constants.ALL_ISSUES_CAN,
                 tracker_constants.OPEN_ISSUES_CAN]):
    num_issues_in_project = services.issue.GetHighestLocalID(
        mr.cnxn, mr.project_id)
    if num_issues_in_project > settings.threshold_to_suppress_prev_next:
      return False

  return True


class _Flipper(object):
  """Helper class for user to flip among issues within a context."""

  def __init__(self, services):
    """Store info for issue flipper widget (prev & next navigation).

    Args:
      services: connections to backend services.
    """
    self.services = services
    self.is_hotlist_flipper = False

  def AssignFlipperValues(self, mr, prev_iid, cur_index, next_iid, total_count):
    # pylint: disable=attribute-defined-outside-init
    if cur_index is None or total_count == 1:
      # The user probably edited the URL, or bookmarked an issue
      # in a search context that no longer matches the issue.
      self.show = ezt.boolean(False)
    else:
      self.show = True
      self.current = cur_index + 1
      self.total_count = total_count
      self.next_id = None
      self.next_project_name = None
      self.prev_url = ''
      self.next_url = ''
      self.next_project = ''

      if prev_iid:
        prev_issue = self.services.issue.GetIssue(mr.cnxn, prev_iid)
        prev_path = '/p/%s%s' % (prev_issue.project_name, urls.ISSUE_DETAIL)
        self.prev_url = framework_helpers.FormatURL(
            mr, prev_path, id=prev_issue.local_id)

      if next_iid:
        next_issue = self.services.issue.GetIssue(mr.cnxn, next_iid)
        self.next_id = next_issue.local_id
        self.next_project_name = next_issue.project_name
        next_path = '/p/%s%s' % (next_issue.project_name, urls.ISSUE_DETAIL)
        self.next_url = framework_helpers.FormatURL(
            mr, next_path, id=next_issue.local_id)
        self.next_project = next_issue.project_name

  def DebugString(self):
    """Return a string representation useful in debugging."""
    if self.show:
      return 'on %s of %s; prev_url:%s; next_url:%s' % (
          self.current, self.total_count, self.prev_url, self.next_url)
    else:
      return 'invisible flipper(show=%s)' % self.show


class _HotlistFlipper(_Flipper):
  """Helper class for user to flip among issues within a hotlist."""

  def __init__(self, mr, services, current_issue, hotlist):
    """Store info for a hotlist's issue flipper widget (prev & next nav.)

    Args:
      mr: commonly used info parsed from the request.
      services: connections to backend services.
      current_issue: the currently viewed issue.
      hotlist: the hotlist this flipper is flipping through.
    """
    super(_HotlistFlipper, self).__init__(services)
    self.hotlist = hotlist
    self.is_hotlist_flipper = True

    issues_list = self.services.issue.GetIssues(
        mr.cnxn,
        [item.issue_id for item in self.hotlist.items])
    project_ids = hotlist_helpers.GetAllProjectsOfIssues(
        [issue for issue in issues_list])
    config_list = hotlist_helpers.GetAllConfigsOfProjects(
        mr.cnxn, project_ids, services)
    harmonized_config = tracker_bizobj.HarmonizeConfigs(config_list)

    (sorted_issues, _hotlist_issues_context,
     _users) = hotlist_helpers.GetSortedHotlistIssues(
         mr, self.hotlist.items, issues_list, harmonized_config,
         services)

    (prev_iid, cur_index,
     next_iid) = features_bizobj.DetermineHotlistIssuePosition(
         current_issue, [issue.issue_id for issue in sorted_issues])

    logging.info('prev_iid, cur_index, next_iid is %r %r %r',
                 prev_iid, cur_index, next_iid)

    self.AssignFlipperValues(
        mr, prev_iid, cur_index, next_iid, len(sorted_issues))


class _TrackerFlipper(_Flipper):
  """Helper class for user to flip among issues within a search result."""

  def __init__(self, mr, services, issue):
    """Store info for issue flipper widget (prev & next navigation).

    Args:
      mr: commonly used info parsed from the request.
      services: connections to backend services.
    """
    super(_TrackerFlipper, self).__init__(services)
    if not _ShouldShowFlipper(mr, services):
      self.show = ezt.boolean(False)
      return

    with work_env.WorkEnv(mr, services) as we:
      (prev_iid, cur_index, next_iid, total_count,
       ) = we.FindIssuePositionInSearch(issue)
      logging.info('prev_iid, cur_index, next_iid is %r %r %r',
                   prev_iid, cur_index, next_iid)
      self.AssignFlipperValues(
          mr, prev_iid, cur_index, next_iid, total_count)


class IssueCommentDeletion(servlet.Servlet):
  """Form handler that allows user to delete/undelete comments."""

  def ProcessFormData(self, mr, post_data):
    """Process the form that un/deletes an issue comment.

    Args:
      mr: commonly used info parsed from the request.
      post_data: The post_data dict for the current request.

    Returns:
      String URL to redirect the user to after processing.
    """
    logging.info('post_data = %s', post_data)
    local_id = int(post_data['id'])
    sequence_num = int(post_data['sequence_num'])
    delete = (post_data['mode'] == '1')
    hotlist_id = post_data.get('hotlist_id', None)

    with work_env.WorkEnv(mr, self.services) as we:
      issue = we.GetIssueByLocalID(mr.project_id, local_id, use_cache=False)
      config = we.GetProjectConfig(mr.project_id)

      all_comments = we.ListIssueComments(issue)
      logging.info('comments on %s are: %s', local_id, all_comments)
      comment = all_comments[sequence_num]

      granted_perms = tracker_bizobj.GetGrantedPerms(
          issue, mr.auth.effective_ids, config)

      if ((comment.is_spam and mr.auth.user_id == comment.user_id) or
          not permissions.CanDelete(
          mr.auth.user_id, mr.auth.effective_ids, mr.perms,
          comment.deleted_by, comment.user_id, mr.project,
          permissions.GetRestrictions(issue), granted_perms=granted_perms)):
        raise permissions.PermissionException('Cannot delete comment')

      we.DeleteComment(issue, comment, delete)

    kwargs = {'id': local_id}
    if hotlist_id:
      kwargs['hotlist_id'] = hotlist_id
    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ISSUE_DETAIL, **kwargs)


class IssueDeleteForm(servlet.Servlet):
  """A form handler to delete or undelete an issue.

  Project owners will see a button on every issue to delete it, and
  if they specifically visit a deleted issue they will see a button to
  undelete it.
  """

  def ProcessFormData(self, mr, post_data):
    """Process the form that un/deletes an issue comment.

    Args:
      mr: commonly used info parsed from the request.
      post_data: The post_data dict for the current request.

    Returns:
      String URL to redirect the user to after processing.
    """
    local_id = int(post_data['id'])
    delete = 'delete' in post_data
    logging.info('Marking issue %d as deleted: %r', local_id, delete)

    with work_env.WorkEnv(mr, self.services) as we:
      issue = we.GetIssueByLocalID(mr.project_id, local_id)
      config = we.GetProjectConfig(mr.project_id)
      granted_perms = tracker_bizobj.GetGrantedPerms(
          issue, mr.auth.effective_ids, config)
      permit_delete = self.CheckPerm(
          mr, permissions.DELETE_ISSUE, art=issue, granted_perms=granted_perms)
      if not permit_delete:
        raise permissions.PermissionException('Cannot un/delete issue')
      we.DeleteIssue(issue, delete)

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ISSUE_DETAIL, id=local_id)

# TODO(jrobbins): do we want this?
# class IssueDerivedLabelsJSON(jsonfeed.JsonFeed)


def CheckCopyIssueRequest(
    services, mr, issue, copy_selected, copy_to, errors):
  """Process the copy issue portions of the issue update form.

  Args:
    services: A Services object
    mr: commonly used info parsed from the request.
    issue: Issue protobuf for the issue being copied.
    copy_selected: True if the user selected the Copy action.
    copy_to: A project_name or url to copy this issue to or None
      if the project name wasn't sent in the form.
    errors: The errors object for this request.

    Returns:
      The project pb for the project the issue will be copy to
      or None if the copy cannot be performed. Perhaps because
      the project does not exist, in which case copy_to and
      copy_to_project will be set on the errors object. Perhaps
      the user does not have permission to copy the issue to the
      destination project, in which case the copy_to field will be
      set on the errors object.
  """
  if not copy_selected:
    return None

  if not copy_to:
    errors.copy_to = 'No destination project specified'
    errors.copy_to_project = copy_to
    return None

  copy_to_project = services.project.GetProjectByName(mr.cnxn, copy_to)
  if not copy_to_project:
    errors.copy_to = 'No such project: ' + copy_to
    errors.copy_to_project = copy_to
    return None

  # permissions enforcement
  if not servlet_helpers.CheckPermForProject(
      mr, permissions.EDIT_ISSUE, copy_to_project):
    errors.copy_to = 'You do not have permission to copy issues to project'
    errors.copy_to_project = copy_to
    return None

  elif permissions.GetRestrictions(issue):
    errors.copy_to = (
        'Issues with Restrict labels are not allowed to be copied.')
    errors.copy_to_project = ''
    return None

  return copy_to_project


def CheckMoveIssueRequest(
    services, mr, issue, move_selected, move_to, errors):
  """Process the move issue portions of the issue update form.

  Args:
    services: A Services object
    mr: commonly used info parsed from the request.
    issue: Issue protobuf for the issue being moved.
    move_selected: True if the user selected the Move action.
    move_to: A project_name or url to move this issue to or None
      if the project name wasn't sent in the form.
    errors: The errors object for this request.

    Returns:
      The project pb for the project the issue will be moved to
      or None if the move cannot be performed. Perhaps because
      the project does not exist, in which case move_to and
      move_to_project will be set on the errors object. Perhaps
      the user does not have permission to move the issue to the
      destination project, in which case the move_to field will be
      set on the errors object.
  """
  if not move_selected:
    return None

  if not move_to:
    errors.move_to = 'No destination project specified'
    errors.move_to_project = move_to
    return None

  if issue.project_name == move_to:
    errors.move_to = 'This issue is already in project ' + move_to
    errors.move_to_project = move_to
    return None

  move_to_project = services.project.GetProjectByName(mr.cnxn, move_to)
  if not move_to_project:
    errors.move_to = 'No such project: ' + move_to
    errors.move_to_project = move_to
    return None

  # permissions enforcement
  if not servlet_helpers.CheckPermForProject(
      mr, permissions.EDIT_ISSUE, move_to_project):
    errors.move_to = 'You do not have permission to move issues to project'
    errors.move_to_project = move_to
    return None

  elif permissions.GetRestrictions(issue):
    errors.move_to = (
        'Issues with Restrict labels are not allowed to be moved.')
    errors.move_to_project = ''
    return None

  return move_to_project


def _GetBinnedHotlistViews(visible_hotlist_views, involved_users):
  """Bins into (logged-in user's, issue-involved users', others') hotlists"""
  user_issue_hotlist_views = []
  involved_users_issue_hotlist_views = []
  remaining_issue_hotlist_views = []

  for view in visible_hotlist_views:
    if view.role_name in ('owner', 'editor'):
      user_issue_hotlist_views.append(view)
    elif view.owner_ids[0] in involved_users:
      involved_users_issue_hotlist_views.append(view)
    else:
      remaining_issue_hotlist_views.append(view)

  return (user_issue_hotlist_views, involved_users_issue_hotlist_views,
          remaining_issue_hotlist_views)
