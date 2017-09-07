# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for sorting lists of project artifacts.

This module exports the SortArtifacts function that does sorting of
Monorail business objects (e.g., an issue).  The sorting is done by
extracting relevant values from the PB using a dictionary of
accessor functions.

The desired sorting directives are specified in part of the user's
HTTP request.  This sort spec consists of the names of the columns
with optional minus signs to indicate descending sort order.

The tool configuration object also affects sorting.  When sorting by
key-value labels, the well-known labels are considered to come
before any non-well-known labels, and those well-known labels sort in
the order in which they are defined in the tool config PB.
"""

import logging

import settings
from framework import framework_constants
from proto import tracker_pb2
from services import caches
from tracker import tracker_bizobj


class DescendingValue(object):
  """A wrapper which reverses the sort order of values."""

  @classmethod
  def MakeDescendingValue(cls, obj):
    """Make a value that sorts in the reverse order as obj."""
    if isinstance(obj, int):
      return -obj
    if obj == MAX_STRING:
      return MIN_STRING
    if obj == MIN_STRING:
      return MAX_STRING
    if isinstance(obj, list):
      return [cls.MakeDescendingValue(item) for item in reversed(obj)]
    return DescendingValue(obj)

  def __init__(self, val):
    self.val = val

  def __cmp__(self, other):
    """Return -1, 0, or 1 base on the reverse of the normal sort order."""
    if isinstance(other, DescendingValue):
      return cmp(other.val, self.val)
    else:
      return cmp(other, self.val)

  def __repr__(self):
    return 'DescendingValue(%r)' % self.val


# A string that sorts after every other string, and one that sorts before them.
MAX_STRING = '~~~'
MIN_STRING = DescendingValue(MAX_STRING)


# RAMCache {issue_id: {column_name: sort_key, ...}, ...}
art_values_cache = None


def InitializeArtValues(services):
  global art_values_cache
  art_values_cache = caches.RamCache(
      services.cache_manager, 'issue', max_size=settings.issue_cache_max_size)


def InvalidateArtValuesKeys(cnxn, keys):
  art_values_cache.InvalidateKeys(cnxn, keys)


def SortArtifacts(
    mr, artifacts, config, accessors, postprocessors, users_by_id=None,
    tie_breakers=None):
  """Return a list of artifacts sorted by the user's sort specification.

  In the following, an "accessor" is a function(art) -> [field_value, ...].

  Args:
    mr: commonly used info parsed from the request, including query.
    artifacts: an unsorted list of project artifact PBs.
    config: Project config PB instance that defines the sort order for
        labels and statuses in this project.
    accessors: dict {column_name: accessor} to get values from the artifacts.
    postprocessors: dict {column_name: postprocessor} to get user emails
        and timestamps.
    users_by_id: optional dictionary {user_id: user_view,...} for all users
        who participate in the list of artifacts.
    tie_breakers: list of column names to add to the end of the sort
        spec if they are not already somewhere in the sort spec.

  Returns:
    A sorted list of artifacts.

  Note: if username_cols is supplied, then users_by_id should be too.

  The approach to sorting is to construct a comprehensive sort key for
  each artifact. To create the sort key, we (a) build lists with a
  variable number of fields to sort on, and (b) allow individual
  fields to be sorted in descending order.  Even with the time taken
  to build the sort keys, calling sorted() with the key seems to be
  faster overall than doing multiple stable-sorts or doing one sort
  using a multi-field comparison function.
  """
  sort_directives = ComputeSortDirectives(mr, config, tie_breakers=tie_breakers)

  # Build a list of accessors that will extract sort keys from the issues.
  accessor_pairs = [
      (sd, _MakeCombinedSortKeyAccessor(
          sd, config, accessors, postprocessors, users_by_id))
      for sd in sort_directives]

  def SortKey(art):
    """Make a sort_key for the given artifact, used by sorted() below."""
    if art_values_cache.HasItem(art.issue_id):
      art_values = art_values_cache.GetItem(art.issue_id)
    else:
      art_values = {}

    sort_key = []
    for sd, accessor in accessor_pairs:
      if sd not in art_values:
        art_values[sd] = accessor(art)
      sort_key.append(art_values[sd])

    art_values_cache.CacheItem(art.issue_id, art_values)
    return sort_key

  return sorted(artifacts, key=SortKey)


def ComputeSortDirectives(mr, config, tie_breakers=None):
  """Return a list with sort directives to be used in sorting.

  Args:
    mr: commonly used info parsed from the request, including query.
    config: Project config PB instance that defines the sort order for
        labels and statuses in this project.
    tie_breakers: list of column names to add to the end of the sort
        spec if they are not already somewhere in the sort spec.

  Returns:
    A list of lower-case column names, each one may have a leading
    minus-sign.
  """
  # Prepend the end-user's sort spec to any project default sort spec.
  if tie_breakers is None:
    tie_breakers = ['id']
  sort_spec = '%s %s %s' % (
      mr.group_by_spec, mr.sort_spec, config.default_sort_spec)
  # Sort specs can have interfering sort orders, so remove any duplicates.
  field_names = set()
  sort_directives = []
  for sort_directive in sort_spec.lower().split():
    field_name = sort_directive.lstrip('-')
    if field_name not in field_names:
      sort_directives.append(sort_directive)
      field_names.add(field_name)

  # Add in the project name so that the overall ordering is completely
  # defined in cross-project search. Otherwise, issues jump up and
  # down on each reload of the same query, and prev/next links get
  # messed up.  It's a no-op in single projects.
  if 'project' not in sort_directives:
    sort_directives.append('project')

  for tie_breaker in tie_breakers:
    if tie_breaker not in sort_directives:
      sort_directives.append(tie_breaker)

  return sort_directives


def _MakeCombinedSortKeyAccessor(
    sort_directive, config, accessors, postprocessors, users_by_id):
  """Return an accessor that extracts a sort key for a UI table column.

  Args:
    sort_directive: string with column name and optional leading minus sign,
        for combined columns, it may have slashes, e.g., "-priority/pri".
    config: ProjectIssueConfig instance that defines the sort order for
        labels and statuses in this project.
    accessors: dictionary of (column_name -> accessor) to get values
        from the artifacts.
    postprocessors: dict {column_name: postprocessor} to get user emails
        and timestamps.
    users_by_id: dictionary {user_id: user_view,...} for all users
        who participate in the list of artifacts (e.g., owners, reporters, cc).

  Returns:
    A list of accessor functions that can be applied to an issue to extract
    the relevant sort key value.

  The strings for status and labels are converted to lower case in
  this method so that they sort like case-insensitive enumerations.
  Any component-specific field of the artifact is sorted according to the
  value returned by the accessors defined in that component.  Those
  accessor functions should lower case string values for fields where
  case-insensitive sorting is desired.
  """
  if sort_directive.startswith('-'):
    combined_col_name = sort_directive[1:]
    descending = True
  else:
    combined_col_name = sort_directive
    descending = False

  wk_labels = [wkl.label for wkl in config.well_known_labels]
  accessors = [
      _MakeSingleSortKeyAccessor(
          col_name, config, accessors, postprocessors, users_by_id, wk_labels)
      for col_name in combined_col_name.split('/')]

  # The most common case is that we sort on a single column, like "priority".
  if len(accessors) == 1:
    return _MaybeMakeDescending(accessors[0], descending)

  # Less commonly, we are sorting on a combined column like "priority/pri".
  def CombinedAccessor(art):
    """Flatten and sort the values for each column in a combined column."""
    key_part = []
    for single_accessor in accessors:
      value = single_accessor(art)
      if isinstance(value, list):
        key_part.extend(value)
      else:
        key_part.append(value)
    return sorted(key_part)

  return _MaybeMakeDescending(CombinedAccessor, descending)


def _MaybeMakeDescending(accessor, descending):
  """If descending is True, return a new function that reverses accessor."""
  if not descending:
    return accessor

  def DescendingAccessor(art):
    asc_value = accessor(art)
    return DescendingValue.MakeDescendingValue(asc_value)

  return DescendingAccessor


def _MakeSingleSortKeyAccessor(
    col_name, config, accessors, postprocessors, users_by_id, wk_labels):
  """Return an accessor function for a single simple UI column."""
  # Case 1. Handle built-in fields: status, component.
  if col_name == 'status':
    wk_statuses = [wks.status for wks in config.well_known_statuses]
    return _IndexOrLexical(wk_statuses, accessors[col_name])

  if col_name == 'component':
    comp_defs = sorted(config.component_defs, key=lambda cd: cd.path.lower())
    comp_ids = [cd.component_id for cd in comp_defs]
    return _IndexListAccessor(comp_ids, accessors[col_name])

  # Case 2. Any other defined accessor functions.
  if col_name in accessors:
    if postprocessors and col_name in postprocessors:
      # sort users by email address or timestamp rather than user ids.
      return _MakeAccessorWithPostProcessor(
          users_by_id, accessors[col_name], postprocessors[col_name])
    else:
      return accessors[col_name]

  # Case 3. Anything else is assumed to be a label prefix or custom field.
  fd_list = [
      fd for fd in config.field_defs
      if (fd.field_name.lower() == col_name and
          fd.field_type != tracker_pb2.FieldTypes.ENUM_TYPE)]
  return _IndexOrLexicalList(
      wk_labels, fd_list, col_name, users_by_id)


IGNORABLE_INDICATOR = -1


def _PrecomputeSortIndexes(values, col_name):
  """Precompute indexes of strings in the values list for fast lookup later."""
  # Make a dictionary that immediately gives us the index of any value
  # in the list, and also add the same values in all-lower letters.  In
  # the case where two values differ only by case, the later value wins,
  # which is fine.
  indexes = {}
  if col_name:
    prefix = col_name + '-'
  else:
    prefix = ''
  for idx, val in enumerate(values):
    if val.lower().startswith(prefix):
      indexes[val] = idx
      indexes[val.lower()] = idx
    else:
      indexes[val] = IGNORABLE_INDICATOR
      indexes[val.lower()] = IGNORABLE_INDICATOR

  return indexes


def _MakeAccessorWithPostProcessor(users_by_id, base_accessor, postprocessor):
  """Make an accessor that returns a list of user_view properties for sorting.

  Args:
    users_by_id: dictionary {user_id: user_view, ...} for all participants
        in the entire list of artifacts.
    base_accessor: an accessor function f(artifact) -> user_id.
    postprocessor: function f(user_view) -> single sortable value.

  Returns:
    An accessor f(artifact) -> value that can be used in sorting
    the decorated list.
  """

  def Accessor(art):
    """Return a user edit name for the given artifact's base_accessor."""
    id_or_id_list = base_accessor(art)
    if isinstance(id_or_id_list, list):
      values = [postprocessor(users_by_id[user_id])
                for user_id in id_or_id_list]
    else:
      values = [postprocessor(users_by_id[id_or_id_list])]

    return sorted(values) or MAX_STRING

  return Accessor


