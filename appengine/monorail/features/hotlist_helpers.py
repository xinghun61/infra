# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions and classes used by the hotlist pages."""

from features import features_constants
from framework import framework_views
from framework import sorting
from framework import table_view_helpers
from framework import paginate
from framework import permissions
from framework import urls
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers
from tracker import tablecell


def CreateHotlistTableData(mr, hotlist_issues, profiler, services):
  """Creates the table data for the hotlistissues table."""
  with profiler.Phase('getting stars'):
    starred_iid_set = set(services.issue_star.LookupStarredItemIDs(
        mr.cnxn, mr.auth.user_id))

  with profiler.Phase('computer col_spec'):
    mr.ComputeColSpec(mr.hotlist)

  issues_list = services.issue.GetIssues(
        mr.cnxn,
        [hotlist_issue.issue_id for hotlist_issue in hotlist_issues])
  with profiler.Phase('Getting config'):
    hotlist_issues_project_ids = GetAllProjectsOfIssues(
        [issue for issue in issues_list])
    is_cross_project = len(hotlist_issues_project_ids) > 1
    config_list = GetAllConfigsOfProjects(
        mr.cnxn, hotlist_issues_project_ids, services)
    harmonized_config = tracker_bizobj.HarmonizeConfigs(config_list)

  with profiler.Phase('Checking issue permissions and getting ranks'):
    allowed_issues = FilterIssues(mr, issues_list, services)
    sorted_ranks = sorted(
        [hotlist_issue.rank for hotlist_issue in hotlist_issues])
    friendly_ranks = {
        rank: friendly for friendly, rank in enumerate(sorted_ranks, 1)}
    issue_ranks = {
        hotlist_issue.issue_id: friendly_ranks[hotlist_issue.rank]
        for hotlist_issue in hotlist_issues}

  with profiler.Phase('Making user views'):
    issues_users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, services.user,
        tracker_bizobj.UsersInvolvedInIssues(allowed_issues or []))

  with profiler.Phase('Sorting issues'):
    sortable_fields = tracker_helpers.SORTABLE_FIELDS.copy()
    sortable_fields.update(
        {'rank': lambda issue: issue_ranks[issue.issue_id]})
    if not mr.sort_spec:
      mr.sort_spec = '-rank'
    sorted_issues = sorting.SortArtifacts(
        mr, allowed_issues, harmonized_config, sortable_fields,
        username_cols=tracker_constants.USERNAME_COLS,
        users_by_id=issues_users_by_id, tie_breakers=['rank', 'id'])

  with profiler.Phase("getting related issues"):
    related_iids = set()
    # TODO(jojwang): if in grid_mode
    # results_needing_related = allowed_issues or []
    results_needing_related = sorted_issues
    lower_cols = mr.col_spec.lower().split()
    for issue in results_needing_related:
      if 'blockedon' in lower_cols:
        related_iids.update(issue.blocked_on_iids)
      if 'blocking' in lower_cols:
        related_iids.update(issue.blocking_iids)
      if 'mergedinto' in lower_cols:
        related_iids.add(issue.merged_into)
    related_issues_list = services.issue.GetIssues(
        mr.cnxn, list(related_iids))
    related_issues = {issue.issue_id: issue for issue in related_issues_list}

  with profiler.Phase('building table'):
    context_for_all_issues = {issue.issue_id: {
          'issue_rank': issue_ranks[issue.issue_id]}
                                for issue in sorted_issues}
    table_data = _MakeTableData(
        sorted_issues, starred_iid_set, mr.col_spec.lower().split(),
        mr.group_by_spec.lower().split(), issues_users_by_id,
        tablecell.CELL_FACTORIES,
        related_issues, harmonized_config, context_for_all_issues)

  column_values = table_view_helpers.ExtractUniqueValues(
      mr.col_spec.lower().split(), sorted_issues, issues_users_by_id,
      harmonized_config)
  unshown_columns = table_view_helpers.ComputeUnshownColumns(
      sorted_issues, mr.col_spec.split(), harmonized_config,
      features_constants.OTHER_BUILT_IN_COLS)
  pagination = paginate.ArtifactPagination(
        mr, [issue.issue_id for issue in sorted_issues],
        features_constants.DEFAULT_RESULTS_PER_PAGE,
        urls.HOTLIST_ISSUES, len(sorted_issues))

  table_related_dict = {
      'column_values': column_values, 'unshown_columns': unshown_columns,
      'pagination': pagination, 'is_cross_project': is_cross_project }
  return table_data, table_related_dict


