# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the hotlistissues page and related forms."""

import logging
from third_party import ezt

import settings
import time
import re

from features import features_bizobj
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
from framework import timestr
from framework import urls
from framework import xsrf
from services import features_svc
from tracker import tracker_bizobj

_INITIAL_ADD_ISSUES_MESSAGE = 'projectname:localID, projectname:localID, etc.'
_MSG_INVALID_ISSUES_INPUT = (
    'Please follow project_name:issue_id, project_name:issue_id..')
_MSG_ISSUES_NOT_FOUND = 'One or more of your issues were not found.'

class HotlistIssues(servlet.Servlet):
  """HotlistIssues is a page that shows the issues of one hotlist."""

  _PAGE_TEMPLATE = 'features/hotlist-issues-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.HOTLIST_TAB_ISSUES

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
    with mr.profiler.Phase('getting hotlist'):
      if mr.hotlist_id is None:
        self.abort(404, 'no hotlist specified')
    if mr.auth.user_id:
      self.services.user.AddVisitedHotlist(
          mr.cnxn, mr.auth.user_id, mr.hotlist_id)

    if mr.mode == 'grid':
      page_data = self.GetGridViewData(mr)
    else:
      page_data = self.GetTableViewData(mr)

    with mr.profiler.Phase('making page perms'):
      owner_permissions = permissions.CanAdministerHotlist(
          mr.auth.effective_ids, mr.hotlist)
      editor_permissions = permissions.CanEditHotlist(
          mr.auth.effective_ids, mr.hotlist)
      # TODO(jojwang): each issue should have an individual
      # SetStar status based on its project to indicate whether or not
      # the star icon should be shown to the user.
      page_perms = template_helpers.EZTItem(
          EditIssue=None, SetStar=mr.auth.user_id)

    allow_rerank = (not mr.group_by_spec and mr.sort_spec.startswith(
        'rank') and (owner_permissions or editor_permissions))

    # Note: The HotlistView is created and returned in servlet.py
    page_data.update({'owner_permissions': ezt.boolean(owner_permissions),
                      'editor_permissions': ezt.boolean(editor_permissions),
                      'issue_tab_mode': 'issueList',
                      'grid_mode': ezt.boolean(mr.mode == 'grid'),
                      'page_perms': page_perms,
                      'colspec': mr.col_spec,
                      'allow_rerank': ezt.boolean(allow_rerank),
                      'csv_link': framework_helpers.FormatURL(
                          mr, '%d/csv' % mr.hotlist_id, num=100),
                      'is_hotlist': ezt.boolean(True),
                      'col_spec': mr.col_spec.lower(),
                      'viewing_user_page': ezt.boolean(True),
                      'set_star_token': '', # needed for shared ezt templates.
                      # for update-issues-hotlists-dialog in
                      # issue-list-controls.
                      'user_issue_hotlists': [],
                      'user_remaining_hotlists': []
                      })
    return page_data
  # TODO(jojwang): implement peek issue on hover, implement starring issues

  def _IsHotlistStarred(self, cnxn, logged_in_user_id, hotlist_id):
    """Return whether the logged in user starred the viewed hotlist."""
    if logged_in_user_id:
      return self.services.hotlist_star.IsItemStarredBy(
          cnxn, hotlist_id, logged_in_user_id)
    return False

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
        mr, mr.hotlist.items, self.services)
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
        'preview_on_hover': (
            settings.enable_quick_edit and mr.auth.user_pb.preview_on_hover),
        # token must be generated using url with userid to accommodate
        # multiple urls for one hotlist
        'edit_hotlist_token': xsrf.GenerateToken(
            mr.auth.user_id,
            hotlist_helpers.GetURLOfHotlist(
                mr.cnxn, mr.hotlist, self.services.user,
                url_for_token=True) + '.do'),
        'add_local_ids': '',
        'placeholder': _INITIAL_ADD_ISSUES_MESSAGE,
        'add_issues_selected': ezt.boolean(False),
        'col_spec': ''
        }
    table_view_data.update(table_related_dict)

    return table_view_data

  def ProcessFormData(self, mr, post_data):
    if post_data.get('deletestate') == 'true':
      hotlist_helpers.RemoveHotlist(mr.cnxn, mr.hotlist_id, self.services)
      return framework_helpers.FormatAbsoluteURL(
          mr, '/u/%s/hotlists' % mr.auth.email,
          saved=1, ts=int(time.time()), include_project=False)

    hotlist_view_url = hotlist_helpers.GetURLOfHotlist(
        mr.cnxn, mr.hotlist, self.services.user)
    current_col_spec = post_data.get('current_col_spec')
    default_url = framework_helpers.FormatAbsoluteURL(
        mr, hotlist_view_url,
        include_project=False, colspec=current_col_spec)
    sorting.InvalidateArtValuesKeys(
        mr.cnxn,
        [hotlist_item.issue_id for hotlist_item
         in mr.hotlist.items])

    if post_data.get('remove') == 'true':
      project_and_local_ids = post_data.get('remove_local_ids')
    else:
      project_and_local_ids = post_data.get('add_local_ids')
      if not project_and_local_ids:
        return default_url

    if project_and_local_ids:
      pattern = re.compile(features_constants.ISSUE_INPUT_REGEX)
      if pattern.match(project_and_local_ids):
        issue_refs_tuples = [(pair.split(':')[0].strip(),
                          int(pair.split(':')[1].strip()))
                             for pair in project_and_local_ids.split(',')
                             if pair.strip()]
        project_names = {project_name for (project_name, _) in
                         issue_refs_tuples}
        projects_dict = self.services.project.GetProjectsByName(
        mr.cnxn, project_names)
        selected_iids, _misses = self.services.issue.ResolveIssueRefs(
        mr.cnxn, projects_dict, mr.project_name, issue_refs_tuples)
        if (not selected_iids) or len(issue_refs_tuples) > len(selected_iids):
          mr.errors.issues = _MSG_ISSUES_NOT_FOUND
          # TODO(jojwang): give issues that were not found.
      else:
        mr.errors.issues = _MSG_INVALID_ISSUES_INPUT
    # TODO(jojwang): fix: when there are errors, hidden column come back on
    # the .do page but go away once the errors are fixed and the form
    # is submitted again
    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr, add_local_ids=project_and_local_ids,
          add_issues_selected=ezt.boolean(True), col_spec=current_col_spec)

    else:
      if post_data.get('remove') == 'true':
        self.services.features.RemoveIssuesFromHotlist(
            mr.cnxn, mr.hotlist_id, selected_iids)
      else:
        added_tuples =  [(issue_id, mr.auth.user_id,
                          int(time.time()), '') for issue_id in
                         selected_iids]
        self.services.features.AddIssuesToHotlists(
            mr.cnxn, [mr.hotlist_id], added_tuples)
      return framework_helpers.FormatAbsoluteURL(
          mr, hotlist_view_url, saved=1, ts=int(time.time()),
          include_project=False, colspec=current_col_spec)

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
         in mr.hotlist.items])
    allowed_issues = hotlist_helpers.FilterIssues(
        mr, issues_list, self.services)
    issue_and_hotlist_users = tracker_bizobj.UsersInvolvedInIssues(
        allowed_issues or []).union(features_bizobj.UsersInvolvedInHotlists(
            [mr.hotlist]))
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        issue_and_hotlist_users)
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

    hotlist_context_dict = {
        hotlist_issue.issue_id: {'adder_id': hotlist_issue.adder_id,
                                 'date_added': timestr.FormatRelativeDate(
                                     hotlist_issue.date_added),
                                 'note': hotlist_issue.note}
        for hotlist_issue in mr.hotlist.items}

    grid_view_data = grid_view_helpers.GetGridViewData(
        mr, allowed_issues, harmonized_config,
        users_by_id, starred_iid_set, grid_limited, related_issues,
        hotlist_context_dict=hotlist_context_dict)

    grid_view_data.update({'pagination': paginate.ArtifactPagination(
          mr, allowed_issues, features_constants.DEFAULT_RESULTS_PER_PAGE,
          total_count=len(allowed_issues),
          list_page_url=urls.HOTLIST_ISSUES)})

    return grid_view_data
