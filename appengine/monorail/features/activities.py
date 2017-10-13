# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Code to support project and user activies pages."""

import logging
import time

from third_party import ezt

from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import sql
from framework import template_helpers
from framework import timestr
from project import project_views
from proto import tracker_pb2
from tracker import tracker_helpers
from tracker import tracker_views


UPDATES_PER_PAGE = 50
MAX_UPDATES_PER_PAGE = 200


class ActivityView(template_helpers.PBProxy):
  """EZT-friendly wrapper for Activities."""

  _TITLE_TEMPLATE = template_helpers.MonorailTemplate(
      framework_constants.TEMPLATE_PATH + 'features/activity-title.ezt',
      compress_whitespace=True, base_format=ezt.FORMAT_HTML)

  _BODY_TEMPLATE = template_helpers.MonorailTemplate(
      framework_constants.TEMPLATE_PATH + 'features/activity-body.ezt',
      compress_whitespace=True, base_format=ezt.FORMAT_HTML)

  def __init__(
      self, pb, services, mr, prefetched_issues, users_by_id,
      autolink=None, all_ref_artifacts=None, ending=None, highlight=None):
    """Constructs an ActivityView out of an Activity protocol buffer.

    Args:
      pb: an IssueComment or Activity protocol buffer.
      services: connections to backend services.
      mr: HTTP request info, used by the artifact autolink.
      prefetched_issues: dictionary of the issues for the comments being shown.
      users_by_id: dict {user_id: UserView} for all relevant users.
      autolink: Autolink instance.
      all_ref_artifacts: list of all artifacts in the activity stream.
      ending: ending type for activity titles, 'in_project' or 'by_user'
      highlight: what to highlight in the middle column on user updates pages
          i.e. 'project', 'user', or None
    """
    template_helpers.PBProxy.__init__(self, pb)

    activity_type = 'ProjectIssueUpdate'  # TODO(jrobbins): more types

    self.comment = None
    self.issue = None
    self.field_changed = None
    self.multiple_fields_changed = ezt.boolean(False)
    self.project = None
    self.user = None
    self.timestamp = time.time()  # Bogus value makes bad ones highly visible.

    if isinstance(pb, tracker_pb2.IssueComment):
      self.timestamp = pb.timestamp
      issue = prefetched_issues[pb.issue_id]
      if self.timestamp == issue.opened_timestamp:
        issue_change_id = None  # This comment is the description.
      else:
        issue_change_id = pb.timestamp  # instead of seq num.

      self.comment = tracker_views.IssueCommentView(
          mr.project_name, pb, users_by_id, autolink,
          all_ref_artifacts, mr, issue)

      # TODO(jrobbins): pass effective_ids of the commenter so that he/she
      # can be identified as a project member or not.
      # TODO(jrobbins): Prefetch all needed projects and configs just like the
      # way that we batch-prefetch issues.
      config = services.config.GetProjectConfig(mr.cnxn, issue.project_id)
      self.issue = tracker_views.IssueView(issue, users_by_id, config)
      self.user = self.comment.creator
      project = services.project.GetProject(mr.cnxn, issue.project_id)
      self.project_name = project.project_name
      self.project = project_views.ProjectView(project)

    else:
      logging.warn('unknown activity object %r', pb)

    nested_page_data = {
        'activity_type': activity_type,
        'issue_change_id': issue_change_id,
        'comment': self.comment,
        'issue': self.issue,
        'project': self.project,
        'user': self.user,
        'timestamp': self.timestamp,
        'ending_type': ending,
        }

    self.escaped_title = self._TITLE_TEMPLATE.GetResponse(
        nested_page_data).strip()
    self.escaped_body = self._BODY_TEMPLATE.GetResponse(
        nested_page_data).strip()

    if autolink is not None and all_ref_artifacts is not None:
      # TODO(jrobbins): actually parse the comment text.  Actually render runs.
      runs = autolink.MarkupAutolinks(
          mr, [template_helpers.TextRun(self.escaped_body)], all_ref_artifacts)
      self.escaped_body = ''.join(run.content for run in runs)

    self.date_bucket, self.date_relative = timestr.GetHumanScaleDate(
        self.timestamp)
    time_tuple = time.localtime(self.timestamp)
    self.date_tooltip = time.asctime(time_tuple)

    # We always highlight the user for starring activities
    if activity_type.startswith('UserStar'):
      self.highlight = 'user'
    else:
      self.highlight = highlight