def _MakeColumnAccessor(col_name):
  """Make an accessor for an issue's labels that have col_name as a prefix.

  Args:
    col_name: string column name.

  Returns:
    An accessor that can be applied to an artifact to return a list of
    labels that have col_name as a prefix.

  For example, _MakeColumnAccessor('priority')(issue) could result in
  [], or ['priority-high'], or a longer list for multi-valued labels.
  """
  prefix = col_name + '-'

  def Accessor(art):
    """Return a list of label values on the given artifact."""
    result = [label.lower() for label in tracker_bizobj.GetLabels(art)
              if label.lower().startswith(prefix)]
    return result

  return Accessor


def _IndexOrLexical(wk_values, base_accessor):
  """Return an accessor to score an artifact based on a user-defined ordering.

  Args:
    wk_values: a list of well-known status values from the config.
    base_accessor: function that gets a field from a given issue.

  Returns:
    An accessor that can be applied to an issue to return a suitable
    sort key.

  For example, when used to sort issue statuses, these accessors return an
  integer for well-known statuses, a string for odd-ball statuses, and an
  extreme value key for issues with no status.  That causes issues to appear
  in the expected order with odd-ball issues sorted lexicographically after
  the ones with well-known status values, and issues with no defined status at
  the very end.
  """
  well_known_value_indexes = _PrecomputeSortIndexes(wk_values, '')

  def Accessor(art):
    """Custom-made function to return a specific value of any issue."""
    value = base_accessor(art)
    if not value:
      # Undefined values sort last.
      return MAX_STRING

    try:
      # Well-known values sort by index.  Ascending sorting has positive ints
      # in well_known_value_indexes.
      return well_known_value_indexes[value]
    except KeyError:
      # Odd-ball values after well-known and lexicographically.
      return value.lower()

  return Accessor


