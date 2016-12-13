# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the hotlistissues page and related forms."""

import logging
from third_party import ezt

import settings
import time

from features import features_constants
from features import hotlist_helpers
from framework import servlet
from framework import sorting
from framework import permissions
from framework import framework_helpers
from framework import paginate
from framework import framework_constants
from framework import framework_views
from framework import grid_view_helpers
from framework import template_helpers
from framework import urls
from framework import xsrf
from services import features_svc
from tracker import tracker_bizobj


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

    if mr.mode == 'grid':
      page_data = self.GetGridViewData(mr)
    else:
      page_data = self.GetTableViewData(mr)

    with self.profiler.Phase('making page perms'):
      owner_permissions = permissions.CanAdministerHotlist(
          mr.auth.effective_ids, mr.hotlist)
      editor_permissions = permissions.CanEditHotlist(
          mr.auth.effective_ids, mr.hotlist)
      # TODO(jojwang): each issue should have an individual
      # SetStar status based on its project
      page_perms = template_helpers.EZTItem(
          EditIssue=None, SetStar=mr.auth.user_id)

    allow_rerank = (not mr.group_by_spec and mr.sort_spec.startswith(
        'rank') and (owner_permissions or editor_permissions))

    # Note: The HotlistView is created and returned in servlet.py
    page_data.update({'owner_permissions': owner_permissions,
                      'editor_permissions': editor_permissions,
                      'issue_tab_mode': 'issueList',
                      'grid_mode': ezt.boolean(mr.mode == 'grid'),
                      'set_star_token': xsrf.GenerateToken(
                          mr.auth.user_id, '/u/%s/hotlsits/%d%s.do' % (
                              mr.viewed_username, mr.hotlist_id,
                              urls.ISSUE_SETSTAR_JSON)),
                      'page_perms': page_perms,
                      'colspec': mr.col_spec,
                      'allow_rerank': ezt.boolean(allow_rerank),
                      'csv_link': '', # TODO(jojwang): fill in when
                      # CSV for hotlists is complete
                      'is_hotlist': ezt.boolean(True)})
    return page_data
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

  def GetTableViewData(self, mr):
    """EZT template values to render a Table View of issues.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dictionary of page data for rendering of the Table View.
    """
    table_data, table_related_dict = hotlist_helpers.CreateHotlistTableData(
        mr, mr.hotlist.iid_rank_pairs, self.profiler, self.services)
    columns = mr.col_spec.split()
    ordered_columns = [template_helpers.EZTItem(col_index=i, name=col)
                       for i, col in enumerate(columns)]
    table_view_data = {
        'table_data': table_data,
        'panels': [template_helpers.EZTItem(ordered_columns=ordered_columns)],
        'cursor': mr.cursor or mr.preview,
        'preview': mr.preview,
        'default_colspec': features_constants.DEFAULT_COL_SPEC,
        'default_results_per_page': 10,
        'csv_link': '', # TODO(jojwang): fill in when done w/ hotlists CSV
        'preview_on_hover': (
            settings.enable_quick_edit and mr.auth.user_pb.preview_on_hover),
        'remove_issues_token': xsrf.GenerateToken(
            mr.auth.user_id,
            '/u/%s/hotlists/%s.do' % (mr.auth.user_id, mr.hotlist_id))
        }
    table_view_data.update(table_related_dict)

    return table_view_data

  def ProcessFormData(self, mr, post_data):
    sorting.InvalidateArtValuesKeys(
        mr.cnxn,
        [hotlist_issue.issue_id for hotlist_issue
         in mr.hotlist.iid_rank_pairs])

    if post_data.get('remove') == 'true':
      project_and_local_ids = post_data.get('remove_local_ids')
    else:
      project_and_local_ids = post_data.get('add_local_ids')

    issue_refs_tuples = [(pair.split(':')[0].strip(),
                          int(pair.split(':')[1].strip()))
                         for pair in project_and_local_ids.split(',')]
    project_names = {project_name for (project_name, _) in issue_refs_tuples}
    projects_dict = self.services.project.GetProjectsByName(
        mr.cnxn, project_names)

    selected_iids = self.services.issue.ResolveIssueRefs(
        mr.cnxn, projects_dict, mr.project_name, issue_refs_tuples)

    if post_data.get('remove') == 'true':
      self.services.features.UpdateHotlistIssues(
          mr.cnxn, mr.hotlist_id, selected_iids, [])
    else:
      iid_rank_pairs_sorted = sorted(
          mr.hotlist.iid_rank_pairs, key=lambda pair: pair.rank)
      rank_base = iid_rank_pairs_sorted[-1].rank + 10
      added_pairs =  [(issue_id, rank_base + multiplier*10)
                     for (multiplier, issue_id) in enumerate(selected_iids)]
      self.services.features.UpdateHotlistIssues(
          mr.cnxn, mr.hotlist_id, [], added_pairs)

    return framework_helpers.FormatAbsoluteURL(
          mr, '/u/%s/hotlists/%s' % (mr.auth.user_id, mr.hotlist_id),
          saved=1, ts=int(time.time()), include_project=False)

  def GetGridViewData(self, mr):
    """EZT template values to render a Table View of issues.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dictionary of page data for rendering of the Table View.
    """
    mr.ComputeColSpec(mr.hotlist)
    starred_iid_set = set(self.services.issue_star.LookupStarredItemIDs(
        mr.cnxn, mr.auth.user_id))
    issues_list = self.services.issue.GetIssues(
        mr.cnxn,
        [hotlist_issue.issue_id for hotlist_issue
         in mr.hotlist.iid_rank_pairs])
    allowed_issues = hotlist_helpers.FilterIssues(
        mr, issues_list, self.services)
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        tracker_bizobj.UsersInvolvedInIssues(allowed_issues or []))
    hotlist_issues_project_ids = hotlist_helpers.GetAllProjectsOfIssues(
        [issue for issue in issues_list])
    config_list = hotlist_helpers.GetAllConfigsOfProjects(
        mr.cnxn, hotlist_issues_project_ids, self.services)
    harmonized_config = tracker_bizobj.HarmonizeConfigs(config_list)
    limit = settings.max_issues_in_grid
    grid_limited = len(allowed_issues) > limit
    lower_cols = mr.col_spec.lower().split()
    grid_x = (mr.x or harmonized_config.default_x_attr or '--').lower()
    grid_y = (mr.y or harmonized_config.default_y_attr or '--').lower()
    lower_cols.append(grid_x)
    lower_cols.append(grid_y)
    related_iids = set()
    for issue in allowed_issues:
      if 'blockedon' in lower_cols:
        related_iids.update(issue.blocked_on_iids)
      if 'blocking' in lower_cols:
        related_iids.update(issue.blocking_iids)
      if 'mergedinto' in lower_cols:
        related_iids.add(issue.merged_into)
    related_issues_list = self.services.issue.GetIssues(
        mr.cnxn, list(related_iids))
    related_issues = {issue.issue_id: issue for issue in related_issues_list}

    grid_view_data = grid_view_helpers.GetGridViewData(
        mr, allowed_issues, harmonized_config,
        users_by_id, starred_iid_set, grid_limited, related_issues)

    grid_view_data.update({'pagination': paginate.ArtifactPagination(
          mr, allowed_issues, features_constants.DEFAULT_RESULTS_PER_PAGE,
          total_count=len(allowed_issues),
          list_page_url=urls.HOTLIST_ISSUES)})

    return grid_view_data
