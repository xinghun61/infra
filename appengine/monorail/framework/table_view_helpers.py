# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes and functions for displaying lists of project artifacts.

This file exports classes TableRow and TableCell that help
represent HTML table rows and cells.  These classes make rendering
HTML tables that list project artifacts much easier to do with EZT.
"""

import collections
import logging

from third_party import ezt

from framework import framework_constants
from framework import template_helpers
from framework import timestr
from proto import tracker_pb2
from tracker import tracker_bizobj


def ComputeUnshownColumns(results, shown_columns, config, built_in_cols):
  """Return a list of unshown columns that the user could add.

  Args:
    results: list of search result PBs. Each must have labels.
    shown_columns: list of column names to be used in results table.
    config: harmonized config for the issue search, including all
        well known labels and custom fields.
    built_in_cols: list of other column names that are built into the tool.
      E.g., star count, or creation date.

  Returns:
    List of column names to append to the "..." menu.
  """
  unshown_set = set()  # lowercases column names
  unshown_list = []  # original-case column names
  shown_set = {col.lower() for col in shown_columns}
  labels_already_seen = set()  # whole labels, original case

  def _MaybeAddLabel(label_name):
    """Add the key part of the given label if needed."""
    if label_name.lower() in labels_already_seen:
      return
    labels_already_seen.add(label_name.lower())
    if '-' in label_name:
      col, _value = label_name.split('-', 1)
      _MaybeAddCol(col)

  def _MaybeAddCol(col):
    if col.lower() not in shown_set and col.lower() not in unshown_set:
      unshown_list.append(col)
      unshown_set.add(col.lower())

  # The user can always add any of the default columns.
  for col in config.default_col_spec.split():
    _MaybeAddCol(col)

  # The user can always add any of the built-in columns.
  for col in built_in_cols:
    _MaybeAddCol(col)

  # The user can add a column for any well-known labels
  for wkl in config.well_known_labels:
    _MaybeAddLabel(wkl.label)

  # The user can add a column for any custom field
  field_ids_alread_seen = set()
  for fd in config.field_defs:
    field_lower = fd.field_name.lower()
    field_ids_alread_seen.add(fd.field_id)
    if field_lower not in shown_set and field_lower not in unshown_set:
      unshown_list.append(fd.field_name)
      unshown_set.add(field_lower)

  # The user can add a column for any key-value label or field in the results.
  for r in results:
    for label_name in tracker_bizobj.GetLabels(r):
      _MaybeAddLabel(label_name)
    for field_value in r.field_values:
      if field_value.field_id not in field_ids_alread_seen:
        field_ids_alread_seen.add(field_value.field_id)
        fd = tracker_bizobj.FindFieldDefByID(field_value.field_id, config)
        if fd:  # could be None for a foreign field, which we don't display.
          field_lower = fd.field_name.lower()
          if field_lower not in shown_set and field_lower not in unshown_set:
            unshown_list.append(fd.field_name)
            unshown_set.add(field_lower)

  return sorted(unshown_list)


def ExtractUniqueValues(columns, artifact_list, users_by_id,
                        config, related_issues, hotlist_context_dict=None):
  """Build a nested list of unique values so the user can auto-filter.

  Args:
    columns: a list of lowercase column name strings, which may contain
        combined columns like "priority/pri".
    artifact_list: a list of artifacts in the complete set of search results.
    users_by_id: dict mapping user_ids to UserViews.
    config: ProjectIssueConfig PB for the current project.
    related_issues: dict {issue_id: issue} of pre-fetched related issues.
    hotlist_context_dict: dict for building a hotlist grid table

  Returns:
    [EZTItem(col1, colname1, [val11, val12,...]), ...]
    A list of EZTItems, each of which has a col_index, column_name,
    and a list of unique values that appear in that column.
  """
  column_values = {col_name: {} for col_name in columns}

  # For each combined column "a/b/c", add entries that point from "a" back
  # to "a/b/c", from "b" back to "a/b/c", and from "c" back to "a/b/c".
  combined_column_parts = collections.defaultdict(list)
  for col in columns:
    if '/' in col:
      for col_part in col.split('/'):
        combined_column_parts[col_part].append(col)

  unique_labels = set()
  for art in artifact_list:
    unique_labels.update(tracker_bizobj.GetLabels(art))

  for label in unique_labels:
    if '-' in label:
      col, val = label.split('-', 1)
      col = col.lower()
      if col in column_values:
        column_values[col][val.lower()] = val
      if col in combined_column_parts:
        for combined_column in combined_column_parts[col]:
          column_values[combined_column][val.lower()] = val
    else:
      if 'summary' in column_values:
        column_values['summary'][label.lower()] = label

  # TODO(jrobbins): Consider refacting some of this to tracker_bizobj
  # or a new builtins.py to reduce duplication.
  if 'reporter' in column_values:
    for art in artifact_list:
      reporter_id = art.reporter_id
      if reporter_id and reporter_id in users_by_id:
        reporter_username = users_by_id[reporter_id].display_name
        column_values['reporter'][reporter_username] = reporter_username

  if 'owner' in column_values:
    for art in artifact_list:
      owner_id = tracker_bizobj.GetOwnerId(art)
      if owner_id and owner_id in users_by_id:
        owner_username = users_by_id[owner_id].display_name
        column_values['owner'][owner_username] = owner_username

  if 'cc' in column_values:
    for art in artifact_list:
      cc_ids = tracker_bizobj.GetCcIds(art)
      for cc_id in cc_ids:
        if cc_id and cc_id in users_by_id:
          cc_username = users_by_id[cc_id].display_name
          column_values['cc'][cc_username] = cc_username

  if 'component' in column_values:
    for art in artifact_list:
      all_comp_ids = list(art.component_ids) + list(art.derived_component_ids)
      for component_id in all_comp_ids:
        cd = tracker_bizobj.FindComponentDefByID(component_id, config)
        if cd:
          column_values['component'][cd.path] = cd.path

  if 'stars' in column_values:
    for art in artifact_list:
      star_count = art.star_count
      column_values['stars'][star_count] = star_count

  if 'status' in column_values:
    for art in artifact_list:
      status = tracker_bizobj.GetStatus(art)
      if status:
        column_values['status'][status.lower()] = status

  if 'project' in column_values:
    for art in artifact_list:
      project_name = art.project_name
      column_values['project'][project_name] = project_name

  if 'mergedinto' in column_values:
    for art in artifact_list:
      if art.merged_into and art.merged_into != 0:
        merged_issue = related_issues[art.merged_into]
        merged_issue_ref = tracker_bizobj.FormatIssueRef((
            merged_issue.project_name, merged_issue.local_id))
        column_values['mergedinto'][merged_issue_ref] = merged_issue_ref

  if 'blocked' in column_values:
    for art in artifact_list:
      if art.blocked_on_iids:
        column_values['blocked']['is_blocked'] = 'Yes'
      else:
        column_values['blocked']['is_not_blocked'] = 'No'

  if 'blockedon' in column_values:
    for art in artifact_list:
      if art.blocked_on_iids:
        for blocked_on_iid in art.blocked_on_iids:
          blocked_on_issue = related_issues[blocked_on_iid]
          blocked_on_ref = tracker_bizobj.FormatIssueRef((
              blocked_on_issue.project_name, blocked_on_issue.local_id))
          column_values['blockedon'][blocked_on_ref] = blocked_on_ref

  # TODO(jrobbins): blocked on, and blocking.
  # And, the ability to parse a user query on those fields and do a SQL search.

  if 'added' in column_values:
    for art in artifact_list:
      if hotlist_context_dict and hotlist_context_dict[art.issue_id]:
        issue_dict = hotlist_context_dict[art.issue_id]
        date_added = issue_dict['date_added']
        column_values['added'][date_added] = date_added

  if 'adder' in column_values:
    for art in artifact_list:
      if hotlist_context_dict and hotlist_context_dict[art.issue_id]:
        issue_dict = hotlist_context_dict[art.issue_id]
        adder_id = issue_dict['adder_id']
        adder = users_by_id[adder_id].display_name
        column_values['adder'][adder] = adder

  if 'attachments' in column_values:
    for art in artifact_list:
      attachment_count = art.attachment_count
      column_values['attachments'][attachment_count] = attachment_count

  # Add all custom field values if the custom field name is a shown column.
  field_id_to_col = {}
  for art in artifact_list:
    for fv in art.field_values:
      field_col, field_type = field_id_to_col.get(fv.field_id, (None, None))
      if field_col == 'NOT_SHOWN':
        continue
      if field_col is None:
        fd = tracker_bizobj.FindFieldDefByID(fv.field_id, config)
        if not fd:
          field_id_to_col[fv.field_id] = 'NOT_SHOWN', None
          continue
        field_col = fd.field_name.lower()
        field_type = fd.field_type
        if field_col not in column_values:
          field_id_to_col[fv.field_id] = 'NOT_SHOWN', None
          continue
        field_id_to_col[fv.field_id] = field_col, field_type

      if field_type == tracker_pb2.FieldTypes.ENUM_TYPE:
        continue  # Already handled by label parsing
      elif field_type == tracker_pb2.FieldTypes.INT_TYPE:
        val = fv.int_value
      elif field_type == tracker_pb2.FieldTypes.STR_TYPE:
        val = fv.str_value
      elif field_type == tracker_pb2.FieldTypes.USER_TYPE:
        user = users_by_id.get(fv.user_id)
        val = user.email if user else framework_constants.NO_USER_NAME
      elif field_type == tracker_pb2.FieldTypes.DATE_TYPE:
        val = fv.int_value  # TODO(jrobbins): convert to date
      elif field_type == tracker_pb2.FieldTypes.BOOL_TYPE:
        val = 'Yes' if fv.int_value else 'No'

      column_values[field_col][val] = val

  # TODO(jrobbins): make the capitalization of well-known unique label and
  # status values match the way it is written in the issue config.

  # Return EZTItems for each column in left-to-right display order.
  result = []
  for i, col_name in enumerate(columns):
    # TODO(jrobbins): sort each set of column values top-to-bottom, by the
    # order specified in the project artifact config. For now, just sort
    # lexicographically to make expected output defined.
    sorted_col_values = sorted(column_values[col_name].values())
    result.append(template_helpers.EZTItem(
        col_index=i, column_name=col_name, filter_values=sorted_col_values))

  return result


def MakeTableData(
    visible_results, starred_items, lower_columns, lower_group_by,
    users_by_id, cell_factories, id_accessor, related_issues, config,
    context_for_all_issues=None):
  """Return a list of list row objects for display by EZT.

  Args:
    visible_results: list of artifacts to display on one pagination page.
    starred_items: list of IDs/names of items in the current project
        that the signed in user has starred.
    lower_columns: list of column names to display, all lowercase.  These can
        be combined column names, e.g., 'priority/pri'.
    lower_group_by: list of column names that define row groups, all lowercase.
    users_by_id: dict mapping user IDs to UserViews.
    cell_factories: dict of functions that each create TableCell objects.
    id_accessor: function that maps from an artifact to the ID/name that might
        be in the starred items list.
    related_issues: dict {issue_id: issue} of pre-fetched related issues.
    config: ProjectIssueConfig PB for the current project.
    context_for_all_issues: A dictionary of dictionaries containing values
        passed in to cell factory functions to create TableCells. Dictionary
        form: {issue_id: {'rank': issue_rank, 'issue_info': info_value, ..},
        issue_id: {'rank': issue_rank}, ..}

  Returns:
    A list of TableRow objects, one for each visible result.
  """
  table_data = []

  group_cell_factories = [
      ChooseCellFactory(group.strip('-'), cell_factories, config)
      for group in lower_group_by]

  # Make a list of cell factories, one for each column.
  factories_to_use = [
      ChooseCellFactory(col, cell_factories, config) for col in lower_columns]

  current_group = None
  for idx, art in enumerate(visible_results):
    row = MakeRowData(
        art, lower_columns, users_by_id, factories_to_use, related_issues,
        config, context_for_all_issues)
    row.starred = ezt.boolean(id_accessor(art) in starred_items)
    row.idx = idx  # EZT does not have loop counters, so add idx.
    table_data.append(row)
    row.group = None

    # Also include group information for the first row in each group.
    # TODO(jrobbins): This seems like more overhead than we need for the
    # common case where no new group heading row is to be inserted.
    group = MakeRowData(
        art, [group_name.strip('-') for group_name in lower_group_by],
        users_by_id, group_cell_factories, related_issues, config,
        context_for_all_issues)
    for cell, group_name in zip(group.cells, lower_group_by):
      cell.group_name = group_name
    if group == current_group:
      current_group.rows_in_group += 1
    else:
      row.group = group
      current_group = group
      current_group.rows_in_group = 1

  return table_data


def MakeRowData(
    art, columns, users_by_id, cell_factory_list, related_issues, config,
    context_for_all_issues):
  """Make a TableRow for use by EZT when rendering HTML table of results.

  Args:
    art: a project artifact PB
    columns: list of lower-case column names
    users_by_id: dictionary {user_id: UserView} with each UserView having
        a "display_name" member.
    cell_factory_list: list of functions that each create TableCell
        objects for a given column.
    related_issues: dict {issue_id: issue} of pre-fetched related issues.
    config: ProjectIssueConfig PB for the current project.
    context_for_all_issues: A dictionary of dictionaries containing values
        passed in to cell factory functions to create TableCells. Dictionary
        form: {issue_id: {'rank': issue_rank, 'issue_info': info_value, ..},
        issue_id: {'rank': issue_rank}, ..}

  Returns:
    A TableRow object for use by EZT to render a table of results.
  """
  if context_for_all_issues is None:
    context_for_all_issues = {}
  ordered_row_data = []
  non_col_labels = []
  label_values = collections.defaultdict(list)

  flattened_columns = set()
  for col in columns:
    if '/' in col:
      flattened_columns.update(col.split('/'))
    else:
      flattened_columns.add(col)

  # Group all "Key-Value" labels by key, and separate the "OneWord" labels.
  _AccumulateLabelValues(
      art.labels, flattened_columns, label_values, non_col_labels)

  _AccumulateLabelValues(
      art.derived_labels, flattened_columns, label_values,
      non_col_labels, is_derived=True)

  # Build up a list of TableCell objects for this row.
  for i, col in enumerate(columns):
    factory = cell_factory_list[i]
    kw = {
        'col': col,
        'users_by_id': users_by_id,
        'non_col_labels': non_col_labels,
        'label_values': label_values,
        'related_issues': related_issues,
        'config': config,
        }
    kw.update(context_for_all_issues.get(art.issue_id, {}))
    new_cell = factory(art, **kw)
    new_cell.col_index = i
    ordered_row_data.append(new_cell)

  return TableRow(ordered_row_data)


def _AccumulateLabelValues(
    labels, columns, label_values, non_col_labels, is_derived=False):
  """Parse OneWord and Key-Value labels for display in a list page.

  Args:
    labels: a list of label strings.
    columns: a list of column names.
    label_values: mutable dictionary {key: [value, ...]} of label values
        seen so far.
    non_col_labels: mutable list of OneWord labels seen so far.
    is_derived: true if these labels were derived via rules.

  Returns:
    Nothing.  But, the given label_values dictionary will grow to hold
    the values of the key-value labels passed in, and the non_col_labels
    list will grow to hold the OneWord labels passed in.  These are shown
    in label columns, and in the summary column, respectively
  """
  for label_name in labels:
    if '-' in label_name:
      parts = label_name.split('-')
      for pivot in range(1, len(parts)):
        column_name = '-'.join(parts[:pivot])
        value = '-'.join(parts[pivot:])
        column_name = column_name.lower()
        if column_name in columns:
          label_values[column_name].append((value, is_derived))
    else:
      non_col_labels.append((label_name, is_derived))


class TableRow(object):
  """A tiny auxiliary class to represent a row in an HTML table."""

  def __init__(self, cells):
    """Initialize the table row with the given data."""
    self.cells = cells
    # Used by MakeTableData for layout.
    self.idx = None
    self.group = None
    self.rows_in_group = None
    self.starred = None

  def __cmp__(self, other):
    """A row is == if each cell is == to the cells in the other row."""
    return cmp(self.cells, other.cells) if other else -1

  def DebugString(self):
    """Return a string that is useful for on-page debugging."""
    return 'TR(%s)' % self.cells


# TODO(jrobbins): also add unsortable... or change this to a list of operations
# that can be done.
CELL_TYPE_ID = 'ID'
CELL_TYPE_SUMMARY = 'summary'
CELL_TYPE_ATTR = 'attr'
CELL_TYPE_UNFILTERABLE = 'unfilterable'


class TableCell(object):
  """Helper class to represent a table cell when rendering using EZT."""

  # Should instances of this class be rendered with whitespace:nowrap?
  # Subclasses can override this constant.
  NOWRAP = ezt.boolean(True)

  def __init__(self, cell_type, explicit_values,
               derived_values=None, non_column_labels=None, align='',
               sort_values=True):
    """Store all the given data for later access by EZT."""
    self.type = cell_type
    self.align = align
    self.col_index = 0  # Is set afterward
    self.values = []
    if non_column_labels:
      self.non_column_labels = [
          template_helpers.EZTItem(value=v, is_derived=ezt.boolean(d))
          for v, d in non_column_labels]
    else:
      self.non_column_labels = []

    for v in (sorted(explicit_values) if sort_values else explicit_values):
      self.values.append(CellItem(v))

    if derived_values:
      for v in (sorted(derived_values) if sort_values else derived_values):
        self.values.append(CellItem(v, is_derived=True))

  def __cmp__(self, other):
    """A cell is == if each value is == to the values in the other cells."""
    return cmp(self.values, other.values) if other else -1

  def DebugString(self):
    return 'TC(%r, %r, %r)' % (
        self.type,
        [v.DebugString() for v in self.values],
        self.non_column_labels)


def CompositeTableCell(columns_to_combine, cell_factories):
  """Cell factory that combines multiple cells in a combined column."""

  class FactoryClass(TableCell):
    def __init__(self, art, config=None, **kw):
      TableCell.__init__(self, CELL_TYPE_UNFILTERABLE, [])

      for sub_col in columns_to_combine:
        kw['col'] = sub_col
        sub_factory = ChooseCellFactory(sub_col, cell_factories, config)
        sub_cell = sub_factory(art, **kw)
        self.non_column_labels.extend(sub_cell.non_column_labels)
        self.values.extend(sub_cell.values)
  return FactoryClass


class CellItem(object):
  """Simple class to display one part of a table cell's value, with style."""

  def __init__(self, item, is_derived=False):
    self.item = item
    self.is_derived = ezt.boolean(is_derived)

  def __cmp__(self, other):
    return cmp(self.item, other.item) if other else -1

  def DebugString(self):
    if self.is_derived:
      return 'CI(derived: %r)' % self.item
    else:
      return 'CI(%r)' % self.item