def _IndexListAccessor(wk_values, base_accessor):
  """Return an accessor to score an artifact based on a user-defined ordering.

  Args:
    wk_values: a list of well-known values from the config.
    base_accessor: function that gets a field from a given issue.

  Returns:
    An accessor that can be applied to an issue to return a suitable
    sort key.
  """
  well_known_value_indexes = {
    val: idx for idx, val in enumerate(wk_values)}

  def Accessor(art):
    """Custom-made function to return a specific value of any issue."""
    values = base_accessor(art)
    if not values:
      # Undefined values sort last.
      return MAX_STRING

    indexes = [well_known_value_indexes.get(val, MAX_STRING) for val in values]
    return sorted(indexes)

  return Accessor


def _IndexOrLexicalList(wk_values, fd_list, col_name, users_by_id):
  """Return an accessor to score an artifact based on a user-defined ordering.

  Args:
    wk_values: A list of well-known labels from the config.
    fd_list: list of FieldDef PBs that match the column name.  These might not
        all have the same field_type.  Enum-type field are not included.
    col_name: lowercase string name of the column that will be sorted on.
    users_by_id: A dictionary {user_id: user_view}.

  Returns:
    An accessor that can be applied to an issue to return a suitable
    sort key.
  """
  well_known_value_indexes = _PrecomputeSortIndexes(wk_values, col_name)

  def Accessor(art):
    """Custom-made function to return a sort value for any issue."""
    idx_or_lex_list = (
        _SortableFieldValues(art, fd_list, users_by_id) +
        _SortableLabelValues(art, col_name, well_known_value_indexes))
    if not idx_or_lex_list:
      return MAX_STRING  # issues with no value sort to the end of the list.
    return sorted(idx_or_lex_list)

  return Accessor


