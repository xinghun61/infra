# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes and functions for displaying grids of project artifacts.

A grid is a two-dimensional display of items where the user can choose
the X and Y axes.
"""

import collections
import logging

from framework import framework_constants
from framework import sorting
from framework import template_helpers
from proto import tracker_pb2
from tracker import tracker_bizobj


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
    artifact_view_factory, all_label_values, config):
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
    label_value_dict = all_label_values[art.local_id]
    x_vals = GetArtifactAttr(
        art, x_attr, users_by_id, label_value_dict, config)
    y_vals = GetArtifactAttr(
        art, y_attr, users_by_id, label_value_dict, config)
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
    art, attribute_name, users_by_id, label_attr_values_dict, config):
  """Return the requested attribute values of the given artifact.

  Args:
    art: a tracked artifact with labels, local_id, summary, stars, and owner.
    attribute_name: lowercase string name of attribute to get.
    users_by_id: dictionary of UserViews already created.
    label_attr_values_dict: dictionary {'key': [value, ...], }.
    config: ProjectIssueConfig PB for the current project.

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
  # TODO(jrobbins): support blocked on, blocking, and mergedinto.
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
    artifacts, attr_name, users_by_id, all_label_values, config):
  """Return true if any artifact does not have a value for attr_name."""
  # TODO(jrobbins): all_label_values needs to be keyed by issue_id to allow
  # cross-project grid views.
  for art in artifacts:
    vals = GetArtifactAttr(
        art, attr_name.lower(), users_by_id, all_label_values[art.local_id],
        config)
    if framework_constants.NO_VALUES in vals:
      return True

  return False