def _MakeTableData(issues, starred_iid_set, lower_columns,
                   lower_group_by, users_by_id, cell_factories,
                   related_issues, config, context_for_all_issues):
  """Returns data from MakeTableData after adding additional information."""
  table_data = table_view_helpers.MakeTableData(
      issues, starred_iid_set, lower_columns, lower_group_by,
      users_by_id, cell_factories, lambda issue: issue.issue_id,
      related_issues, config, context_for_all_issues)

  for row, art in zip(table_data, issues):
    row.issue_id = art.issue_id
    row.local_id = art.local_id
    row.project_name = art.project_name
    row.issue_ref = '%s:%d' % (art.project_name, art.local_id)
    row.issue_url = tracker_helpers.FormatRelativeIssueURL(
        art.project_name, urls.ISSUE_DETAIL, id=art.local_id)

  return table_data


def FilterIssues(mr, issues, services):
  """Return a list of issues that the user is allowed to view."""
  allowed_issues = []
  project_ids = GetAllProjectsOfIssues(issues)
  issue_projects = services.project.GetProjects(mr.cnxn, project_ids)
  configs_by_project_id = services.config.GetProjectConfigs(
      mr.cnxn, project_ids)
  perms_by_project_id = {
      pid: permissions.GetPermissions(
          mr.auth.user_pb, mr.auth.effective_ids, p)
      for pid, p in issue_projects.items()}
  for issue in issues:
    issue_project = issue_projects[issue.project_id]
    config = configs_by_project_id[issue.project_id]
    perms = perms_by_project_id[issue.project_id]
    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, mr.auth.effective_ids, config)
    permit_view = permissions.CanViewIssue(
        mr.auth.effective_ids, perms,
        issue_project, issue, granted_perms=granted_perms)
    if permit_view:
      allowed_issues.append(issue)

  return allowed_issues


def GetAllConfigsOfProjects(cnxn, project_ids, services):
  """Returns a list of configs for the given list of projects."""
  config_dict = services.config.GetProjectConfigs(cnxn, project_ids)
  config_list = [config_dict[project_id] for project_id in project_ids]
  return config_list


def GetAllProjectsOfIssues(issues):
  """Returns a list of all projects that the given issues are in."""
  project_ids = set()
  for issue in issues:
    project_ids.add(issue.project_id)
  return project_ids


def MembersWithoutGivenIDs(hotlist, exclude_ids):
  """Return three lists of member user IDs, with exclude_ids not in them."""
  owner_ids = [user_id for user_id in hotlist.owner_ids
               if user_id not in exclude_ids]
  editor_ids = [user_id for user_id in hotlist.editor_ids
                   if user_id not in exclude_ids]
  follower_ids = [user_id for user_id in hotlist.follower_ids
                     if user_id not in exclude_ids]

  return owner_ids, editor_ids, follower_ids


def MembersWithGivenIDs(hotlist, new_member_ids, role):
  """Return three lists of member IDs with the new IDs in the right one.

  Args:
    hotlist: Hotlist PB for the project to get current members from.
    new_member_ids: set of user IDs for members being added.
    role: string name of the role that new_member_ids should be granted.

  Returns:
    Three lists of member IDs with new_member_ids added to the appropriate
    list and removed from any other role.

  Raises:
    ValueError: if the role is not one of owner, committer, or contributor.
  """
  owner_ids, editor_ids, follower_ids = MembersWithoutGivenIDs(
      hotlist, new_member_ids)

  if role == 'owner':
    owner_ids.extend(new_member_ids)
  elif role == 'editor':
    editor_ids.extend(new_member_ids)
  elif role == 'follower':
    follower_ids.extend(new_member_ids)
  else:
    raise ValueError()

  return owner_ids, editor_ids, follower_ids
