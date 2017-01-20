# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes and functions for displaying grids of project artifacts.

A grid is a two-dimensional display of items where the user can choose
the X and Y axes.
"""

from third_party import ezt

import collections
import logging
import settings

from framework import framework_constants
from framework import sorting
from framework import table_view_helpers
from framework import template_helpers
from framework import urls
from proto import tracker_pb2
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers


# We shorten long attribute values to fit into the table cells.
_MAX_CELL_DISPLAY_CHARS = 70


def SortGridHeadings(col_name, heading_value_list, users_by_id, config,
                     asc_accessors):
  """Sort the grid headings according to well-known status and label order.

  Args:
    col_name: String column name that is used on that grid axis.
    heading_value_list: List of grid row or column heading values.
    users_by_id: Dict mapping user_ids to UserViews.
    config: ProjectIssueConfig PB for the current project.
    asc_accessors: Dict (col_name -> function()) for special columns.

  Returns:
    The same heading values, but sorted in a logical order.
  """
  decorated_list = []
  fd = tracker_bizobj.FindFieldDef(col_name, config)
  if fd:  # Handle fields.
    for value in heading_value_list:
      field_value = tracker_bizobj.GetFieldValueWithRawValue(
          fd.field_type, None, users_by_id, value)
      decorated_list.append([field_value, field_value])
  elif col_name == 'status':
    wk_statuses = [wks.status.lower()
                   for wks in config.well_known_statuses]
    decorated_list = [(_WKSortingValue(value.lower(), wk_statuses), value)
                      for value in heading_value_list]

  elif col_name in asc_accessors:  # Special cols still sort alphabetically.
    decorated_list = [(value, value)
                      for value in heading_value_list]

  else:  # Anything else is assumed to be a label prefix
    wk_labels = [wkl.label.lower().split('-', 1)[-1]
                 for wkl in config.well_known_labels]
    decorated_list = [(_WKSortingValue(value.lower(), wk_labels), value)
                      for value in heading_value_list]

  decorated_list.sort()
  result = [decorated_tuple[1] for decorated_tuple in decorated_list]
  logging.info('Headers for %s are: %r', col_name, result)
  return result


def _WKSortingValue(value, well_known_list):
  """Return a value used to sort headings so that well-known ones are first."""
  if not value:
    return sorting.MAX_STRING  # Undefined values sort last.
  try:
    # well-known values sort by index
    return well_known_list.index(value)
  except ValueError:
    return value  # odd-ball values lexicographically after all well-known ones


def MakeGridData(
    artifacts, x_attr, x_headings, y_attr, y_headings, users_by_id,
    artifact_view_factory, all_label_values, config, related_issues,
    hotlist_context_dict=None):
  """Return a list of grid row items for display by EZT.

  Args:
    artifacts: a list of issues to consider showing.
    x_attr: lowercase name of the attribute that defines the x-axis.
    x_headings: list of values for column headings.
    y_attr: lowercase name of the attribute that defines the y-axis.
    y_headings: list of values for row headings.
    users_by_id: dict {user_id: user_view, ...} for referenced users.
    artifact_view_factory: constructor for grid tiles.
    all_label_values: pre-parsed dictionary of values from the key-value
        labels on each issue: {issue_id: {key: [val,...], ...}, ...}
    config: ProjectIssueConfig PB for the current project.
    related_issues: dict {issue_id: issue} of pre-fetched related issues.
    hotlist_context_dict: dict{issue_id: {hotlist_item_field: field_value, ..}}

  Returns:
    A list of EZTItems, each representing one grid row, and each having
    a nested list of grid cells.

  Each grid row has a row name, and a list of cells.  Each cell has a
  list of tiles.  Each tile represents one artifact.  Artifacts are
  represented once in each cell that they match, so one artifact that
  has multiple values for a certain attribute can occur in multiple cells.
  """
  x_attr = x_attr.lower()
  y_attr = y_attr.lower()

  # A flat dictionary {(x, y): [cell, ...], ...] for the whole grid.
  x_y_data = collections.defaultdict(list)

  # Put each issue into the grid cell(s) where it belongs.
  for art in artifacts:
    if hotlist_context_dict:
      hotlist_issues_context = hotlist_context_dict[art.issue_id]
    else:
      hotlist_issues_context = None
    label_value_dict = all_label_values[art.local_id]
    x_vals = GetArtifactAttr(
        art, x_attr, users_by_id, label_value_dict, config, related_issues,
        hotlist_issue_context=hotlist_issues_context)
    y_vals = GetArtifactAttr(
        art, y_attr, users_by_id, label_value_dict, config, related_issues,
        hotlist_issue_context=hotlist_issues_context)
    tile = artifact_view_factory(art)

    # Put the current issue into each cell where it belongs, which will usually
    # be exactly 1 cell, but it could be a few.
    if x_attr != '--' and y_attr != '--':  # User specified both axes.
      for x in x_vals:
        for y in y_vals:
          x_y_data[x, y].append(tile)
    elif y_attr != '--':  # User only specified Y axis.
      for y in y_vals:
        x_y_data['All', y].append(tile)
    elif x_attr != '--':  # User only specified X axis.
      for x in x_vals:
        x_y_data[x, 'All'].append(tile)
    else:  # User specified neither axis.
      x_y_data['All', 'All'].append(tile)

  # Convert the dictionary to a list-of-lists so that EZT can iterate over it.
  grid_data = []
  for y in y_headings:
    cells_in_row = []
    for x in x_headings:
      tiles = x_y_data[x, y]

      drill_down = ''
      if x_attr != '--':
        drill_down = MakeDrillDownSearch(x_attr, x)
      if y_attr != '--':
        drill_down += MakeDrillDownSearch(y_attr, y)

      cells_in_row.append(template_helpers.EZTItem(
          tiles=tiles, count=len(tiles), drill_down=drill_down))
    grid_data.append(template_helpers.EZTItem(
        grid_y_heading=y, cells_in_row=cells_in_row))

  return grid_data


def MakeDrillDownSearch(attr, value):
  """Constructs search term for drill-down.

  Args:
    attr: lowercase name of the attribute to narrow the search on.
    value: value to narrow the search to.

  Returns:
    String with user-query term to narrow a search to the given attr value.
  """
  if value == framework_constants.NO_VALUES:
    return '-has:%s ' % attr
  else:
    return '%s=%s ' % (attr, value)


def MakeLabelValuesDict(art):
  """Return a dict of label values and a list of one-word labels.

  Args:
    art: artifact object, e.g., an issue PB.

  Returns:
    A dict {prefix: [suffix,...], ...} for each key-value label.
  """
  label_values = collections.defaultdict(list)
  for label_name in tracker_bizobj.GetLabels(art):
    if '-' in label_name:
      key, value = label_name.split('-', 1)
      label_values[key.lower()].append(value)

  return label_values


def GetArtifactAttr(
    art, attribute_name, users_by_id, label_attr_values_dict,
    config, related_issues, hotlist_issue_context=None):
  """Return the requested attribute values of the given artifact.

  Args:
    art: a tracked artifact with labels, local_id, summary, stars, and owner.
    attribute_name: lowercase string name of attribute to get.
    users_by_id: dictionary of UserViews already created.
    label_attr_values_dict: dictionary {'key': [value, ...], }.
    config: ProjectIssueConfig PB for the current project.
    related_issues: dict {issue_id: issue} of pre-fetched related issues.
    hotlist_issue_context: dict of {hotlist_issue_field: field_value,..}

  Returns:
    A list of string attribute values, or [framework_constants.NO_VALUES]
    if the artifact has no value for that attribute.
  """
  if attribute_name == '--':
    return []
  if attribute_name == 'id':
    return [art.local_id]
  if attribute_name == 'summary':
    return [art.summary]
  if attribute_name == 'status':
    return [tracker_bizobj.GetStatus(art)]
  if attribute_name == 'stars':
    return [art.star_count]
  if attribute_name == 'attachments':
    return [art.attachment_count]
  # TODO(jrobbins): support blocking
  if attribute_name == 'project':
    return [art.project_name]
  if attribute_name == 'mergedinto':
    if art.merged_into and art.merged_into != 0:
      return [tracker_bizobj.FormatIssueRef((
          related_issues[art.merged_into].project_name,
          related_issues[art.merged_into].local_id))]
    else:
      return [framework_constants.NO_VALUES]
  if attribute_name == 'blocked':
    return ['Yes' if art.blocked_on_iids else 'No']
  if attribute_name == 'blockedon':
    if not art.blocked_on_iids:
      return [framework_constants.NO_VALUES]
    else:
      return [tracker_bizobj.FormatIssueRef((
          related_issues[blocked_on_iid].project_name,
          related_issues[blocked_on_iid].local_id)) for
              blocked_on_iid in art.blocked_on_iids]
  if attribute_name == 'adder':
    if hotlist_issue_context:
      adder_id = hotlist_issue_context['adder_id']
      return [users_by_id[adder_id].display_name]
    else:
      return [framework_constants.NO_VALUES]
  if attribute_name == 'added':
    if hotlist_issue_context:
      return [hotlist_issue_context['date_added']]
    else:
      return [framework_constants.NO_VALUES]
  if attribute_name == 'reporter':
    return [users_by_id[art.reporter_id].display_name]
  if attribute_name == 'owner':
    owner_id = tracker_bizobj.GetOwnerId(art)
    if not owner_id:
      return [framework_constants.NO_VALUES]
    else:
      return [users_by_id[owner_id].display_name]
  if attribute_name == 'cc':
    cc_ids = tracker_bizobj.GetCcIds(art)
    if not cc_ids:
      return [framework_constants.NO_VALUES]
    else:
      return [users_by_id[cc_id].display_name for cc_id in cc_ids]
  if attribute_name == 'component':
    comp_ids = list(art.component_ids) + list(art.derived_component_ids)
    if not comp_ids:
      return [framework_constants.NO_VALUES]
    else:
      paths = []
      for comp_id in comp_ids:
        cd = tracker_bizobj.FindComponentDefByID(comp_id, config)
        if cd:
          paths.append(cd.path)
      return paths

  # Check to see if it is a field. Process as field only if it is not an enum
  # type because enum types are stored as key-value labels.
  fd = tracker_bizobj.FindFieldDef(attribute_name, config)
  if fd and fd.field_type != tracker_pb2.FieldTypes.ENUM_TYPE:
    values = []
    for fv in art.field_values:
      if fv.field_id == fd.field_id:
        value = tracker_bizobj.GetFieldValueWithRawValue(
            fd.field_type, fv, users_by_id, None)
        values.append(value)
    return values

  # Since it is not a built-in attribute or a field, it must be a key-value
  # label.
  return label_attr_values_dict.get(
      attribute_name, [framework_constants.NO_VALUES])


def AnyArtifactHasNoAttr(
    artifacts, attr_name, users_by_id, all_label_values, config,
    related_issues, hotlist_context_dict=None):
  """Return true if any artifact does not have a value for attr_name."""
  # TODO(jrobbins): all_label_values needs to be keyed by issue_id to allow
  # cross-project grid views.
  for art in artifacts:
    if hotlist_context_dict:
      hotlist_issue_context = hotlist_context_dict[art.issue_id]
    else:
      hotlist_issue_context = None
    vals = GetArtifactAttr(
        art, attr_name.lower(), users_by_id, all_label_values[art.local_id],
        config, related_issues, hotlist_issue_context=hotlist_issue_context)
    if framework_constants.NO_VALUES in vals:
      return True

  return False


def GetGridViewData(
    mr, results, config, users_by_id, starred_iid_set,
    grid_limited, related_issues, hotlist_context_dict=None):
  """EZT template values to render a Grid View of issues.
  Args:
    mr: commonly used info parsed from the request.
    results: The Issue PBs that are the search results to be displayed.
    config: The ProjectConfig PB for the project this view is in.
    users_by_id: A dictionary {user_id: user_view,...} for all the users
        involved in results.
    starred_iid_set: Set of issues that the user has starred.
    grid_limited: True if the results were limited to fit within the grid.
    related_issues: dict {issue_id: issue} of pre-fetched related issues.
    hotlist_context_dict: dict for building a hotlist grid table

  Returns:
    Dictionary for EZT template rendering of the Grid View.
  """
  # We need ordered_columns because EZT loops have no loop-counter available.
  # And, we use column number in the Javascript to hide/show columns.
  columns = mr.col_spec.split()
  ordered_columns = [template_helpers.EZTItem(col_index=i, name=col)
                     for i, col in enumerate(columns)]
  unshown_columns = table_view_helpers.ComputeUnshownColumns(
      results, columns, config, tracker_constants.OTHER_BUILT_IN_COLS)

  grid_x_attr = (mr.x or config.default_x_attr or '--').lower()
  grid_y_attr = (mr.y or config.default_y_attr or '--').lower()
  all_label_values = {}
  for art in results:
    all_label_values[art.local_id] = (
        MakeLabelValuesDict(art))

  if grid_x_attr == '--':
    grid_x_headings = ['All']
  else:
    grid_x_items = table_view_helpers.ExtractUniqueValues(
        [grid_x_attr], results, users_by_id, config, related_issues,
        hotlist_context_dict=hotlist_context_dict)
    grid_x_headings = grid_x_items[0].filter_values
    if AnyArtifactHasNoAttr(
        results, grid_x_attr, users_by_id, all_label_values,
        config, related_issues, hotlist_context_dict= hotlist_context_dict):
      grid_x_headings.append(framework_constants.NO_VALUES)
    grid_x_headings = SortGridHeadings(
        grid_x_attr, grid_x_headings, users_by_id, config,
        tracker_helpers.SORTABLE_FIELDS)

  if grid_y_attr == '--':
    grid_y_headings = ['All']
  else:
    grid_y_items = table_view_helpers.ExtractUniqueValues(
        [grid_y_attr], results, users_by_id, config, related_issues,
        hotlist_context_dict=hotlist_context_dict)
    grid_y_headings = grid_y_items[0].filter_values
    if AnyArtifactHasNoAttr(
        results, grid_y_attr, users_by_id, all_label_values,
        config, related_issues, hotlist_context_dict= hotlist_context_dict):
      grid_y_headings.append(framework_constants.NO_VALUES)
    grid_y_headings = SortGridHeadings(
        grid_y_attr, grid_y_headings, users_by_id, config,
        tracker_helpers.SORTABLE_FIELDS)

  logging.info('grid_x_headings = %s', grid_x_headings)
  logging.info('grid_y_headings = %s', grid_y_headings)
  grid_data = PrepareForMakeGridData(
      results, starred_iid_set, grid_x_attr, grid_x_headings,
      grid_y_attr, grid_y_headings, users_by_id, all_label_values,
      config, related_issues, hotlist_context_dict=hotlist_context_dict)

  grid_axis_choice_dict = {}
  for oc in ordered_columns:
    grid_axis_choice_dict[oc.name] = True
  for uc in unshown_columns:
    grid_axis_choice_dict[uc] = True
  for bad_axis in tracker_constants.NOT_USED_IN_GRID_AXES:
    if bad_axis in grid_axis_choice_dict:
      del grid_axis_choice_dict[bad_axis]
  grid_axis_choices = grid_axis_choice_dict.keys()
  grid_axis_choices.sort()

  grid_cell_mode = mr.cells
  if len(results) > settings.max_tiles_in_grid and mr.cells == 'tiles':
    grid_cell_mode = 'ids'

  grid_view_data = {
      'grid_limited': ezt.boolean(grid_limited),
      'grid_shown': len(results),
      'grid_x_headings': grid_x_headings,
      'grid_y_headings': grid_y_headings,
      'grid_data': grid_data,
      'grid_axis_choices': grid_axis_choices,
      'grid_cell_mode': grid_cell_mode,
      'results': results,  # Really only useful in if-any.
  }
  return grid_view_data


def PrepareForMakeGridData(
    allowed_results, starred_iid_set, x_attr,
    grid_col_values, y_attr, grid_row_values, users_by_id, all_label_values,
    config, related_issues, hotlist_context_dict=None):
  """Return all data needed for EZT to render the body of the grid view."""

  def IssueViewFactory(issue):
    return template_helpers.EZTItem(
      summary=issue.summary, local_id=issue.local_id, issue_id=issue.issue_id,
      status=issue.status or issue.derived_status, starred=None)

  grid_data = MakeGridData(
      allowed_results, x_attr, grid_col_values, y_attr, grid_row_values,
      users_by_id, IssueViewFactory, all_label_values, config, related_issues,
      hotlist_context_dict=hotlist_context_dict)
  issue_dict = {issue.issue_id: issue for issue in allowed_results}
  for grid_row in grid_data:
    for grid_cell in grid_row.cells_in_row:
      for tile in grid_cell.tiles:
        if tile.issue_id in starred_iid_set:
          tile.starred = ezt.boolean(True)
        issue = issue_dict[tile.issue_id]
        tile.issue_url = tracker_helpers.FormatRelativeIssueURL(
            issue.project_name, urls.ISSUE_DETAIL, id=tile.local_id)
        tile.issue_ref = issue.project_name + ':' + str(tile.local_id)

  return grid_data