def _SortableFieldValues(art, fd_list, users_by_id):
  """Return a list of field values relevant to one UI table column."""
  sortable_value_list = []
  for fd in fd_list:
    for fv in art.field_values:
      if fv.field_id == fd.field_id:
        sortable_value_list.append(
            tracker_bizobj.GetFieldValue(fv, users_by_id))

  return sortable_value_list


def _SortableLabelValues(art, col_name, well_known_value_indexes):
  """Return a list of ints and strings for labels relevant to one UI column."""
  sortable_value_list = []
  for label in tracker_bizobj.GetLabels(art):
    idx_or_lex = well_known_value_indexes.get(label)
    if idx_or_lex == IGNORABLE_INDICATOR:
      continue  # Label is known to not have the desired prefix.
    if idx_or_lex is None:
      if '-' not in label:
        # Skip an irrelevant OneWord label and remember to ignore it later.
        well_known_value_indexes[label] = IGNORABLE_INDICATOR
        continue
      key, value = label.lower().split('-', 1)
      if key == col_name:
        # Label is a key-value label with an odd-ball value, remember it
        idx_or_lex = value
        well_known_value_indexes[label] = value
      else:
        # Label was a key-value label that is not relevant to this column.
        # Remember to ignore it later.
        well_known_value_indexes[label] = IGNORABLE_INDICATOR
        continue

    sortable_value_list.append(idx_or_lex)

  return sortable_value_list
