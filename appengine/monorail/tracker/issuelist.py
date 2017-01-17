# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Implementation of the issue list feature of the Monorail Issue Tracker.

Summary of page classes:
  IssueList: Shows a table of issue that satisfy search criteria.
"""

import logging
from third_party import ezt

import settings
from framework import framework_helpers
from framework import framework_views
from framework import grid_view_helpers
from framework import permissions
from framework import servlet
from framework import sql
from framework import table_view_helpers
from framework import template_helpers
from framework import urls
from framework import xsrf
from search import frontendsearchpipeline
from search import searchpipeline
from search import query2ast
from services import issue_svc
from tracker import tablecell
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers


class IssueList(servlet.Servlet):
  """IssueList shows a page with a list of issues (search results).

  The issue list is actually a table with a configurable set of columns
  that can be edited by the user.
  """

  _PAGE_TEMPLATE = 'tracker/issue-list-page.ezt'
  _ELIMINATE_BLANK_LINES = True
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ISSUES

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    search_error_message = ''

    # Check if the user's query is just the ID of an existing issue.
    # TODO(jrobbins): consider implementing this for cross-project search.
    if mr.project and tracker_constants.JUMP_RE.match(mr.query):
      local_id = int(mr.query)
      try:
        _issue = self.services.issue.GetIssueByLocalID(
            mr.cnxn, mr.project_id, local_id)  # does it exist?
        url = framework_helpers.FormatAbsoluteURL(
            mr, urls.ISSUE_DETAIL, id=local_id)
        self.redirect(url, abort=True)  # Jump to specified issue.
      except issue_svc.NoSuchIssueException:
        pass  # The user is searching for a number that is not an issue ID.

    with self.profiler.Phase('finishing config work'):
      if mr.project_id:
        config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
      else:
        config = tracker_bizobj.MakeDefaultProjectIssueConfig(None)

    with self.profiler.Phase('starting frontend search pipeline'):
      pipeline = frontendsearchpipeline.FrontendSearchPipeline(
          mr, self.services, self.profiler,
          tracker_constants.DEFAULT_RESULTS_PER_PAGE)

    # Perform promises that require authentication information.
    with self.profiler.Phase('getting stars'):
      starred_iid_set = _GetStarredIssues(
          mr.cnxn, mr.auth.user_id, self.services)

    with self.profiler.Phase('computing col_spec'):
      mr.ComputeColSpec(config)

    if not mr.errors.AnyErrors():
      pipeline.SearchForIIDs()
      pipeline.MergeAndSortIssues()
      pipeline.Paginate()

    with self.profiler.Phase('publishing emails'):
      framework_views.RevealAllEmailsToMembers(mr, pipeline.users_by_id)

    with self.profiler.Phase('getting related issues'):
      related_iids = set()
      if pipeline.grid_mode:
        results_needing_related = pipeline.allowed_results or []
      else:
        results_needing_related = pipeline.visible_results or []
      lower_cols = mr.col_spec.lower().split()
      grid_x = (mr.x or config.default_x_attr or '--').lower()
      grid_y = (mr.y or config.default_y_attr or '--').lower()
      lower_cols.append(grid_x)
      lower_cols.append(grid_y)
      for issue in results_needing_related:
        if 'blockedon' in lower_cols:
          related_iids.update(issue.blocked_on_iids)
        if 'blocking' in lower_cols:
          related_iids.update(issue.blocking_iids)
        if 'mergedinto' in lower_cols:
          related_iids.add(issue.merged_into)
      related_issues_list = self.services.issue.GetIssues(
          mr.cnxn, list(related_iids))
      related_issues = {issue.issue_id: issue for issue in related_issues_list}

    with self.profiler.Phase('building table/grid'):
      if pipeline.grid_mode:
        page_data = grid_view_helpers.GetGridViewData(
            mr, pipeline.allowed_results or [], pipeline.harmonized_config,
            pipeline.users_by_id, starred_iid_set, pipeline.grid_limited,
            related_issues)
      else:
        page_data = self.GetTableViewData(
            mr, pipeline.visible_results or [], pipeline.harmonized_config,
            pipeline.users_by_id, starred_iid_set, related_issues)

    # We show a special message when no query will every produce any results
    # because the project has no issues in it.
    with self.profiler.Phase('starting stars promise'):
      if mr.project_id:
        project_has_any_issues = (
            pipeline.allowed_results or
            self.services.issue.GetHighestLocalID(mr.cnxn, mr.project_id) != 0)
      else:
        project_has_any_issues = True  # Message only applies in a project.

    with self.profiler.Phase('making page perms'):
      page_perms = self.MakePagePerms(
          mr, None,
          permissions.SET_STAR,
          permissions.CREATE_ISSUE,
          permissions.EDIT_ISSUE)

    if pipeline.error_responses:
      search_error_message = (
          '%d search backends did not respond or had errors. '
          'These results are probably incomplete.'
          % len(pipeline.error_responses))

    # Update page data with variables that are shared between list and
    # grid view.
    users_hotlists = self.services.features.GetHotlistsByUserID(
        mr.cnxn, mr.auth.user_id)
    print mr.auth.user_id
    print users_hotlists
    print "sjdlkfjslkdjfkldsjflkdsnfsdlfnlsdkjflkdsj"
    page_data.update({
        'issue_tab_mode': 'issueList',
        'pagination': pipeline.pagination,
        'is_cross_project': ezt.boolean(len(pipeline.query_project_ids) != 1),
        'project_has_any_issues': ezt.boolean(project_has_any_issues),
        'colspec': mr.col_spec,
        'page_perms': page_perms,
        'grid_mode': ezt.boolean(pipeline.grid_mode),
        'panel_id': mr.panel_id,
        'set_star_token': xsrf.GenerateToken(
            mr.auth.user_id, '/p/%s%s.do' % (
                mr.project_name, urls.ISSUE_SETSTAR_JSON)),
        'search_error_message': search_error_message,
        'is_hotlist': ezt.boolean(False),
        'users_hotlists': users_hotlists,
        # the following are needed by templates for hotlists
        'owner_permissions': ezt.boolean(False),
        'editor_permissions': ezt.boolean(False),
        'remove_issues_token': '',
        'add_local_ids': '',
        'placeholder': ''
    })

    return page_data

  def GetCellFactories(self):
    return tablecell.CELL_FACTORIES

  def GetTableViewData(
      self, mr, results, config, users_by_id, starred_iid_set, related_issues):
    """EZT template values to render a Table View of issues.

    Args:
      mr: commonly used info parsed from the request.
      results: list of Issue PBs for the search results to be displayed.
      config: The ProjectIssueConfig PB for the current project.
      users_by_id: A dictionary {user_id: UserView} for all the users
      involved in results.
      starred_iid_set: Set of issues that the user has starred.
      related_issues: dict {issue_id: issue} of pre-fetched related issues.

    Returns:
      Dictionary of page data for rendering of the Table View.
    """
    # We need ordered_columns because EZT loops have no loop-counter available.
    # And, we use column number in the Javascript to hide/show columns.
    columns = mr.col_spec.split()
    ordered_columns = [template_helpers.EZTItem(col_index=i, name=col)
                       for i, col in enumerate(columns)]
    unshown_columns = table_view_helpers.ComputeUnshownColumns(
        results, columns, config, tracker_constants.OTHER_BUILT_IN_COLS)

    lower_columns = mr.col_spec.lower().split()
    lower_group_by = mr.group_by_spec.lower().split()
    table_data = _MakeTableData(
        results, starred_iid_set, lower_columns, lower_group_by,
        users_by_id, self.GetCellFactories(), related_issues, config)

    # Used to offer easy filtering of each unique value in each column.
    column_values = table_view_helpers.ExtractUniqueValues(
        lower_columns, results, users_by_id, config, related_issues)

    table_view_data = {
        'table_data': table_data,
        'column_values': column_values,
        # Put ordered_columns inside a list of exactly 1 panel so that
        # it can work the same as the dashboard initial panel list headers.
        'panels': [template_helpers.EZTItem(ordered_columns=ordered_columns)],
        'unshown_columns': unshown_columns,
        'cursor': mr.cursor or mr.preview,
        'preview': mr.preview,
        'default_colspec': tracker_constants.DEFAULT_COL_SPEC,
        'default_results_per_page': tracker_constants.DEFAULT_RESULTS_PER_PAGE,
        'csv_link': framework_helpers.FormatURL(
            mr, 'csv', num=settings.max_artifact_search_results_per_page),
        'preview_on_hover': ezt.boolean(
            _ShouldPreviewOnHover(mr.auth.user_pb)),
        }
    return table_view_data

  def GatherHelpData(self, mr, page_data):
    """Return a dict of values to drive on-page user help.

    Args:
      mr: common information parsed from the HTTP request.
      page_data: Dictionary of base and page template data.

    Returns:
      A dict of values to drive on-page user help, to be added to page_data.
    """
    help_data = super(IssueList, self).GatherHelpData(mr, page_data)
    dismissed = []
    if mr.auth.user_pb:
      dismissed = mr.auth.user_pb.dismissed_cues

    if mr.project_id:
      config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    else:
      config = tracker_bizobj.MakeDefaultProjectIssueConfig(None)

    try:
      _query_ast, is_fulltext_query = searchpipeline.ParseQuery(
          mr, config, self.services)
    except query2ast.InvalidQueryError:
      is_fulltext_query = False

    query_plus_col_spec = '%r %r' % (
        mr.query and mr.query.lower(), mr.col_spec and mr.col_spec.lower())
    uses_timestamp_term = any(
      col_name in query_plus_col_spec
      for col_name in ('ownermodified', 'statusmodified', 'componentmodified'))

    if (mr.mode == 'grid' and mr.cells == 'tiles' and
        len(page_data.get('results', [])) > settings.max_tiles_in_grid and
        'showing_ids_instead_of_tiles' not in dismissed):
      help_data['cue'] = 'showing_ids_instead_of_tiles'
    elif (_AnyDerivedValues(page_data.get('table_data', [])) and
          'italics_mean_derived' not in dismissed):
      help_data['cue'] = 'italics_mean_derived'
    elif (uses_timestamp_term and
          'issue_timestamps' not in dismissed):
      help_data['cue'] = 'issue_timestamps'
    # Note that the following are only offered to signed in users because
    # otherwise the first one would appear all the time to anon users.
    elif (mr.auth.user_id and mr.mode != 'grid' and
          'dit_keystrokes' not in dismissed):
      help_data['cue'] = 'dit_keystrokes'
    elif (mr.auth.user_id and is_fulltext_query and
          'stale_fulltext' not in dismissed):
      help_data['cue'] = 'stale_fulltext'

    return help_data

def _AnyDerivedValues(table_data):
  """Return True if any value in the given table_data was derived."""
  for row in table_data:
    for cell in row.cells:
      for item in cell.values:
        if item.is_derived:
          return True

  return False


def _MakeTableData(
    visible_results, starred_iid_set, lower_columns, lower_group_by,
    users_by_id, cell_factories, related_issues, config):
  """Return a list of list row objects for display by EZT."""
  table_data = table_view_helpers.MakeTableData(
      visible_results, starred_iid_set,
      lower_columns, lower_group_by, users_by_id, cell_factories,
      lambda issue: issue.issue_id, related_issues, config)

  for row, art in zip(table_data, visible_results):
    row.local_id = art.local_id
    row.project_name = art.project_name
    row.issue_ref = '%s:%d' % (art.project_name, art.local_id)
    row.issue_url = tracker_helpers.FormatRelativeIssueURL(
        art.project_name, urls.ISSUE_DETAIL, id=art.local_id)

  return table_data


def _GetStarredIssues(cnxn, logged_in_user_id, services):
  """Get the set of issues that the logged in user has starred."""
  starred_iids = services.issue_star.LookupStarredItemIDs(
      cnxn, logged_in_user_id)
  return set(starred_iids)


def _ShouldPreviewOnHover(user):
  """Return true if we should show the issue preview when the user hovers.

  Args:
    user: User PB for the currently signed in user.

  Returns:
    True if the preview (peek) should open on hover over the issue ID.
  """
  return settings.enable_quick_edit and user.preview_on_hover