class TableCellKeyLabels(TableCell):
  """TableCell subclass specifically for showing user-defined label values."""

  def __init__(self, _art, col=None, label_values=None,  **_kw):
    label_value_pairs = label_values.get(col, [])
    explicit_values = [value for value, is_derived in label_value_pairs
                       if not is_derived]
    derived_values = [value for value, is_derived in label_value_pairs
                      if is_derived]
    TableCell.__init__(self, CELL_TYPE_ATTR, explicit_values,
                       derived_values=derived_values)


class TableCellProject(TableCell):
  """TableCell subclass for showing an artifact's project name."""

  def __init__(self, art, **_kw):
    TableCell.__init__(
        self, CELL_TYPE_ATTR, [art.project_name])


class TableCellStars(TableCell):
  """TableCell subclass for showing an artifact's star count."""

  def __init__(self, art, **_kw):
    TableCell.__init__(
        self, CELL_TYPE_ATTR, [art.star_count], align='right')


class TableCellSummary(TableCell):
  """TableCell subclass for showing an artifact's summary."""

  def __init__(self, art, non_col_labels=None, **_kw):
    TableCell.__init__(
        self, CELL_TYPE_SUMMARY, [art.summary],
        non_column_labels=non_col_labels)


class TableCellDate(TableCell):
  """TableCell subclass for showing any kind of date timestamp."""

  # Make instances of this class render with whitespace:nowrap.
  NOWRAP = ezt.boolean(True)

  def __init__(self, timestamp, days_only=False):
    values = []
    if timestamp:
      date_str = timestr.FormatRelativeDate(timestamp, days_only=days_only)
      if not date_str:
        date_str = timestr.FormatAbsoluteDate(timestamp)
      values = [date_str]

    TableCell.__init__(self, CELL_TYPE_UNFILTERABLE, values)


