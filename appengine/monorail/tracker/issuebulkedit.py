# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the issue bulk edit page and related forms.

Summary of classes:
  IssueBulkEdit: Show a form for editing multiple issues and allow the
     user to update them all at once.
"""

import httplib
import logging
import time

from third_party import ezt

from features import filterrules_helpers
from features import notify
from framework import actionlimit
from framework import framework_constants
from framework import framework_views
from framework import monorailrequest
from framework import permissions
from framework import servlet
from framework import template_helpers
from services import tracker_fulltext
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from tracker import tracker_views


class IssueBulkEdit(servlet.Servlet):
  """IssueBulkEdit lists multiple issues and allows an edit to all of them."""

  _PAGE_TEMPLATE = 'tracker/issue-bulk-edit-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ISSUES
  _CAPTCHA_ACTION_TYPES = [actionlimit.ISSUE_BULK_EDIT]

  _SECONDS_OVERHEAD = 4
  _SECONDS_PER_UPDATE = 0.12
  _SLOWNESS_THRESHOLD = 10

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.

    Raises:
      PermissionException: if the user is not allowed to enter an issue.
    """
    super(IssueBulkEdit, self).AssertBasePermission(mr)
    can_edit = self.CheckPerm(mr, permissions.EDIT_ISSUE)
    can_comment = self.CheckPerm(mr, permissions.ADD_ISSUE_COMMENT)
    if not (can_edit and can_comment):
      raise permissions.PermissionException('bulk edit forbidden')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    with self.profiler.Phase('getting issues'):
      if not mr.local_id_list:
        raise monorailrequest.InputException()
      requested_issues = self.services.issue.GetIssuesByLocalIDs(
          mr.cnxn, mr.project_id, sorted(mr.local_id_list))

    with self.profiler.Phase('filtering issues'):
      # TODO(jrobbins): filter out issues that the user cannot edit and
      # provide that as feedback rather than just siliently ignoring them.
      open_issues, closed_issues = (
          tracker_helpers.GetAllowedOpenedAndClosedIssues(
              mr, [issue.issue_id for issue in requested_issues],
              self.services))
      issues = open_issues + closed_issues

    if not issues:
      self.abort(404, 'no issues found')

    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    type_label_set = {
        lab.lower() for lab in issues[0].labels
        if lab.lower().startswith('type-')}
    for issue in issues[1:]:
      new_type_set = {
          lab.lower() for lab in issue.labels
          if lab.lower().startswith('type-')}
      type_label_set &= new_type_set

    field_views = [
        tracker_views.MakeFieldValueView(
            fd, config, type_label_set, [], [], {})
        # TODO(jrobbins): field-level view restrictions, display options
        # TODO(jrobbins): custom fields in templates supply values to view.
        for fd in config.field_defs
        if not fd.is_deleted]
    # Explicitly set all field views to not required. We do not want to force
    # users to have to set it for issues missing required fields.
    # See https://bugs.chromium.org/p/monorail/issues/detail?id=500 for more
    # details.
    for fv in field_views:
      fv.field_def.is_required_bool = None

    with self.profiler.Phase('making issue proxies'):
      issue_views = [
          template_helpers.EZTItem(
              local_id=issue.local_id, summary=issue.summary,
              closed=ezt.boolean(issue in closed_issues))
          for issue in issues]

    num_seconds = (int(len(issue_views) * self._SECONDS_PER_UPDATE) +
                   self._SECONDS_OVERHEAD)

    page_perms = self.MakePagePerms(
        mr, None,
        permissions.CREATE_ISSUE,
        permissions.DELETE_ISSUE)

    return {
        'issue_tab_mode': 'issueBulkEdit',
        'issues': issue_views,
        'num_issues': len(issue_views),
        'show_progress': ezt.boolean(num_seconds > self._SLOWNESS_THRESHOLD),
        'num_seconds': num_seconds,

        'initial_blocked_on': '',
        'initial_blocking': '',
        'initial_comment': '',
        'initial_status': '',
        'initial_owner': '',
        'initial_merge_into': '',
        'initial_cc': '',
        'initial_components': '',
        'labels': [],
        'fields': field_views,

        'restrict_to_known': ezt.boolean(config.restrict_to_known),
        'page_perms': page_perms,
        'statuses_offer_merge': config.statuses_offer_merge,
        }

  def ProcessFormData(self, mr, post_data):
    """Process the posted issue update form.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to after processing.
    """
    if not mr.local_id_list:
      logging.info('missing issue local IDs, probably tampered')
      self.response.status = httplib.BAD_REQUEST
      return

    # Check that the user is logged in; anon users cannot update issues.
    if not mr.auth.user_id:
      logging.info('user was not logged in, cannot update issue')
      self.response.status = httplib.BAD_REQUEST  # xxx should raise except
      return

    self.CountRateLimitedActions(
        mr, {actionlimit.ISSUE_BULK_EDIT: len(mr.local_id_list)})

    # Check that the user has permission to add a comment, and to enter
    # metadata if they are trying to do that.
    if not self.CheckPerm(mr, permissions.ADD_ISSUE_COMMENT):
      logging.info('user has no permission to add issue comment')
      self.response.status = httplib.BAD_REQUEST
      return

    if not self.CheckPerm(mr, permissions.EDIT_ISSUE):
      logging.info('user has no permission to edit issue metadata')
      self.response.status = httplib.BAD_REQUEST
      return

    move_to = post_data.get('move_to', '').lower()
    if move_to and not self.CheckPerm(mr, permissions.DELETE_ISSUE):
      logging.info('user has no permission to move issue')
      self.response.status = httplib.BAD_REQUEST
      return

    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    parsed = tracker_helpers.ParseIssueRequest(
        mr.cnxn, post_data, self.services, mr.errors, mr.project_name)
    field_helpers.ShiftEnumFieldsIntoLabels(
        parsed.labels, parsed.labels_remove,
        parsed.fields.vals, parsed.fields.vals_remove,
        config)
    field_vals = field_helpers.ParseFieldValues(
        mr.cnxn, self.services.user, parsed.fields.vals, config)
    field_vals_remove = field_helpers.ParseFieldValues(
        mr.cnxn, self.services.user, parsed.fields.vals_remove, config)

    # Treat status '' as no change and explicit 'clear' as clearing the status.
    status = parsed.status
    if status == '':
      status = None
    if post_data.get('op_statusenter') == 'clear':
      status = ''

    reporter_id = mr.auth.user_id
    logging.info('bulk edit request by %s', reporter_id)
    self.CheckCaptcha(mr, post_data)

    if parsed.users.owner_id is None:
      mr.errors.owner = 'Invalid owner username'
    else:
      valid, msg = tracker_helpers.IsValidIssueOwner(
          mr.cnxn, mr.project, parsed.users.owner_id, self.services)
      if not valid:
        mr.errors.owner = msg

    if (status in config.statuses_offer_merge and
        not post_data.get('merge_into')):
      mr.errors.merge_into_id = 'Please enter a valid issue ID'

    move_to_project = None
    if move_to:
      if mr.project_name == move_to:
        mr.errors.move_to = 'The issues are already in project ' + move_to
      else:
        move_to_project = self.services.project.GetProjectByName(
            mr.cnxn, move_to)
        if not move_to_project:
          mr.errors.move_to = 'No such project: ' + move_to

    # Treat owner '' as no change, and explicit 'clear' as NO_USER_SPECIFIED
    owner_id = parsed.users.owner_id
    if parsed.users.owner_username == '':
      owner_id = None
    if post_data.get('op_ownerenter') == 'clear':
      owner_id = framework_constants.NO_USER_SPECIFIED

    comp_ids = tracker_helpers.LookupComponentIDs(
        parsed.components.paths, config, mr.errors)
    comp_ids_remove = tracker_helpers.LookupComponentIDs(
        parsed.components.paths_remove, config, mr.errors)
    if post_data.get('op_componententer') == 'remove':
      comp_ids, comp_ids_remove = comp_ids_remove, comp_ids

    cc_ids, cc_ids_remove = parsed.users.cc_ids, parsed.users.cc_ids_remove
    if post_data.get('op_memberenter') == 'remove':
      cc_ids, cc_ids_remove = parsed.users.cc_ids_remove, parsed.users.cc_ids

    if post_data.get('op_blockedonenter') == 'append':
      blocked_on_add = parsed.blocked_on.iids
      blocked_on_remove = []
    else:
      blocked_on_add = []
      blocked_on_remove = parsed.blocked_on.iids
    if post_data.get('op_blockingenter') == 'append':
      blocking_add = parsed.blocking.iids
      blocking_remove = []
    else:
      blocking_add = []
      blocking_remove = parsed.blocking.iids

    iids_actually_changed = []
    old_owner_ids = []
    combined_amendments = []
    merge_into_issue = None
    new_starrers = set()

    if not mr.errors.AnyErrors():
      # Because we will modify issues, load from DB rather than cache.
      issue_list = self.services.issue.GetIssuesByLocalIDs(
          mr.cnxn, mr.project_id, mr.local_id_list, use_cache=False)

      # Skip any individual issues that the user is not allowed to edit.
      editable_issues = [
          issue for issue in issue_list
          if permissions.CanEditIssue(
              mr.auth.effective_ids, mr.perms, mr.project, issue)]

      # Skip any restrict issues that cannot be moved
      if move_to:
        editable_issues = [
            issue for issue in editable_issues
            if not permissions.GetRestrictions(issue)]

      # If 'Duplicate' status is specified ensure there are no permission issues
      # with the issue we want to merge with.
      if post_data.get('merge_into'):
        for issue in editable_issues:
          _, merge_into_issue = tracker_helpers.ParseMergeFields(
              mr.cnxn, self.services, mr.project_name, post_data, parsed.status,
              config, issue, mr.errors)
          if merge_into_issue:
            merge_allowed = tracker_helpers.IsMergeAllowed(
                merge_into_issue, mr, self.services)
            if not merge_allowed:
              mr.errors.merge_into_id = 'Target issue %s cannot be modified' % (
                                            merge_into_issue.local_id)
              break

            # Update the new_starrers set.
            new_starrers.update(tracker_helpers.GetNewIssueStarrers(
                mr.cnxn, self.services, issue.issue_id,
                merge_into_issue.issue_id))

      # Proceed with amendments only if there are no reported errors.
      if not mr.errors.AnyErrors():
        # Sort the issues: we want them in this order so that the
        # corresponding old_owner_id are found in the same order.
        editable_issues.sort(lambda i1, i2: cmp(i1.local_id, i2.local_id))

        iids_to_invalidate = set()
        rules = self.services.features.GetFilterRules(
            mr.cnxn, config.project_id)
        predicate_asts = filterrules_helpers.ParsePredicateASTs(
            rules, config, None)
        for issue in editable_issues:
          old_owner_id = tracker_bizobj.GetOwnerId(issue)
          merge_into_iid = (
              merge_into_issue.issue_id if merge_into_issue else None)

          amendments, _ = self.services.issue.DeltaUpdateIssue(
              mr.cnxn, self.services, mr.auth.user_id, mr.project_id, config,
              issue, status, owner_id, cc_ids, cc_ids_remove, comp_ids,
              comp_ids_remove, parsed.labels, parsed.labels_remove, field_vals,
              field_vals_remove, parsed.fields.fields_clear,
              blocked_on_add=blocked_on_add,
              blocked_on_remove=blocked_on_remove,
              blocking_add=blocking_add, blocking_remove=blocking_remove,
              merged_into=merge_into_iid, comment=parsed.comment,
              iids_to_invalidate=iids_to_invalidate, rules=rules,
              predicate_asts=predicate_asts)

          if amendments or parsed.comment:  # Avoid empty comments.
            iids_actually_changed.append(issue.issue_id)
            old_owner_ids.append(old_owner_id)
            combined_amendments.extend(amendments)

        self.services.issue.InvalidateIIDs(mr.cnxn, iids_to_invalidate)
        self.services.project.UpdateRecentActivity(
            mr.cnxn, mr.project.project_id)

        # Add new_starrers and new CCs to merge_into_issue.
        if merge_into_issue:
          merge_into_project = self.services.project.GetProjectByName(
              mr.cnxn, merge_into_issue.project_name)
          tracker_helpers.AddIssueStarrers(
              mr.cnxn, self.services, mr, merge_into_issue.issue_id,
              merge_into_project, new_starrers)
          tracker_helpers.MergeCCsAndAddCommentMultipleIssues(
              self.services, mr, editable_issues, merge_into_project,
              merge_into_issue)

        if move_to and editable_issues:
          tracker_fulltext.UnindexIssues(
              [issue.issue_id for issue in editable_issues])
          for issue in editable_issues:
            old_text_ref = 'issue %s:%s' % (issue.project_name, issue.local_id)
            moved_back_iids = self.services.issue.MoveIssues(
                mr.cnxn, move_to_project, [issue], self.services.user)
            new_text_ref = 'issue %s:%s' % (issue.project_name, issue.local_id)
            if issue.issue_id in moved_back_iids:
              content = 'Moved %s back to %s again.' % (
                  old_text_ref, new_text_ref)
            else:
              content = 'Moved %s to now be %s.' % (old_text_ref, new_text_ref)
            self.services.issue.CreateIssueComment(
                mr.cnxn, issue, mr.auth.user_id, content, amendments=[
                   tracker_bizobj.MakeProjectAmendment(
                       move_to_project.project_name)])

        send_email = 'send_email' in post_data

        users_by_id = framework_views.MakeAllUserViews(
            mr.cnxn, self.services.user,
            [owner_id], cc_ids, cc_ids_remove, old_owner_ids,
            tracker_bizobj.UsersInvolvedInAmendments(combined_amendments))
        if move_to and editable_issues:
          iids_actually_changed = [
              issue.issue_id for issue in editable_issues]

        notify.SendIssueBulkChangeNotification(
            iids_actually_changed, mr.request.host,
            old_owner_ids, parsed.comment,
            reporter_id, combined_amendments, send_email, users_by_id)

    if mr.errors.AnyErrors():
      bounce_cc_parts = (
          parsed.users.cc_usernames +
          ['-%s' % ccur for ccur in parsed.users.cc_usernames_remove])
      bounce_labels = (
          parsed.labels +
          ['-%s' % lr for lr in parsed.labels_remove])
      self.PleaseCorrect(
          mr, initial_status=parsed.status,
          initial_owner=parsed.users.owner_username,
          initial_merge_into=post_data.get('merge_into', 0),
          initial_cc=', '.join(bounce_cc_parts),
          initial_comment=parsed.comment,
          initial_components=parsed.components.entered_str,
          labels=bounce_labels)
      return

    with self.profiler.Phase('reindexing issues'):
      logging.info('starting reindexing')
      start = time.time()
      # Get the updated issues and index them
      issue_list = self.services.issue.GetIssuesByLocalIDs(
          mr.cnxn, mr.project_id, mr.local_id_list)
      tracker_fulltext.IndexIssues(
          mr.cnxn, issue_list, self.services.user, self.services.issue,
          self.services.config)
      logging.info('reindexing %d issues took %s sec',
                   len(issue_list), time.time() - start)

    # TODO(jrobbins): These could be put into the form action attribute.
    mr.can = int(post_data['can'])
    mr.query = post_data['q']
    mr.col_spec = post_data['colspec']
    mr.sort_spec = post_data['sort']
    mr.group_by_spec = post_data['groupby']
    mr.start = int(post_data['start'])
    mr.num = int(post_data['num'])

    # TODO(jrobbins): implement bulk=N param for a better confirmation alert.
    return tracker_helpers.FormatIssueListURL(
        mr, config, saved=len(mr.local_id_list), ts=int(time.time()))
