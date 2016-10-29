
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the hotlistissues page and related forms."""

from third_party import ezt

import settings

from features import hotlist_views
from features import features_bizobj
from features import features_constants
from framework import servlet
from framework import sorting
from framework import permissions
from framework import paginate
from framework import framework_views
from framework import framework_helpers
from framework import table_view_helpers
from framework import template_helpers
from framework import urls
from framework import xsrf
from services import features_svc
from tracker import tablecell
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers


class HotlistIssues(servlet.Servlet):
  """HotlistIssues is a page that shows the issues of one hotlist."""

  _PAGE_TEMPLATE = 'features/hotlist-issues-page.ezt'

  def AssertBasePermission(self, mr):
    """Check that the user has permission to even visit this page."""
    super(HotlistIssues, self).AssertBasePermission(mr)
    try:
      hotlist = self._GetHotlist(mr)
    except features_svc.NoSuchHotlistException:
      return
    permit_view = permissions.CanViewHotlist(mr.auth.effective_ids, hotlist)
    if not permit_view:
      raise permissions.PermissionException(
        'User is not allowed to view this hotlist')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly usef info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    with self.profiler.Phase('getting hotlist'):
      if mr.hotlist_id is None:
        self.abort(404, 'no hotlist specified')

    with self.profiler.Phase('getting stars'):
      starred_iid_set = set(self.services.issue_star.LookupStarredItemIDs(
          mr.cnxn, mr.auth.user_id))

    with self.profiler.Phase('computing col_spec'):
      mr.ComputeColSpec(mr.hotlist)
      # NOTE: ComputeColSpec takes config but only calls config.default_col_spec
      # hotlists are not configs but have a default_col_spec

    related_issues = {}
    # TODO(jojwang): implement this, necessary for columns of
    # BlockedOn/Blocking/MergedInto. {global issue_id: issue pb}

    hotlist_issues = mr.hotlist.iid_rank_pairs
    # list of HotlistIssues, not Issues

    issues_list = self.services.issue.GetIssues(
        mr.cnxn,
        [hotlist_issue.issue_id for hotlist_issue in hotlist_issues])
    with self.profiler.Phase('Getting config'):
      hotlist_issues_project_ids = self.GetAllProjectsOfIssues(
          [issue for issue in issues_list])
      is_cross_project = len(hotlist_issues_project_ids) > 1
      config_list = self.GetAllConfigsOfProjects(
          mr.cnxn, hotlist_issues_project_ids)
      harmonized_config = tracker_bizobj.HarmonizeConfigs(config_list)

    with self.profiler.Phase('Checking issue permissions and getting ranks'):
      allowed_issues = self._FilterIssues(mr, issues_list)
      issue_ranks = {
          hotlist_issue.issue_id: hotlist_issue.rank
          for hotlist_issue in hotlist_issues}

    with self.profiler.Phase('Making user views'):
      issues_users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user,
          tracker_bizobj.UsersInvolvedInIssues(allowed_issues or []))

    with self.profiler.Phase('Sorting issues'):
      sortable_fields = tracker_helpers.SORTABLE_FIELDS.copy()
      sortable_fields.update(
          {'rank': lambda issue: issue_ranks[issue.issue_id]})
      sorted_issues = sorting.SortArtifacts(
          mr, allowed_issues, harmonized_config, sortable_fields,
          username_cols=tracker_constants.USERNAME_COLS,
          users_by_id=issues_users_by_id, tie_breakers=['rank', 'id'])

    pagination = paginate.ArtifactPagination(
        mr, [issue.issue_id for issue in sorted_issues],
        features_constants.DEFAULT_RESULTS_PER_PAGE,
        urls.HOTLIST_ISSUES, len(sorted_issues))

    with self.profiler.Phase('building table'):
      context_for_all_issues = {issue.issue_id: {
          'issue_rank': issue_ranks[issue.issue_id],}
                                for issue in sorted_issues}
      page_data = self.GetTableViewData(
          mr, sorted_issues, harmonized_config,
          issues_users_by_id, starred_iid_set, related_issues,
          context_for_all_issues)

    with self.profiler.Phase('making page perms'):
      owner_permissions = permissions.CanAdministerHotlist(
          mr.auth.effective_ids, mr.hotlist)
      editor_permissions = permissions.CanEditHotlist(
          mr.auth.effective_ids, mr.hotlist)
      page_perms = template_helpers.EZTItem(EditIssue=None)

    # Note: The HotlistView is created and returned in servlet.py
    page_data.update({'owner_permissions': owner_permissions,
                      'editor_permissions': editor_permissions,
                      'is_cross_project': is_cross_project,
                      'pagination': pagination,
                      'issue_tab_mode': 'issueList',
                      'grid_mode': ezt.boolean(False),
                      'set_star_token': xsrf.GenerateToken(
                          mr.auth.user_id, '/u/%s/hotlsits/%d%s.do' % (
                              mr.viewed_username, mr.hotlist_id,
                              urls.ISSUE_SETSTAR_JSON)),
                      'page_perms': page_perms,
                      'colspec': mr.col_spec,})
    return page_data
  # TODO(jojwang): implement grid_mode and update page_date; grid_mode will not
  # always be False
  # TODO(jojwang): implement peek issue on hover, implement starring issues

  def _GetHotlist(self, mr):
    """Retrieve the current hotlist."""
    if mr.hotlist_id is None:
      return None
    try:
      hotlist = self.services.features.GetHotlist( mr.cnxn, mr.hotlist_id)
    except features_svc.NoSuchHotlistException:
      self.abort(404, 'hotlist not found')
    return hotlist

  def GetAllProjectsOfIssues(self, issues):
    project_ids = set()
    for issue in issues:
      project_ids.add(issue.project_id)
    return project_ids

  def GetAllConfigsOfProjects(self, cnxn, project_ids):
    config_dict = self.services.config.GetProjectConfigs(cnxn, project_ids)
    config_list = [config_dict[project_id] for project_id in project_ids]
    return config_list

  def _FilterIssues(self, mr, issues):
    """Return a list of issues that the user is allowed to view."""
    allowed_issues = []
    project_ids = self.GetAllProjectsOfIssues(issues)
    issue_projects = self.services.project.GetProjects(mr.cnxn, project_ids)
    configs_by_project_id = self.services.config.GetProjectConfigs(
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

  def GetCellFactories(self):
    return tablecell.CELL_FACTORIES

  def GetTableViewData(
      self, mr, issues, config, users_by_id,
      starred_iid_set, related_issues, context_for_all_issues):
    """EZT template values to render a Table View of issues.

    Args:
      mr: commonly used info parsed from the request.
      issues: list of Issue PBs to be displayed
      config: The harmonized config for all ProjectIssueConfig PBs that have
        issues in this hotlist
      users_by_id: A dictionary of {user_id: UserView} for all the users
        involved in the issues.
      starred_iid_set: Set of issues that the user has starred
        related_issues: dict {issue_id: issue} of pre-fetched related issues.
      context_for_all_issues: A dictionary of dictionaries containing values
        passed in to cell factory functions to create TableCells. Dictionary
        form: {issue_id: {'rank': issue_rank, 'issue_info': info_value, ..},
        issue_id: {'rank': issue_rank}, ..}

    Returns:
      Dictionary of page data for rendering of the Table View.
    """
    columns = mr.col_spec.split()
    ordered_columns = [template_helpers.EZTItem(col_index=i, name=col)
                       for i, col in enumerate(columns)]
    lower_columns = mr.col_spec.lower().split()
    lower_group_by = mr.group_by_spec.lower().split()
    table_data = _MakeTableData(
        issues, starred_iid_set, lower_columns, lower_group_by, users_by_id,
        self.GetCellFactories(), related_issues, config, context_for_all_issues)
    column_values = table_view_helpers.ExtractUniqueValues(
        lower_columns, issues, users_by_id, config)
    unshown_columns = table_view_helpers.ComputeUnshownColumns(
        issues, columns, config, features_constants.OTHER_BUILT_IN_COLS)
    table_view_data = {
        'table_data': table_data,
        'column_values': column_values,
        'panels': [template_helpers.EZTItem(ordered_columns=ordered_columns)],
        'cursor': mr.cursor or mr.preview,
        'preview': mr.preview,
        'default_colspec': features_constants.DEFAULT_COL_SPEC,
        'default_results_per_page': 10,
        'csv_link': framework_helpers.FormatURL(mr, 'csv'),
        'preview_on_hover': (
            settings.enable_quick_edit and mr.auth.user_pb.preview_on_hover),
        'unshown_columns': unshown_columns,
        }

    return table_view_data


def _MakeTableData(issues, starred_iid_set, lower_columns,
                   lower_group_by, users_by_id, cell_factories,
                   related_issues, config, context_for_all_issues):
  table_data = table_view_helpers.MakeTableData(
      issues, starred_iid_set, lower_columns, lower_group_by,
      users_by_id, cell_factories, lambda issue: issue.issue_id,
      related_issues, config, context_for_all_issues)

  for row, art in zip(table_data, issues):
    row.local_id = art.local_id
    row.project_name = art.project_name
    row.issue_ref = '%s:%d' % (art.project_name, art.local_id)
    row.issue_url = tracker_helpers.FormatRelativeIssueURL(
        art.project_name, urls.ISSUE_DETAIL, id=art.local_id)

  return table_data
