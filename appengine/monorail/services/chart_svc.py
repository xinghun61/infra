# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A service for querying data for charts.

Functions for querying the IssueSnapshot table and associated join tables.
"""

from framework import sql
from search import search_helpers


ISSUESNAPSHOT_TABLE_NAME = 'IssueSnapshot'


class ChartService(object):
  """Class for querying chart data."""

  def __init__(self):
    self.issuesnapshot_tbl = sql.SQLTableManager(ISSUESNAPSHOT_TABLE_NAME)

  def QueryIssueSnapshots(self, cnxn, config_svc, unixtime, bucketby,
                          effective_ids, project, perms, label_prefix=None):
    """Queries historical issue counts grouped by label or component.

    Args:
      cnxn: A MonorailConnection instance.
      config_svc: A ConfigService instance.
      unixtime: An integer representing the Unix time in seconds.
      bucketby: Which dimension to group by. Either 'label' or 'component'.
      effective_ids: The effective User IDs associated with the current user.
      project: A project object representing the current project.
      perms: A permissions object associated with the current user.
      label_prefix: Required when bucketby is 'label.' Will limit the query to
        only labels with the specified prefix (for example 'Pri').

    Returns:
      A list of pairs with values:
        (label or component name,
         number of occurrences for the given timestamp)
    """
    restricted_label_ids = search_helpers.GetPersonalAtRiskLabelIDs(
      cnxn, None, config_svc, effective_ids, project, perms)

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

    # TODO(jeffcarp, monorail:3534): Add support for user's query params.
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

    if bucketby == 'component':
      cols = ['Comp.path', 'COUNT(DISTINCT(IssueSnapshot.issue_id))']
      left_joins.extend([
        (('IssueSnapshot2Component AS Is2c ON'
          ' Is2c.issuesnapshot_id = IssueSnapshot.id'), []),
        ('ComponentDef AS Comp ON Comp.id = Is2c.component_id', []),
      ])
      group_by = ['Comp.path']
    elif bucketby == 'label':
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
    else:
      raise ValueError('`bucketby` must be in (component, label)')

    return self.issuesnapshot_tbl.Select(cnxn, cols=cols,
      left_joins=left_joins, where=where, group_by=group_by)
