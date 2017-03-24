# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Convert a user's issue sorting directives into SQL clauses.

Some sort directives translate into simple ORDER BY column specifications.
Other sort directives require that a LEFT JOIN be done to bring in
relevant information that is then used in the ORDER BY.

Sorting based on strings can slow down the DB because long sort-keys
must be loaded into RAM, which means that fewer sort-keys fit into the
DB's sorting buffers at a time.  Also, Monorail defines the sorting
order of well-known labels and statuses based on the order in which
they are defined in the project's config.  So, we determine the sort order of
labels and status values before executing the query and then use the MySQL
FIELD() function to sort their IDs in the desired order, without sorting
strings.

For more info, see the "Sorting in Monorail" and "What makes Monorail Fast?"
design docs.
"""

import logging

from framework import sql
from proto import tracker_pb2


NATIVE_SORTABLE_FIELDS = [
    'id', 'stars', 'attachments', 'opened', 'closed', 'modified',
    'ownermodified', 'statusmodified', 'componentmodified',
    ]

FIELDS_TO_COLUMNS = {
    'id': 'local_id',
    'stars': 'star_count',
    'attachments': 'attachment_count',
    'ownermodified': 'owner_modified',
    'statusmodified': 'status_modified',
    'componentmodified': 'component_modified',
    }


def BuildSortClauses(
    sort_directives, harmonized_labels, harmonized_statuses,
    harmonized_fields):
  """Return LEFT JOIN and ORDER BY clauses needed to sort the results."""
  if not sort_directives:
    return [], []

  all_left_joins = []
  all_order_by = []
  for i, sd in enumerate(sort_directives):
    left_join_parts, order_by_parts = _OneSortDirective(
        i, sd, harmonized_labels, harmonized_statuses, harmonized_fields)
    all_left_joins.extend(left_join_parts)
    all_order_by.extend(order_by_parts)

  return all_left_joins, all_order_by


def _ProcessProjectSD(fmt):
  """Convert a 'project' sort directive into SQL."""
  left_joins = []
  order_by = [(fmt('Issue.project_id {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessReporterSD(fmt):
  """Convert a 'reporter' sort directive into SQL."""
  left_joins = [
      (fmt('User AS {alias} ON Issue.reporter_id = {alias}.user_id'), [])]
  order_by = [
      (fmt('ISNULL({alias}.email) {sort_dir}'), []),
      (fmt('{alias}.email {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessOwnerSD(fmt):
  """Convert a 'owner' sort directive into SQL."""
  left_joins = [
      (fmt('User AS {alias} ON (Issue.owner_id = {alias}.user_id OR '
           'Issue.derived_owner_id = {alias}.user_id)'), [])]
  order_by = [
      (fmt('ISNULL({alias}.email) {sort_dir}'), []),
      (fmt('{alias}.email {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessCcSD(fmt):
  """Convert a 'cc' sort directive into SQL."""
  # Note: derived cc's are included automatically.
  # Note: This sorts on the best Cc, not all Cc addresses.
  # Being more exact might require GROUP BY and GROUP_CONCAT().
  left_joins = [
      (fmt('Issue2Cc AS {alias} ON Issue.id = {alias}.issue_id '
           'LEFT JOIN User AS {alias}_user '
           'ON {alias}.cc_id = {alias}_user.user_id'), [])]
  order_by = [
      (fmt('ISNULL({alias}_user.email) {sort_dir}'), []),
      (fmt('{alias}_user.email {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessComponentSD(fmt):
  """Convert a 'component' sort directive into SQL."""
  # Note: derived components are included automatically.
  # Note: This sorts on the best component, not all of them.
  # Being more exact might require GROUP BY and GROUP_CONCAT().
  left_joins = [
      (fmt('Issue2Component AS {alias} ON Issue.id = {alias}.issue_id '
           'LEFT JOIN ComponentDef AS {alias}_component '
           'ON {alias}.component_id = {alias}_component.id'), [])]
  order_by = [
      (fmt('ISNULL({alias}_component.path) {sort_dir}'), []),
      (fmt('{alias}_component.path {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessSummarySD(fmt):
  """Convert a 'summary' sort directive into SQL."""
  left_joins = [
      (fmt('IssueSummary AS {alias} ON Issue.id = {alias}.issue_id'), [])]
  order_by = [(fmt('{alias}.summary {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessStatusSD(fmt, harmonized_statuses):
  """Convert a 'status' sort directive into SQL."""
  left_joins = []
  # Note: status_def_rows are already ordered by REVERSED rank.
  wk_status_ids = [
      stat_id for stat_id, rank, _ in harmonized_statuses
      if rank is not None]
  odd_status_ids = [
      stat_id for stat_id, rank, _ in harmonized_statuses
      if rank is None]
  wk_status_ph = sql.PlaceHolders(wk_status_ids)
  # Even though oddball statuses sort lexographically, use FIELD to determine
  # the order so that the database sorts ints rather than strings for speed.
  odd_status_ph = sql.PlaceHolders(odd_status_ids)

  order_by = []  # appended to below: both well-known and oddball can apply
  sort_col = ('IF(ISNULL(Issue.status_id), Issue.derived_status_id, '
              'Issue.status_id)')
  # Reverse sort by using rev_sort_dir because we want NULLs at the end.
  if wk_status_ids:
    order_by.append(
        (fmt('FIELD({sort_col}, {wk_status_ph}) {rev_sort_dir}',
             sort_col=sort_col, wk_status_ph=wk_status_ph),
         wk_status_ids))
  if odd_status_ids:
    order_by.append(
        (fmt('FIELD({sort_col}, {odd_status_ph}) {rev_sort_dir}',
             sort_col=sort_col, odd_status_ph=odd_status_ph),
         odd_status_ids))

  return left_joins, order_by


def _ProcessBlockedSD(fmt):
  """Convert a 'blocked' sort directive into SQL."""
  left_joins = [
      (fmt('IssueRelation AS {alias} ON Issue.id = {alias}.issue_id '
           'AND {alias}.kind = %s'),
       ['blockedon'])]
  order_by = [(fmt('ISNULL({alias}.dst_issue_id) {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessBlockedOnSD(fmt):
  """Convert a 'blockedon' sort directive into SQL."""
  left_joins = [
      (fmt('IssueRelation AS {alias} ON Issue.id = {alias}.issue_id '
           'AND {alias}.kind = %s'),
       ['blockedon'])]
  order_by = [(fmt('ISNULL({alias}.dst_issue_id) {sort_dir}'), []),
              (fmt('{alias}.dst_issue_id {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessBlockingSD(fmt):
  """Convert a 'blocking' sort directive into SQL."""
  left_joins = [
      (fmt('IssueRelation AS {alias} ON Issue.id = {alias}.dst_issue_id '
           'AND {alias}.kind = %s'),
       ['blockedon'])]
  order_by = [(fmt('ISNULL({alias}.issue_id) {sort_dir}'), []),
              (fmt('{alias}.issue_id {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessMergedIntoSD(fmt):
  """Convert a 'mergedinto' sort directive into SQL."""
  left_joins = [
      (fmt('IssueRelation AS {alias} ON Issue.id = {alias}.issue_id '
           'AND {alias}.kind = %s'),
       ['mergedinto'])]
  order_by = [(fmt('ISNULL({alias}.dst_issue_id) {sort_dir}'), []),
              (fmt('{alias}.dst_issue_id {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessOwnerLastVisitSD(fmt):
  """Convert a 'ownerlastvisit' sort directive into SQL."""
  left_joins = [
      (fmt('User AS {alias} ON (Issue.owner_id = {alias}.user_id OR '
           'Issue.derived_owner_id = {alias}.user_id)'), [])]
  order_by = [
      (fmt('ISNULL({alias}.last_visit_timestamp) {sort_dir}'), []),
      (fmt('{alias}.last_visit_timestamp {sort_dir}'), [])]
  return left_joins, order_by


def _ProcessCustomAndLabelSD(
    sd, harmonized_labels, harmonized_fields, alias, sort_dir, fmt):
  """Convert a label or custom field sort directive into SQL."""
  left_joins = []
  order_by = []

  fd_list = [fd for fd in harmonized_fields
             if fd.field_name.lower() == sd]
  if fd_list:
    int_left_joins, int_order_by = _CustomFieldSortClauses(
        fd_list, tracker_pb2.FieldTypes.INT_TYPE, 'int_value',
        alias, sort_dir)
    str_left_joins, str_order_by = _CustomFieldSortClauses(
        fd_list, tracker_pb2.FieldTypes.STR_TYPE, 'str_value',
        alias, sort_dir)
    user_left_joins, user_order_by = _CustomFieldSortClauses(
        fd_list, tracker_pb2.FieldTypes.USER_TYPE, 'user_id',
        alias, sort_dir)
    left_joins.extend(int_left_joins + str_left_joins + user_left_joins)
    order_by.extend(int_order_by + str_order_by + user_order_by)

  label_left_joinss, label_order_by = _LabelSortClauses(
      sd, harmonized_labels, fmt)
  left_joins.extend(label_left_joinss)
  order_by.extend(label_order_by)

  return left_joins, order_by


def _LabelSortClauses(sd, harmonized_labels, fmt):
  """Give LEFT JOIN and ORDER BY terms for label sort directives."""
  # Note: derived labels should work automatically.

  # label_def_rows are already ordered by REVERSED rank.
  wk_label_ids = [
      label_id for label_id, rank, label in harmonized_labels
      if label.lower().startswith('%s-' % sd) and rank is not None]
  odd_label_ids = [
      label_id for label_id, rank, label in harmonized_labels
      if label.lower().startswith('%s-' % sd) and rank is None]
  all_label_ids = wk_label_ids + odd_label_ids

  if all_label_ids:
    left_joins = [
        (fmt('Issue2Label AS {alias} ON Issue.id = {alias}.issue_id '
             'AND {alias}.label_id IN ({all_label_ph})',
             all_label_ph=sql.PlaceHolders(all_label_ids)),
         all_label_ids)]
  else:
    left_joins = []

  order_by = []
  # Reverse sort by using rev_sort_dir because we want NULLs at the end.
  if wk_label_ids:
    order_by.append(
        (fmt('FIELD({alias}.label_id, {wk_label_ph}) {rev_sort_dir}',
             wk_label_ph=sql.PlaceHolders(wk_label_ids)),
         wk_label_ids))
  if odd_label_ids:
    # Even though oddball labels sort lexographically, use FIELD to determine
    # the order so that the database sorts ints rather than strings for speed
    order_by.append(
        (fmt('FIELD({alias}.label_id, {odd_label_ph}) {rev_sort_dir}',
             odd_label_ph=sql.PlaceHolders(odd_label_ids)),
         odd_label_ids))

  return left_joins, order_by


def _CustomFieldSortClauses(
    fd_list, value_type, value_column, alias, sort_dir):
  """Give LEFT JOIN and ORDER BY terms for custom fields of the given type."""
  relevant_fd_list = [fd for fd in fd_list if fd.field_type == value_type]
  if not relevant_fd_list:
    return [], []

  field_ids_ph = sql.PlaceHolders(relevant_fd_list)
  def Fmt(sql_str):
    return sql_str.format(
        value_column=value_column, sort_dir=sort_dir,
        field_ids_ph=field_ids_ph, alias=alias + '_' + value_column)

  left_joins = [
      (Fmt('Issue2FieldValue AS {alias} ON Issue.id = {alias}.issue_id '
           'AND {alias}.field_id IN ({field_ids_ph})'),
       [fd.field_id for fd in relevant_fd_list])]

  if value_type == tracker_pb2.FieldTypes.USER_TYPE:
    left_joins.append(
        (Fmt('User AS {alias}_user ON {alias}.user_id = {alias}_user.user_id'),
         []))
    order_by = [
        (Fmt('ISNULL({alias}_user.email) {sort_dir}'), []),
        (Fmt('{alias}_user.email {sort_dir}'), [])]
  else:
    # Unfortunately, this sorts on the best field value, not all of them.
    order_by = [
        (Fmt('ISNULL({alias}.{value_column}) {sort_dir}'), []),
        (Fmt('{alias}.{value_column} {sort_dir}'), [])]

  return left_joins, order_by


_PROCESSORS = {
    'component': _ProcessComponentSD,
    'project': _ProcessProjectSD,
    'reporter': _ProcessReporterSD,
    'owner': _ProcessOwnerSD,
    'cc': _ProcessCcSD,
    'summary': _ProcessSummarySD,
    'blocked': _ProcessBlockedSD,
    'blockedon': _ProcessBlockedOnSD,
    'blocking': _ProcessBlockingSD,
    'mergedinto': _ProcessMergedIntoSD,
    'ownerlastvisit': _ProcessOwnerLastVisitSD,
    }


def _OneSortDirective(
    i, sd, harmonized_labels, harmonized_statuses, harmonized_fields):
  """Return SQL clauses to do the sorting for one sort directive."""
  alias = 'Sort%d' % i
  if sd.startswith('-'):
    sort_dir, rev_sort_dir = 'DESC', 'ASC'
    sd = sd[1:]
  else:
    sort_dir, rev_sort_dir = 'ASC', 'DESC'

  def Fmt(sql_str, **kwargs):
    return sql_str.format(
        sort_dir=sort_dir, rev_sort_dir=rev_sort_dir, alias=alias,
        sd=sd, col=FIELDS_TO_COLUMNS.get(sd, sd), **kwargs)

  if sd in NATIVE_SORTABLE_FIELDS:
    left_joins = []
    order_by = [(Fmt('Issue.{col} {sort_dir}'), [])]
    return left_joins, order_by

  elif sd in _PROCESSORS:
    proc = _PROCESSORS[sd]
    return proc(Fmt)

  elif sd == 'status':
    return _ProcessStatusSD(Fmt, harmonized_statuses)
  else:  # otherwise, it must be a field or label, or both
    return _ProcessCustomAndLabelSD(
        sd, harmonized_labels, harmonized_fields, alias, sort_dir, Fmt)
