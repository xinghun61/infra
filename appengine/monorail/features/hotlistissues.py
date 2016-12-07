# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the hotlistissues page and related forms."""

from third_party import ezt

import settings
import time

from features import features_constants
from features import hotlist_helpers
from framework import servlet
from framework import sorting
from framework import permissions
from framework import framework_helpers
from framework import template_helpers
from framework import urls
from framework import xsrf
from services import features_svc


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

    page_data = self.GetTableViewData(mr)

    with self.profiler.Phase('making page perms'):
      owner_permissions = permissions.CanAdministerHotlist(
          mr.auth.effective_ids, mr.hotlist)
      editor_permissions = permissions.CanEditHotlist(
          mr.auth.effective_ids, mr.hotlist)
      page_perms = template_helpers.EZTItem(EditIssue=None)

    allow_rerank = (not mr.group_by_spec and mr.sort_spec.startswith(
        'rank') and (owner_permissions or editor_permissions))

    # Note: The HotlistView is created and returned in servlet.py
    page_data.update({'owner_permissions': owner_permissions,
                      'editor_permissions': editor_permissions,
                      'issue_tab_mode': 'issueList',
                      'grid_mode': ezt.boolean(False),
                      'set_star_token': xsrf.GenerateToken(
                          mr.auth.user_id, '/u/%s/hotlsits/%d%s.do' % (
                              mr.viewed_username, mr.hotlist_id,
                              urls.ISSUE_SETSTAR_JSON)),
                      'page_perms': page_perms,
                      'colspec': mr.col_spec,
                      'allow_rerank': ezt.boolean(allow_rerank),})
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
        'csv_link': framework_helpers.FormatURL(mr, 'csv'),
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
