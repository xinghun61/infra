# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the issue peek page and related forms."""

import logging
import time
from third_party import ezt

import settings
from features import commands
from features import notify
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import monorailrequest
from framework import paginate
from framework import permissions
from framework import servlet
from framework import sql
from framework import template_helpers
from framework import urls
from framework import xsrf
from services import issue_svc
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers
from tracker import tracker_views


class IssuePeek(servlet.Servlet):
  """IssuePeek is a page that shows the details of one issue."""

  _PAGE_TEMPLATE = 'tracker/issue-peek-ajah.ezt'
  _ALLOW_VIEWING_DELETED = False

  def AssertBasePermission(self, mr):
    """Check that the user has permission to even visit this page."""
    super(IssuePeek, self).AssertBasePermission(mr)
    try:
      issue = self._GetIssue(mr)
    except issue_svc.NoSuchIssueException:
      return
    if not issue:
      return
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, mr.auth.effective_ids, config)
    permit_view = permissions.CanViewIssue(
        mr.auth.effective_ids, mr.perms, mr.project, issue,
        allow_viewing_deleted=self._ALLOW_VIEWING_DELETED,
        granted_perms=granted_perms)
    if not permit_view:
      logging.warning('Issue is %r', issue)
      raise permissions.PermissionException(
          'User is not allowed to view this issue')

  def _GetIssue(self, mr):
    """Retrieve the current issue."""
    if mr.local_id is None:
      return None  # GatherPageData will detect the same condition.

    # TODO(jrobbins): Re-enable the issue cache on issue detail pages after
    # the stale issue defect (monorail:2514) is 100% resolved.
    issue = self.services.issue.GetIssueByLocalID(
        mr.cnxn, mr.project_id, mr.local_id, use_cache=False)
    return issue

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    if mr.local_id is None:
      self.abort(404, 'no issue specified')
    with self.profiler.Phase('finishing getting issue'):
      issue = self._GetIssue(mr)
      if issue is None:
        self.abort(404, 'issue not found')

    # We give no explanation of missing issues on the peek page.
    if issue is None or issue.deleted:
      self.abort(404, 'issue not found')

    star_cnxn = sql.MonorailConnection()
    star_promise = framework_helpers.Promise(
        self.services.issue_star.IsItemStarredBy, star_cnxn,
        issue.issue_id, mr.auth.user_id)

    with self.profiler.Phase('getting project issue config'):
      config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    with self.profiler.Phase('finishing getting comments'):
      comments = self.services.issue.GetCommentsForIssue(
          mr.cnxn, issue.issue_id)

    descriptions, visible_comments, cmnt_pagination = PaginateComments(
        mr, issue, comments, config)

    with self.profiler.Phase('making user proxies'):
      involved_user_ids = tracker_bizobj.UsersInvolvedInIssues([issue])
      group_ids = self.services.usergroup.DetermineWhichUserIDsAreGroups(
          mr.cnxn, involved_user_ids)
      comment_user_ids = tracker_bizobj.UsersInvolvedInCommentList(
          descriptions + visible_comments)
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, involved_user_ids,
          comment_user_ids, group_ids=group_ids)
      framework_views.RevealAllEmailsToMembers(mr, users_by_id)

    (issue_view, description_views,
     comment_views) = self._MakeIssueAndCommentViews(
         mr, issue, users_by_id, descriptions, visible_comments, config)

    with self.profiler.Phase('getting starring info'):
      starred = star_promise.WaitAndGetValue()
      star_cnxn.Close()
      permit_edit = permissions.CanEditIssue(
          mr.auth.effective_ids, mr.perms, mr.project, issue)

    mr.ComputeColSpec(config)
    restrict_to_known = config.restrict_to_known

    page_perms = self.MakePagePerms(
        mr, issue,
        permissions.CREATE_ISSUE,
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
        permissions.VIEW_INBOUND_MESSAGES)
    page_perms.EditIssue = ezt.boolean(permit_edit)

    prevent_restriction_removal = (
        mr.project.only_owners_remove_restrictions and
        not framework_bizobj.UserOwnsProject(
            mr.project, mr.auth.effective_ids))

    cmd_slots, default_slot_num = self.services.features.GetRecentCommands(
        mr.cnxn, mr.auth.user_id, mr.project_id)
    cmd_slot_views = [
        template_helpers.EZTItem(
            slot_num=slot_num, command=command, comment=comment)
        for slot_num, command, comment in cmd_slots]

    previous_locations = self.GetPreviousLocations(mr, issue)

    return {
        'issue_tab_mode': 'issueDetail',
        'issue': issue_view,
        'description': description_views,
        'comments': comment_views,
        'labels': issue.labels,
        'num_detail_rows': len(comment_views) + 4,
        'noisy': ezt.boolean(tracker_helpers.IsNoisy(
            len(comment_views), issue.star_count)),

        'cmnt_pagination': cmnt_pagination,
        'colspec': mr.col_spec,
        'searchtip': 'You can jump to any issue by number',
        'starred': ezt.boolean(starred),

        'pagegen': str(long(time.time() * 1000000)),
        'set_star_token': xsrf.GenerateToken(
            mr.auth.user_id, '/p/%s%s' % (  # Note: no .do suffix.
                mr.project_name, urls.ISSUE_SETSTAR_JSON)),

        'restrict_to_known': ezt.boolean(restrict_to_known),
        'prevent_restriction_removal': ezt.boolean(
            prevent_restriction_removal),

        'statuses_offer_merge': config.statuses_offer_merge,
        'page_perms': page_perms,
        'cmd_slots': cmd_slot_views,
        'default_slot_num': default_slot_num,
        'quick_edit_submit_url': tracker_helpers.FormatRelativeIssueURL(
            issue.project_name, urls.ISSUE_PEEK + '.do', id=issue.local_id),
        'previous_locations': previous_locations,
        # for template issue-meta-part shared by issuedetail servlet
        'user_hotlists': [],
        'user_issue_hotlists': [],
        'involved_users_issue_hotlists': [],
        'remaining_issue_hotlists': [],
        }

  def GetPreviousLocations(self, mr, issue):
    """Return a list of previous locations of the current issue."""
    previous_location_ids = self.services.issue.GetPreviousLocations(
        mr.cnxn, issue)
    previous_locations = []
    for old_pid, old_id in previous_location_ids:
      old_project = self.services.project.GetProject(mr.cnxn, old_pid)
      previous_locations.append(
          template_helpers.EZTItem(
              project_name=old_project.project_name, local_id=old_id))

    return previous_locations

  def _MakeIssueAndCommentViews(
      self, mr, issue, users_by_id, descriptions, comments, config,
      issue_reporters=None, comment_reporters=None):
    """Create view objects that help display parts of an issue.

    Args:
      mr: commonly used info parsed from the request.
      issue: issue PB for the currently viewed issue.
      users_by_id: dictionary of {user_id: UserView,...}.
      descriptions: list of IssueComment PBs for the issue report history.
      comments: list of IssueComment PBs on the current issue.
      issue_reporters: list of user IDs who have flagged the issue as spam.
      comment_reporters: map of comment ID to list of flagging user IDs.
      config: ProjectIssueConfig for the project that contains this issue.

    Returns:
      (issue_view, description_views, comment_views). One IssueView for
      the whole issue, a list of IssueCommentViews for the issue descriptions,
      and then a list of IssueCommentViews for each additional comment.
    """
    with self.profiler.Phase('getting related issues'):
      open_related, closed_related = (
          tracker_helpers.GetAllowedOpenAndClosedRelatedIssues(
              self.services, mr, issue))
      all_related_iids = list(issue.blocked_on_iids) + list(issue.blocking_iids)
      if issue.merged_into:
        all_related_iids.append(issue.merged_into)
      all_related = self.services.issue.GetIssues(mr.cnxn, all_related_iids)

    with self.profiler.Phase('making issue view'):
      issue_view = tracker_views.IssueView(
          issue, users_by_id, config,
          open_related=open_related, closed_related=closed_related,
          all_related={rel.issue_id: rel for rel in all_related})

    with self.profiler.Phase('autolinker object lookup'):
      all_ref_artifacts = self.services.autolink.GetAllReferencedArtifacts(
          mr, [c.content for c in descriptions + comments])

    with self.profiler.Phase('making comment views'):
      reporter_auth = monorailrequest.AuthData.FromUserID(
          mr.cnxn, descriptions[0].user_id, self.services)
      desc_views = [
          tracker_views.IssueCommentView(
              mr.project_name, d, users_by_id,
              self.services.autolink, all_ref_artifacts, mr,
              issue, effective_ids=reporter_auth.effective_ids)
          for d in descriptions]
      # TODO(jrobbins): get effective_ids of each comment author, but
      # that is too slow right now.
      comment_views = [
          tracker_views.IssueCommentView(
              mr.project_name, c, users_by_id, self.services.autolink,
              all_ref_artifacts, mr, issue)
          for c in comments]

    issue_view.flagged_spam = mr.auth.user_id in issue_reporters
    if comment_reporters is not None:
      for c in comment_views:
        c.flagged_spam = mr.auth.user_id in comment_reporters.get(c.id, [])

    return issue_view, desc_views, comment_views

  def ProcessFormData(self, mr, post_data):
    """Process the posted issue update form.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to, or None if response was already sent.
    """
    cmd = post_data.get('cmd', '')
    send_email = 'send_email' in post_data
    comment = post_data.get('comment', '')
    slot_used = int(post_data.get('slot_used', 1))
    page_generation_time = long(post_data['pagegen'])
    issue = self._GetIssue(mr)
    old_owner_id = tracker_bizobj.GetOwnerId(issue)
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    summary, status, owner_id, cc_ids, labels = commands.ParseQuickEditCommand(
        mr.cnxn, cmd, issue, config, mr.auth.user_id, self.services)
    component_ids = issue.component_ids  # TODO(jrobbins): component commands
    field_values = issue.field_values  # TODO(jrobbins): edit custom fields

    permit_edit = permissions.CanEditIssue(
        mr.auth.effective_ids, mr.perms, mr.project, issue)
    if not permit_edit:
      raise permissions.PermissionException(
          'User is not allowed to edit this issue')

    amendments, _ = self.services.issue.ApplyIssueComment(
        mr.cnxn, self.services, mr.auth.user_id,
        mr.project_id, mr.local_id, summary, status, owner_id, cc_ids,
        labels, field_values, component_ids, issue.blocked_on_iids,
        issue.blocking_iids, issue.dangling_blocked_on_refs,
        issue.dangling_blocking_refs, issue.merged_into,
        page_gen_ts=page_generation_time, comment=comment)
    self.services.project.UpdateRecentActivity(
        mr.cnxn, mr.project.project_id)

    if send_email:
      if amendments or comment.strip():
        cmnts = self.services.issue.GetCommentsForIssue(
            mr.cnxn, issue.issue_id)
        notify.PrepareAndSendIssueChangeNotification(
            issue.issue_id, mr.request.host, mr.auth.user_id, len(cmnts) - 1,
            send_email=send_email, old_owner_id=old_owner_id)

    # TODO(jrobbins): allow issue merge via quick-edit.

    self.services.features.StoreRecentCommand(
        mr.cnxn, mr.auth.user_id, mr.project_id, slot_used, cmd, comment)

    # TODO(jrobbins): this is very similar to a block of code in issuebulkedit.
    mr.can = int(post_data['can'])
    mr.query = post_data.get('q', '')
    mr.col_spec = post_data.get('colspec', '')
    mr.sort_spec = post_data.get('sort', '')
    mr.group_by_spec = post_data.get('groupby', '')
    mr.start = int(post_data['start'])
    mr.num = int(post_data['num'])
    preview_issue_ref_str = '%s:%d' % (issue.project_name, issue.local_id)
    return tracker_helpers.FormatIssueListURL(
        mr, config, preview=preview_issue_ref_str, updated=mr.local_id,
        ts=int(time.time()))