def GatherUpdatesData(
    services, mr, project_ids=None, user_ids=None, ending=None,
    updates_page_url=None, autolink=None, highlight=None):
  """Gathers and returns updates data.

  Args:
    services: Connections to backend services.
    mr: HTTP request info, used by the artifact autolink.
    project_ids: List of project IDs we want updates for.
    user_ids: List of user IDs we want updates for.
    ending: Ending type for activity titles, 'in_project' or 'by_user'.
    updates_page_url: The URL that will be used to create pagination links from.
    autolink: Autolink instance.
    highlight: What to highlight in the middle column on user updates pages
        i.e. 'project', 'user', or None.
  """
  ascending = bool(mr.after)

  # num should be non-negative number
  num = mr.GetPositiveIntParam('num', UPDATES_PER_PAGE)
  num = min(num, MAX_UPDATES_PER_PAGE)

  updates_data = {
      'no_stars': None,
      'no_activities': None,
      'pagination': None,
      'updates_data': None,
      'ending_type': ending,
      }

  if not user_ids and not project_ids:
    updates_data['no_stars'] = ezt.boolean(True)
    return updates_data

  with mr.profiler.Phase('get activities'):
    # TODO(jrobbins): make this into a persist method.
    # TODO(jrobbins): this really needs permission checking in SQL, which will
    # be slow.
    where_conds = [('Issue.id = Comment.issue_id', [])]
    if project_ids is not None:
      cond_str = 'Comment.project_id IN (%s)' % sql.PlaceHolders(project_ids)
      where_conds.append((cond_str, project_ids))
    if user_ids is not None:
      cond_str = 'Comment.commenter_id IN (%s)' % sql.PlaceHolders(user_ids)
      where_conds.append((cond_str, user_ids))

    if project_ids:
      use_clause = 'USE INDEX (project_id) USE INDEX FOR ORDER BY (project_id)'
    elif user_ids:
      use_clause = (
          'USE INDEX (commenter_id) USE INDEX FOR ORDER BY (commenter_id)')
    else:
      use_clause = ''

    if mr.before:
      where_conds.append(('created < %s', [mr.before]))
    if mr.after:
      where_conds.append(('created > %s', [mr.after]))
    if ascending:
      order_by = [('created', [])]
    else:
      order_by = [('created DESC', [])]

    comments = services.issue.GetComments(
        mr.cnxn, joins=[('Issue', [])], deleted_by=None, where=where_conds,
        use_clause=use_clause, order_by=order_by, limit=num + 1)

    # TODO(jrobbins): it would be better if we could just get the dict directly.
    prefetched_issues_list = services.issue.GetIssues(
        mr.cnxn, {c.issue_id for c in comments})
    prefetched_issues = {
        issue.issue_id: issue for issue in prefetched_issues_list}
    needed_project_ids = {issue.project_id for issue in prefetched_issues_list}
    prefetched_projects = services.project.GetProjects(
        mr.cnxn, needed_project_ids)
    prefetched_configs = services.config.GetProjectConfigs(
        mr.cnxn, needed_project_ids)
    viewable_issues_list = tracker_helpers.FilterOutNonViewableIssues(
        mr.auth.effective_ids, mr.auth.user_pb, prefetched_projects,
        prefetched_configs, prefetched_issues_list)
    viewable_iids = {issue.issue_id for issue in viewable_issues_list}

    # Filter the comments based on permission to view the issue.
    # TODO(jrobbins): push permission checking in the query so that pagination
    # pages never become underfilled, or use backends to shard.
    # TODO(jrobbins): come back to this when I implement private comments.
    comments = [
        c for c in comments if c.issue_id in viewable_iids]

    if ascending:
      comments.reverse()

  amendment_user_ids = []
  for comment in comments:
    for amendment in comment.amendments:
      amendment_user_ids.extend(amendment.added_user_ids)
      amendment_user_ids.extend(amendment.removed_user_ids)

  users_by_id = framework_views.MakeAllUserViews(
      mr.cnxn, services.user, [c.user_id for c in comments],
      amendment_user_ids)
  framework_views.RevealAllEmailsToMembers(mr, users_by_id)

  num_results_returned = len(comments)
  displayed_activities = comments[:UPDATES_PER_PAGE]

  if not num_results_returned:
    updates_data['no_activities'] = ezt.boolean(True)
    return updates_data

  # Get all referenced artifacts first
  all_ref_artifacts = None
  if autolink is not None:
    content_list = []
    for activity in comments:
      content_list.append(activity.content)

    all_ref_artifacts = autolink.GetAllReferencedArtifacts(
        mr, content_list)

  # Now process content and gather activities
  today = []
  yesterday = []
  pastweek = []
  pastmonth = []
  thisyear = []
  older = []

  with mr.profiler.Phase('rendering activities'):
    for activity in displayed_activities:
      entry = ActivityView(
          activity, services, mr, prefetched_issues, users_by_id,
          autolink=autolink, all_ref_artifacts=all_ref_artifacts, ending=ending,
          highlight=highlight)

      if entry.date_bucket == 'Today':
        today.append(entry)
      elif entry.date_bucket == 'Yesterday':
        yesterday.append(entry)
      elif entry.date_bucket == 'Last 7 days':
        pastweek.append(entry)
      elif entry.date_bucket == 'Last 30 days':
        pastmonth.append(entry)
      elif entry.date_bucket == 'Earlier this year':
        thisyear.append(entry)
      elif entry.date_bucket == 'Before this year':
        older.append(entry)

  new_after = None
  new_before = None
  if displayed_activities:
    new_after = displayed_activities[0].timestamp
    new_before = displayed_activities[-1].timestamp

  prev_url = None
  next_url = None
  if updates_page_url:
    list_servlet_rel_url = updates_page_url.split('/')[-1]
    if displayed_activities and (mr.before or mr.after):
      prev_url = framework_helpers.FormatURL(
          mr, list_servlet_rel_url, after=new_after)
    if mr.after or len(comments) > UPDATES_PER_PAGE:
      next_url = framework_helpers.FormatURL(
          mr, list_servlet_rel_url, before=new_before)

  if prev_url or next_url:
    pagination = template_helpers.EZTItem(
        start=None, last=None, prev_url=prev_url, next_url=next_url,
        reload_url=None, visible=ezt.boolean(True), total_count=None)
  else:
    pagination = None

  updates_data.update({
      'no_activities': ezt.boolean(False),
      'pagination': pagination,
      'updates_data': template_helpers.EZTItem(
          today=today, yesterday=yesterday, pastweek=pastweek,
          pastmonth=pastmonth, thisyear=thisyear, older=older),
      })

  return updates_data