class TableCellCustom(TableCell):
  """Abstract TableCell subclass specifically for showing custom fields."""

  def __init__(self, art, col=None, users_by_id=None, config=None, **_kw):
    explicit_values = []
    derived_values = []
    for fv in art.field_values:
      # TODO(jrobbins): for cross-project search this could be a list.
      fd = tracker_bizobj.FindFieldDefByID(fv.field_id, config)
      if not fd:
        # TODO(jrobbins): This can happen if an issue with a custom
        # field value is moved to a different project.
        logging.warn('Issue ID %r has undefined field value %r',
                     art.issue_id, fv)
      elif fd.field_name.lower() == col:
        val = tracker_bizobj.GetFieldValue(fv, users_by_id)
        if fv.derived:
          derived_values.append(val)
        else:
          explicit_values.append(val)

    TableCell.__init__(self, CELL_TYPE_ATTR, explicit_values,
                       derived_values=derived_values)

  def ExtractValue(self, fv, _users_by_id):
    return 'field-id-%d-not-implemented-yet' % fv.field_id

# TODO(jrobbins): eliminate these subclasses and just use TableCellCustom
# for all custom fields, but have word wrap for strings.

class TableCellCustomInt(TableCellCustom):
  """TableCell subclass specifically for showing custom int fields."""
  pass