def PaginateComments(mr, issue, issuecomment_list, config):
  """Filter and paginate the IssueComment PBs for the given issue.

  Unlike most pagination, this one starts at the end of the whole
  list so it shows only the most recent comments.  The user can use
  the "Older" and "Newer" links to page through older comments.

  Args:
    mr: common info parsed from the HTTP request.
    issue: Issue PB for the issue being viewed.
    issuecomment_list: list of IssueComment PBs for the viewed issue,
        the zeroth item in this list is the initial issue description.
    config: ProjectIssueConfig for the project that contains this issue.

  Returns:
    A tuple (descriptions, visible_comments, pagination), where descriptions
    is a list of IssueComment PBs for the issue description history,
    visible_comments is a list of IssueComment PBs for the comments that
    should be displayed on the current pagination page, and pagination is a
    VirtualPagination object that keeps track of the Older and Newer links.
  """
  if not issuecomment_list:
    return [], [], None

  # TODO(lukasperaza): update first comments' rows to is_description=TRUE
  # so [issuecomment_list[0]] can be removed
  descriptions = (
      [issuecomment_list[0]] +
      [comment for comment in issuecomment_list[1:] if comment.is_description])
  comments = issuecomment_list[1:]
  allowed_comments = []
  restrictions = permissions.GetRestrictions(issue)
  granted_perms = tracker_bizobj.GetGrantedPerms(
      issue, mr.auth.effective_ids, config)
  for c in comments:
    can_delete = permissions.CanDelete(
        mr.auth.user_id, mr.auth.effective_ids, mr.perms, c.deleted_by,
        c.user_id, mr.project, restrictions, granted_perms=granted_perms)
    if can_delete or not c.deleted_by:
      allowed_comments.append(c)

  pagination_url = '%s?id=%d' % (urls.ISSUE_DETAIL, issue.local_id)
  pagination = paginate.VirtualPagination(
      mr, len(allowed_comments),
      framework_constants.DEFAULT_COMMENTS_PER_PAGE,
      list_page_url=pagination_url,
      count_up=False, start_param='cstart', num_param='cnum',
      max_num=settings.max_comments_per_page)
  if pagination.last == 1 and pagination.start == len(allowed_comments):
    pagination.visible = ezt.boolean(False)
  visible_comments = allowed_comments[
      pagination.last - 1:pagination.start]

  return descriptions, visible_comments, pagination
