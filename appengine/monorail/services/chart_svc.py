# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A service for querying data for charts.

Functions for querying the IssueSnapshot table and associated join tables.
"""

import logging
import settings
import time

from framework import framework_helpers
from framework import sql
from search import search_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from search import query2ast
from search import ast2select
from search import ast2ast


ISSUESNAPSHOT_TABLE_NAME = 'IssueSnapshot'
ISSUESNAPSHOT2CC_TABLE_NAME = 'IssueSnapshot2Cc'
ISSUESNAPSHOT2COMPONENT_TABLE_NAME = 'IssueSnapshot2Component'
ISSUESNAPSHOT2LABEL_TABLE_NAME = 'IssueSnapshot2Label'

ISSUESNAPSHOT_COLS = ['id', 'issue_id', 'shard', 'project_id', 'local_id',
    'reporter_id', 'owner_id', 'status_id', 'period_start', 'period_end',
    'is_open']
ISSUESNAPSHOT2CC_COLS = ['issuesnapshot_id', 'cc_id']
ISSUESNAPSHOT2COMPONENT_COLS = ['issuesnapshot_id', 'component_id']
ISSUESNAPSHOT2LABEL_COLS = ['issuesnapshot_id', 'label_id']


class ChartService(object):
  """Class for querying chart data."""

  def __init__(self, config_service):
    """Constructor for ChartService.

    Args:
      config_service (ConfigService): An instance of ConfigService.
    """
    self.config_service = config_service

    # Set up SQL table objects.
    self.issuesnapshot_tbl = sql.SQLTableManager(ISSUESNAPSHOT_TABLE_NAME)
    self.issuesnapshot2cc_tbl = sql.SQLTableManager(
        ISSUESNAPSHOT2CC_TABLE_NAME)
    self.issuesnapshot2component_tbl = sql.SQLTableManager(
        ISSUESNAPSHOT2COMPONENT_TABLE_NAME)
    self.issuesnapshot2label_tbl = sql.SQLTableManager(
        ISSUESNAPSHOT2LABEL_TABLE_NAME)

  def QueryIssueSnapshots(self, cnxn, services, unixtime, effective_ids,
                          project, perms, group_by=None, label_prefix=None,
                          query=None, canned_query=None):
    """Queries historical issue counts grouped by label or component.

    Args:
      cnxn: A MonorailConnection instance.
      services: A Services instance.
      unixtime: An integer representing the Unix time in seconds.
      effective_ids: The effective User IDs associated with the current user.
      project: A project object representing the current project.
      perms: A permissions object associated with the current user.
      group_by (str, optional): Which dimension to group by. Values can
        be 'label', 'component', or None, in which case no grouping will
        be applied.
      label_prefix: Required when group_by is 'label.' Will limit the query to
        only labels with the specified prefix (for example 'Pri').
      query (str, optional): A query string from the request to apply to
        the snapshot query.
      canned_query (str, optional): Derived from the can= query parameter,
        applied to the query scope.

    Returns:
      1. A dict of {'2nd dimension or "total"': number of occurences}.
      2. A list of any unsupported query conditions in query.
    """
    if query:
      project_config = services.config.GetProjectConfig(cnxn,
          project.project_id)
      try:
        query_left_joins, query_where, unsupported_conds = self._QueryToWhere(
            cnxn, services, project_config, query, canned_query, project)
      except ast2select.NoPossibleResults:
        return {}, ['Invalid query.']

    else:
      unsupported_conds = []

    restricted_label_ids = search_helpers.GetPersonalAtRiskLabelIDs(
      cnxn, None, self.config_service, effective_ids, project, perms)

    left_joins = [
      ('Issue ON IssueSnapshot.issue_id = Issue.id', []),
    ]

    if restricted_label_ids:
      left_joins.append(
        (('Issue2Label AS Forbidden_label'
          ' ON Issue.id = Forbidden_label.issue_id'
          ' AND Forbidden_label.label_id IN (%s)' % (
            sql.PlaceHolders(restricted_label_ids)
        )), restricted_label_ids))

    if effective_ids:
      left_joins.append(
        ('Issue2Cc AS I2cc'
         ' ON Issue.id = I2cc.issue_id'
         ' AND I2cc.cc_id IN (%s)' % sql.PlaceHolders(effective_ids),
         effective_ids))

    # TODO(jeffcarp): Handle case where there are issues with no labels.
    where = [
      ('IssueSnapshot.period_start <= %s', [unixtime]),
      ('IssueSnapshot.period_end > %s', [unixtime]),
      ('IssueSnapshot.project_id = %s', [project.project_id]),
      ('IssueSnapshot.is_open = %s', [True]),
      ('Issue.is_spam = %s', [False]),
      ('Issue.deleted = %s', [False]),
    ]

    forbidden_label_clause = 'Forbidden_label.label_id IS NULL'
    if effective_ids:
      if restricted_label_ids:
        forbidden_label_clause = ' OR %s' % forbidden_label_clause
      else:
        forbidden_label_clause =  ''

      where.append(
        ((
          '(Issue.reporter_id IN (%s)'
          ' OR Issue.owner_id IN (%s)'
          ' OR I2cc.cc_id IS NOT NULL'
          '%s)'
        ) % (
          sql.PlaceHolders(effective_ids), sql.PlaceHolders(effective_ids),
          forbidden_label_clause
        ),
          list(effective_ids) + list(effective_ids)
        ))
    else:
      where.append((forbidden_label_clause, []))

    if group_by == 'component':
      cols = ['Comp.path', 'COUNT(DISTINCT(IssueSnapshot.issue_id))']
      left_joins.extend([
        (('IssueSnapshot2Component AS Is2c ON'
          ' Is2c.issuesnapshot_id = IssueSnapshot.id'), []),
        ('ComponentDef AS Comp ON Comp.id = Is2c.component_id', []),
      ])
      group_by = ['Comp.path']
    elif group_by == 'label':
      cols = ['Lab.label', 'COUNT(DISTINCT(IssueSnapshot.issue_id))']
      left_joins.extend([
        (('IssueSnapshot2Label AS Is2l'
          ' ON Is2l.issuesnapshot_id = IssueSnapshot.id'), []),
        ('LabelDef AS Lab ON Lab.id = Is2l.label_id', []),
      ])

      if not label_prefix:
        raise ValueError('`label_prefix` required when grouping by label.')

      # TODO(jeffcarp): If LookupIDsOfLabelsMatching() is called on output,
      # ensure regex is case-insensitive.
      where.append(('LOWER(Lab.label) LIKE %s', [label_prefix.lower() + '-%']))
      group_by = ['Lab.label']
    elif not group_by:
      cols = ['COUNT(DISTINCT(IssueSnapshot.issue_id))']
    else:
      raise ValueError('`group_by` must be label, component, or None.')

    if query:
      left_joins.extend(query_left_joins)
      where.extend(query_where)

    promises = []
    for shard_id in range(settings.num_logical_shards):
      thread_where = where + [('IssueSnapshot.shard = %s', [shard_id])]
      p = framework_helpers.Promise(self.issuesnapshot_tbl.Select,
        cnxn=cnxn, cols=cols, left_joins=left_joins, where=thread_where,
        group_by=group_by, shard_id=shard_id)
      promises.append(p)

    shard_values_dict = {}
    for promise in promises:
      # Wait for each query to complete and add it to the dict.
      shard_values = promise.WaitAndGetValue()
      if not shard_values:
        continue
      if group_by:
        for name, count in shard_values:
          shard_values_dict.setdefault(name, 0)
          shard_values_dict[name] += count
      else:
        shard_values_dict.setdefault('total', 0)
        shard_values_dict['total'] += shard_values[0][0]

    unsupported_field_names = list(set([
        field.field_name
        for cond in unsupported_conds
        for field in cond.field_defs
    ]))

    return shard_values_dict, unsupported_field_names

  def StoreIssueSnapshots(self, cnxn, issues, commit=True):
    """Adds an IssueSnapshot and updates the previous one for each issue."""
    for issue in issues:
      right_now = self._currentTime()

      # Look for an existing (latest) IssueSnapshot with this issue_id.
      previous_snapshots = self.issuesnapshot_tbl.Select(
          cnxn, cols=ISSUESNAPSHOT_COLS,
          issue_id=issue.issue_id,
          limit=1,
          order_by=[('period_start DESC', [])])

      if len(previous_snapshots) > 0:
        previous_snapshot_id = previous_snapshots[0][0]
        logging.info('Found previous IssueSnapshot with id: %s',
          previous_snapshot_id)

        # Update previous snapshot's end time to right now.
        delta = { 'period_end': right_now }
        where = [('IssueSnapshot.id = %s', [previous_snapshot_id])]
        self.issuesnapshot_tbl.Update(cnxn, delta, commit=commit, where=where)

      config = self.config_service.GetProjectConfig(cnxn, issue.project_id)
      period_end = settings.maximum_snapshot_period_end
      is_open = tracker_helpers.MeansOpenInProject(
        tracker_bizobj.GetStatus(issue), config)
      shard = issue.issue_id % settings.num_logical_shards
      status = tracker_bizobj.GetStatus(issue)
      status_id = self.config_service.LookupStatusID(
          cnxn, issue.project_id, status) or None
      owner_id = tracker_bizobj.GetOwnerId(issue) or None

      issuesnapshot_rows = [(issue.issue_id, shard, issue.project_id,
        issue.local_id, issue.reporter_id, owner_id, status_id, right_now,
        period_end, is_open)]

      ids = self.issuesnapshot_tbl.InsertRows(
          cnxn, ISSUESNAPSHOT_COLS[1:],
          issuesnapshot_rows,
          replace=True, commit=commit,
          return_generated_ids=True)
      issuesnapshot_id = ids[0]

      # Add all labels to IssueSnapshot2Label.
      label_rows = [
          (issuesnapshot_id,
           self.config_service.LookupLabelID(cnxn, issue.project_id, label))
          for label in tracker_bizobj.GetLabels(issue)
      ]
      self.issuesnapshot2label_tbl.InsertRows(
          cnxn, ISSUESNAPSHOT2LABEL_COLS,
          label_rows, replace=True, commit=commit)

      # Add all CCs to IssueSnapshot2Cc.
      cc_rows = [
        (issuesnapshot_id, cc_id)
        for cc_id in tracker_bizobj.GetCcIds(issue)
      ]
      self.issuesnapshot2cc_tbl.InsertRows(
          cnxn, ISSUESNAPSHOT2CC_COLS,
          cc_rows,
          replace=True, commit=commit)

      # Add all components to IssueSnapshot2Component.
      component_rows = [
        (issuesnapshot_id, component_id)
        for component_id in issue.component_ids
      ]
      self.issuesnapshot2component_tbl.InsertRows(
          cnxn, ISSUESNAPSHOT2COMPONENT_COLS,
          component_rows,
          replace=True, commit=commit)

      # Add all components to IssueSnapshot2Hotlist.
      # This is raw SQL to obviate passing FeaturesService down through
      #   the call stack wherever this function is called.
      # TODO(jrobbins): sort out dependencies between service classes.
      cnxn.Execute('''
        INSERT INTO IssueSnapshot2Hotlist (issuesnapshot_id, hotlist_id)
        SELECT %s, hotlist_id FROM Hotlist2Issue WHERE issue_id = %s
      ''', [issuesnapshot_id, issue.issue_id])

  def _currentTime(self):
    """This is a separate method so it can be mocked by tests."""
    return time.time()

  def _QueryToWhere(self, cnxn, services, project_config, query, canned_query,
                    project):
    """Parses a query string into LEFT JOIN and WHERE conditions.

    Args:
      cnxn: A MonorailConnection instance.
      services: A Services instance.
      project_config: The configuration for the given project.
      query (string): The query to parse.
      canned_query (string): The supplied canned query.
      project: The current project.

    Returns:
      1. A list of LEFT JOIN clauses for the SQL query.
      2. A list of WHERE clases for the SQL query.
      3. A list of query conditions that are unsupported with snapshots.
    """
    if not query:
      return [], [], []

    if canned_query:
      scope = canned_query
    else:
      scope = ''

    query_ast = query2ast.ParseUserQuery(query, scope,
        query2ast.BUILTIN_ISSUE_FIELDS, project_config)
    query_ast = ast2ast.PreprocessAST(cnxn, query_ast, [project.project_id],
        services, project_config)
    left_joins, where, unsupported = ast2select.BuildSQLQuery(query_ast,
        snapshot_mode=True)

    return left_joins, where, unsupported