class TableCellCustomStr(TableCellCustom):
  """TableCell subclass specifically for showing custom str fields."""
  NOWRAP = ezt.boolean(False)


class TableCellCustomUser(TableCellCustom):
  """TableCell subclass specifically for showing custom user fields."""
  pass


class TableCellCustomDate(TableCellCustom):
  """TableCell subclass specifically for showing custom date fields."""
  pass

class TableCellCustomBool(TableCellCustom):
  """TableCell subclass specifically for showing custom int fields."""
  pass


_CUSTOM_FIELD_CELL_FACTORIES = {
    tracker_pb2.FieldTypes.ENUM_TYPE: TableCellKeyLabels,
    tracker_pb2.FieldTypes.INT_TYPE: TableCellCustomInt,
    tracker_pb2.FieldTypes.STR_TYPE: TableCellCustomStr,
    tracker_pb2.FieldTypes.USER_TYPE: TableCellCustomUser,
    tracker_pb2.FieldTypes.DATE_TYPE: TableCellCustomDate,
    tracker_pb2.FieldTypes.BOOL_TYPE: TableCellCustomBool,
}


def ChooseCellFactory(col, cell_factories, config):
  """Return the CellFactory to use for the given column."""
  if col in cell_factories:
    return cell_factories[col]

  if '/' in col:
    return CompositeTableCell(col.split('/'), cell_factories)

  fd = tracker_bizobj.FindFieldDef(col, config)
  if fd:
    return _CUSTOM_FIELD_CELL_FACTORIES[fd.field_type]

  return TableCellKeyLabels
