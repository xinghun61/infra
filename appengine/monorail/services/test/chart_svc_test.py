# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for chart_svc module."""

import datetime
import mox
import re
import settings
import unittest

from google.appengine.ext import testbed

from services import chart_svc
from services import config_svc
from services import service_manager
from framework import permissions
from framework import sql
from proto import ast_pb2
from proto import tracker_pb2
from search import search_helpers
from testing import fake
from tracker import tracker_bizobj


def MakeChartService(my_mox, config):
  chart_service = chart_svc.ChartService(config)
  for table_var in ['issuesnapshot_tbl', 'issuesnapshot2label_tbl',
      'issuesnapshot2component_tbl', 'issuesnapshot2cctbl', 'labeldef_tbl']:
    setattr(chart_service, table_var, my_mox.CreateMock(sql.SQLTableManager))
  return chart_service


class ChartServiceTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.services = service_manager.Services()
    self.config_service = fake.ConfigService()
    self.services.config = self.config_service
    self.services.chart = MakeChartService(self.mox, self.config_service)
    self.mox.StubOutWithMock(self.services.chart, '_QueryToWhere')
    self.mox.StubOutWithMock(search_helpers, 'GetPersonalAtRiskLabelIDs')
    self.mox.StubOutWithMock(settings, 'num_logical_shards')
    settings.num_logical_shards = 1
    self.mox.StubOutWithMock(self.services.chart, '_currentTime')

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def _verifySQL(self, cols, left_joins, where, group_by=None):
    for col in cols:
      self.assertTrue(sql._IsValidColumnName(col))
    for join_str, _ in left_joins:
      self.assertTrue(sql._IsValidJoin(join_str))
    for where_str, _ in where:
      self.assertTrue(sql._IsValidWhereCond(where_str))
    if group_by:
      for groupby_str in group_by:
        self.assertTrue(sql._IsValidGroupByTerm(groupby_str))

  def testQueryIssueSnapshots_InvalidGroupBy(self):
    """Make sure the `group_by` argument is checked."""
    project = fake.Project(project_id=789)
    perms = permissions.USER_PERMISSIONSET
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
        self.config_service, [10L, 20L], project,
        perms).AndReturn([91, 81])

    self.mox.ReplayAll()
    with self.assertRaises(ValueError):
      self.services.chart.QueryIssueSnapshots(self.cnxn, self.services,
          unixtime=1514764800, effective_ids=[10L, 20L], project=project,
          perms=perms, group_by='rutabaga', label_prefix='rutabaga')
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_NoLabelPrefix(self):
    """Make sure the `label_prefix` argument is required."""
    project = fake.Project(project_id=789)
    perms = permissions.USER_PERMISSIONSET
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
        self.config_service, [10L, 20L], project,
        perms).AndReturn([91, 81])

    self.mox.ReplayAll()
    with self.assertRaises(ValueError):
      self.services.chart.QueryIssueSnapshots(self.cnxn, self.services,
          unixtime=1514764800, effective_ids=[10L, 20L], project=project,
          perms=perms, group_by='label')
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_Components(self):
    """Test a burndown query from a regular user grouping by component."""
    project = fake.Project(project_id=789)
    perms = permissions.PermissionSet(['BarPerm'])
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
        self.config_service, [10L, 20L], project,
        perms).AndReturn([91, 81])

    cols = [
      'Comp.path',
      'COUNT(DISTINCT(IssueSnapshot.issue_id))',
    ]
    left_joins = [
      ('Issue ON IssueSnapshot.issue_id = Issue.id', []),
      ('Issue2Label AS Forbidden_label'
       ' ON Issue.id = Forbidden_label.issue_id'
       ' AND Forbidden_label.label_id IN (%s,%s)', [91, 81]),
      ('Issue2Cc AS I2cc'
       ' ON Issue.id = I2cc.issue_id'
       ' AND I2cc.cc_id IN (%s,%s)', [10L, 20L]),
      ('IssueSnapshot2Component AS Is2c'
       ' ON Is2c.issuesnapshot_id = IssueSnapshot.id', []),
      ('ComponentDef AS Comp ON Comp.id = Is2c.component_id', [])
    ]
    where = [
      ('IssueSnapshot.period_start <= %s', [1514764800]),
      ('IssueSnapshot.period_end > %s', [1514764800]),
      ('IssueSnapshot.project_id = %s', [789]),
      ('IssueSnapshot.is_open = %s', [True]),
      ('Issue.is_spam = %s', [False]),
      ('Issue.deleted = %s', [False]),
      ('(Issue.reporter_id IN (%s,%s)'
       ' OR Issue.owner_id IN (%s,%s)'
       ' OR I2cc.cc_id IS NOT NULL'
       ' OR Forbidden_label.label_id IS NULL)',
       [10L, 20L, 10L, 20L]
      ),
      ('IssueSnapshot.shard = %s', [0])
    ]
    group_by = ['Comp.path']

    self.services.chart.issuesnapshot_tbl.Select(cnxn=self.cnxn, cols=cols,
      group_by=group_by, left_joins=left_joins, shard_id=0, where=where)

    self._verifySQL(cols, left_joins, where, group_by)

    self.mox.ReplayAll()
    self.services.chart.QueryIssueSnapshots(self.cnxn, self.services,
        unixtime=1514764800, effective_ids=[10L, 20L], project=project,
        perms=perms, group_by='component')
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_Labels(self):
    """Test a burndown query from a regular user grouping by label."""
    project = fake.Project(project_id=789)
    perms = permissions.PermissionSet(['BarPerm'])
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
        self.config_service, [10L, 20L], project,
        perms).AndReturn([91, 81])

    cols = [
      'Lab.label',
      'COUNT(DISTINCT(IssueSnapshot.issue_id))',
    ]
    left_joins = [
      ('Issue ON IssueSnapshot.issue_id = Issue.id', []),
      ('Issue2Label AS Forbidden_label'
       ' ON Issue.id = Forbidden_label.issue_id'
       ' AND Forbidden_label.label_id IN (%s,%s)', [91, 81]),
      ('Issue2Cc AS I2cc'
       ' ON Issue.id = I2cc.issue_id'
       ' AND I2cc.cc_id IN (%s,%s)', [10L, 20L]),
      ('IssueSnapshot2Label AS Is2l'
       ' ON Is2l.issuesnapshot_id = IssueSnapshot.id', []),
      ('LabelDef AS Lab ON Lab.id = Is2l.label_id', [])
    ]
    where = [
      ('IssueSnapshot.period_start <= %s', [1514764800]),
      ('IssueSnapshot.period_end > %s', [1514764800]),
      ('IssueSnapshot.project_id = %s', [789]),
      ('IssueSnapshot.is_open = %s', [True]),
      ('Issue.is_spam = %s', [False]),
      ('Issue.deleted = %s', [False]),
      ('(Issue.reporter_id IN (%s,%s)'
       ' OR Issue.owner_id IN (%s,%s)'
       ' OR I2cc.cc_id IS NOT NULL'
       ' OR Forbidden_label.label_id IS NULL)',
       [10L, 20L, 10L, 20L]
      ),
      ('LOWER(Lab.label) LIKE %s', ['foo-%']),
      ('IssueSnapshot.shard = %s', [0])
    ]
    group_by = ['Lab.label']

    self.services.chart.issuesnapshot_tbl.Select(cnxn=self.cnxn, cols=cols,
      group_by=group_by, left_joins=left_joins, shard_id=0, where=where)

    self._verifySQL(cols, left_joins, where, group_by)

    self.mox.ReplayAll()
    self.services.chart.QueryIssueSnapshots(self.cnxn, self.services,
        unixtime=1514764800, effective_ids=[10L, 20L], project=project,
        perms=perms, group_by='label', label_prefix='Foo')
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_NoGroupBy(self):
    """Test a burndown query from a regular user with no grouping."""
    project = fake.Project(project_id=789)
    perms = permissions.PermissionSet(['BarPerm'])
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
        self.config_service, [10L, 20L], project,
        perms).AndReturn([91, 81])

    cols = [
      'COUNT(DISTINCT(IssueSnapshot.issue_id))',
    ]
    left_joins = [
      ('Issue ON IssueSnapshot.issue_id = Issue.id', []),
      ('Issue2Label AS Forbidden_label'
       ' ON Issue.id = Forbidden_label.issue_id'
       ' AND Forbidden_label.label_id IN (%s,%s)', [91, 81]),
      ('Issue2Cc AS I2cc'
       ' ON Issue.id = I2cc.issue_id'
       ' AND I2cc.cc_id IN (%s,%s)', [10L, 20L]),
    ]
    where = [
      ('IssueSnapshot.period_start <= %s', [1514764800]),
      ('IssueSnapshot.period_end > %s', [1514764800]),
      ('IssueSnapshot.project_id = %s', [789]),
      ('IssueSnapshot.is_open = %s', [True]),
      ('Issue.is_spam = %s', [False]),
      ('Issue.deleted = %s', [False]),
      ('(Issue.reporter_id IN (%s,%s)'
       ' OR Issue.owner_id IN (%s,%s)'
       ' OR I2cc.cc_id IS NOT NULL'
       ' OR Forbidden_label.label_id IS NULL)',
       [10L, 20L, 10L, 20L]
      ),
      ('IssueSnapshot.shard = %s', [0])
    ]
    group_by = None

    self.services.chart.issuesnapshot_tbl.Select(cnxn=self.cnxn, cols=cols,
      group_by=group_by, left_joins=left_joins, shard_id=0, where=where)

    self._verifySQL(cols, left_joins, where)

    self.mox.ReplayAll()
    self.services.chart.QueryIssueSnapshots(self.cnxn, self.services,
        unixtime=1514764800, effective_ids=[10L, 20L], project=project,
        perms=perms, group_by=None, label_prefix='Foo')
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_LabelsNotLoggedInUser(self):
    """Tests fetching burndown snapshot counts grouped by labels
    for a user who is not logged in. Also no restricted labels are
    present.
    """
    project = fake.Project(project_id=789)
    perms = permissions.READ_ONLY_PERMISSIONSET
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
        self.config_service, set([]), project,
        perms).AndReturn([91, 81])

    cols = [
      'Lab.label',
      'COUNT(DISTINCT(IssueSnapshot.issue_id))',
    ]
    left_joins = [
      ('Issue ON IssueSnapshot.issue_id = Issue.id', []),
      ('Issue2Label AS Forbidden_label'
       ' ON Issue.id = Forbidden_label.issue_id'
       ' AND Forbidden_label.label_id IN (%s,%s)', [91, 81]),
      ('IssueSnapshot2Label AS Is2l'
       ' ON Is2l.issuesnapshot_id = IssueSnapshot.id', []),
      ('LabelDef AS Lab ON Lab.id = Is2l.label_id', []),
    ]
    where = [
      ('IssueSnapshot.period_start <= %s', [1514764800]),
      ('IssueSnapshot.period_end > %s', [1514764800]),
      ('IssueSnapshot.project_id = %s', [789]),
      ('IssueSnapshot.is_open = %s', [True]),
      ('Issue.is_spam = %s', [False]),
      ('Issue.deleted = %s', [False]),
      ('Forbidden_label.label_id IS NULL', []),
      ('LOWER(Lab.label) LIKE %s', ['foo-%']),
      ('IssueSnapshot.shard = %s', [0])
    ]
    group_by = ['Lab.label']

    self.services.chart.issuesnapshot_tbl.Select(cnxn=self.cnxn, cols=cols,
      group_by=group_by, left_joins=left_joins, shard_id=0, where=where)

    self._verifySQL(cols, left_joins, where, group_by)

    self.mox.ReplayAll()
    self.services.chart.QueryIssueSnapshots(self.cnxn, self.services,
        unixtime=1514764800, effective_ids=set([]), project=project,
        perms=perms, group_by='label', label_prefix='Foo')
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_NoRestrictedLabels(self):
    """Test a label burndown query when the project has no restricted labels."""
    project = fake.Project(project_id=789)
    perms = permissions.USER_PERMISSIONSET
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
        self.config_service, [10L, 20L], project,
        perms).AndReturn([])

    cols = [
      'Lab.label',
      'COUNT(DISTINCT(IssueSnapshot.issue_id))',
    ]
    left_joins = [
      ('Issue ON IssueSnapshot.issue_id = Issue.id', []),
      ('Issue2Cc AS I2cc'
       ' ON Issue.id = I2cc.issue_id'
       ' AND I2cc.cc_id IN (%s,%s)', [10L, 20L]),
      ('IssueSnapshot2Label AS Is2l'
       ' ON Is2l.issuesnapshot_id = IssueSnapshot.id', []),
      ('LabelDef AS Lab ON Lab.id = Is2l.label_id', []),
    ]
    where = [
      ('IssueSnapshot.period_start <= %s', [1514764800]),
      ('IssueSnapshot.period_end > %s', [1514764800]),
      ('IssueSnapshot.project_id = %s', [789]),
      ('IssueSnapshot.is_open = %s', [True]),
      ('Issue.is_spam = %s', [False]),
      ('Issue.deleted = %s', [False]),
      ('(Issue.reporter_id IN (%s,%s)'
       ' OR Issue.owner_id IN (%s,%s)'
       ' OR I2cc.cc_id IS NOT NULL)',
       [10L, 20L, 10L, 20L]
      ),
      ('LOWER(Lab.label) LIKE %s', ['foo-%']),
      ('IssueSnapshot.shard = %s', [0]),
    ]
    group_by = ['Lab.label']

    self.services.chart.issuesnapshot_tbl.Select(cnxn=self.cnxn, cols=cols,
      group_by=group_by, left_joins=left_joins, shard_id=0, where=where)

    self._verifySQL(cols, left_joins, where, group_by)

    self.mox.ReplayAll()
    self.services.chart.QueryIssueSnapshots(self.cnxn, self.services,
        unixtime=1514764800, effective_ids=[10L, 20L], project=project,
        perms=perms, group_by='label', label_prefix='Foo')
    self.mox.VerifyAll()

  def SetUpStoreIssueSnapshots(self, store_label, replace_now=None,
                                      found_id=None, project_id=789,
                                      owner_id=111L, component_ids=None,
                                      cc_rows=None):
    """Set up all calls to mocks that StoreIssueSnapshots will call."""
    now = self.services.chart._currentTime().AndReturn(replace_now or 12345678)

    if found_id:
      select_return = [(found_id,)]
    else:
      select_return = []

    self.services.chart.issuesnapshot_tbl.Select(self.cnxn,
        cols=chart_svc.ISSUESNAPSHOT_COLS,
        issue_id=78901, limit=1,
        order_by=[('period_start DESC', [])]).AndReturn(select_return)

    if found_id:
      self.services.chart.issuesnapshot_tbl.Update(self.cnxn,
          {'period_end': now},
          where=[('IssueSnapshot.id = %s', [found_id])], commit=False)

    # Shard is 0 because len(shards) = 1 and 1 % 1 = 0.
    shard = 0
    self.services.chart.issuesnapshot_tbl.InsertRows(self.cnxn,
      chart_svc.ISSUESNAPSHOT_COLS[1:],
      [(78901, shard, project_id, 1, 111L, owner_id, 1,
        now, 4294967295, True)],
      replace=True, commit=False, return_generated_ids=True).AndReturn([5678])

    if store_label:
      label_rows = [(5678, 1)]
    else:
      label_rows = []

    self.services.chart.issuesnapshot2label_tbl.InsertRows(self.cnxn,
        chart_svc.ISSUESNAPSHOT2LABEL_COLS,
        label_rows,
        replace=True, commit=False)

    if not cc_rows:
      cc_rows = []
    self.services.chart.issuesnapshot2cc_tbl.InsertRows(
        self.cnxn, chart_svc.ISSUESNAPSHOT2CC_COLS,
        [(5678, row[1]) for row in cc_rows],
        replace=True, commit=False)

    if component_ids:
      component_rows = [(5678, component_id) for component_id in component_ids]
    else:
      component_rows = []
    self.services.chart.issuesnapshot2component_tbl.InsertRows(
        self.cnxn, chart_svc.ISSUESNAPSHOT2COMPONENT_COLS,
        component_rows,
        replace=True, commit=False)

    # Spacing of string must match.
    self.cnxn.Execute((
      '\n        INSERT INTO IssueSnapshot2Hotlist '
      '(issuesnapshot_id, hotlist_id)\n        '
      'SELECT %s, hotlist_id FROM Hotlist2Issue '
      'WHERE issue_id = %s\n      '
    ), [5678, 78901])

  def testStoreIssueSnapshots_NoChange(self):
    """Test that StoreIssueSnapshots inserts and updates previous
    issue snapshots correctly."""

    now_1 = 1517599888
    now_2 = 1517599999

    issue = fake.MakeTestIssue(issue_id=78901,
        project_id=789, local_id=1, reporter_id=111L, owner_id=111L,
        summary='sum', status='Status1',
        labels=['Type-Defect'],
        component_ids=[11], assume_stale=False,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12, cc_ids=[222L, 333L], derived_cc_ids=[888L])

    # Snapshot #1
    cc_rows = [(5678, 222L), (5678, 333L), (5678, 888L)]
    self.SetUpStoreIssueSnapshots(store_label=True, replace_now=now_1,
      component_ids=[11], cc_rows=cc_rows)

    # Snapshot #2
    self.SetUpStoreIssueSnapshots(store_label=True, replace_now=now_2,
      found_id=5678, component_ids=[11], cc_rows=cc_rows)

    self.mox.ReplayAll()
    self.services.chart.StoreIssueSnapshots(self.cnxn, [issue], commit=False)
    self.services.chart.StoreIssueSnapshots(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testStoreIssueSnapshots_AllFieldsChanged(self):
    """Test that StoreIssueSnapshots inserts and updates previous
    issue snapshots correctly. This tests that all relations (labels,
    CCs, and components) are updated."""

    now_1 = 1517599888
    now_2 = 1517599999

    issue_1 = fake.MakeTestIssue(issue_id=78901,
        project_id=789, local_id=1, reporter_id=111L, owner_id=111L,
        summary='sum', status='Status1',
        labels=['Type-Defect'],
        component_ids=[11, 12], assume_stale=False,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12, cc_ids=[222L, 333L], derived_cc_ids=[888L])

    issue_2 = fake.MakeTestIssue(issue_id=78901,
        project_id=123, local_id=1, reporter_id=111L, owner_id=222L,
        summary='sum', status='Status2',
        labels=['Type-Enhancement'],
        component_ids=[13], assume_stale=False,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12, cc_ids=[222L, 444L], derived_cc_ids=[888L, 999L])

    # Snapshot #1
    cc_rows_1 = [(5678, 222L), (5678, 333L), (5678, 888L)]
    self.SetUpStoreIssueSnapshots(store_label=True, replace_now=now_1,
      component_ids=[11, 12], cc_rows=cc_rows_1)

    # Snapshot #2
    cc_rows_2 = [(5678, 222L), (5678, 444L), (5678, 888L), (5678, 999L)]
    self.SetUpStoreIssueSnapshots(store_label=True, replace_now=now_2,
      found_id=5678, project_id=123, owner_id=222L, component_ids=[13],
      cc_rows=cc_rows_2)

    self.mox.ReplayAll()
    self.services.chart.StoreIssueSnapshots(self.cnxn, [issue_1], commit=False)
    self.services.chart.StoreIssueSnapshots(self.cnxn, [issue_2], commit=False)
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_WithQueryString(self):
    """Test the query param is parsed and used."""
    project = fake.Project(project_id=789)
    perms = permissions.USER_PERMISSIONSET
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
      self.config_service, [10L, 20L], project, perms).AndReturn([])

    cols = [
      'Lab.label',
      'COUNT(DISTINCT(IssueSnapshot.issue_id))',
    ]
    left_joins = [
      ('Issue ON IssueSnapshot.issue_id = Issue.id', []),
      ('Issue2Cc AS I2cc'
       ' ON Issue.id = I2cc.issue_id'
       ' AND I2cc.cc_id IN (%s,%s)', [10L, 20L]),
      ('IssueSnapshot2Label AS Is2l'
       ' ON Is2l.issuesnapshot_id = IssueSnapshot.id', []),
      ('LabelDef AS Lab ON Lab.id = Is2l.label_id', []),
      ('IssueSnapshot2Label AS Cond0 '
       'ON IssueSnapshot.id = Cond0.issuesnapshot_id '
       'AND Cond0.label_id = %s', [15L]),
    ]
    where = [
      ('IssueSnapshot.period_start <= %s', [1514764800]),
      ('IssueSnapshot.period_end > %s', [1514764800]),
      ('IssueSnapshot.project_id = %s', [789]),
      ('IssueSnapshot.is_open = %s', [True]),
      ('Issue.is_spam = %s', [False]),
      ('Issue.deleted = %s', [False]),
      ('(Issue.reporter_id IN (%s,%s)'
       ' OR Issue.owner_id IN (%s,%s)'
       ' OR I2cc.cc_id IS NOT NULL)',
       [10L, 20L, 10L, 20L]
      ),
      ('LOWER(Lab.label) LIKE %s', ['foo-%']),
      ('Cond0.label_id IS NULL', []),
      ('IssueSnapshot.shard = %s', [0]),
    ]
    group_by = ['Lab.label']

    query_left_joins = [(
        'IssueSnapshot2Label AS Cond0 '
        'ON IssueSnapshot.id = Cond0.issuesnapshot_id '
        'AND Cond0.label_id = %s', [15L])]
    query_where = [('Cond0.label_id IS NULL', [])]
    unsupported_field_names = ['ownerbouncing']

    unsupported_conds = [
      ast_pb2.Condition(op=ast_pb2.QueryOp(1), field_defs=[
        tracker_pb2.FieldDef(field_name='ownerbouncing',
                             field_type=tracker_pb2.FieldTypes.BOOL_TYPE),
      ])
    ]

    self.services.chart._QueryToWhere(mox.IgnoreArg(), mox.IgnoreArg(),
        mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg(),
        mox.IgnoreArg()).AndReturn((query_left_joins, query_where,
        unsupported_conds))

    self.services.chart.issuesnapshot_tbl.Select(cnxn=self.cnxn, cols=cols,
      group_by=group_by, left_joins=left_joins, shard_id=0, where=where)

    self._verifySQL(cols, left_joins, where, group_by)

    self.mox.ReplayAll()
    _, unsupported = self.services.chart.QueryIssueSnapshots(self.cnxn,
        self.services, unixtime=1514764800, effective_ids=[10L, 20L],
        project=project, perms=perms, group_by='label',
        query='-label:Performance%20is:ownerbouncing', label_prefix='Foo')
    self.mox.VerifyAll()

    self.assertEqual(unsupported_field_names, unsupported)
