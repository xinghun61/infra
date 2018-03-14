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
from testing import fake
from search import search_helpers


def MakeChartService(my_mox):
  chart_service = chart_svc.ChartService()
  for table_var in ['issuesnapshot_tbl', 'labeldef_tbl']:
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
    self.services.chart = MakeChartService(self.mox)
    self.config_service = fake.ConfigService()
    self.mox.StubOutWithMock(search_helpers, 'GetPersonalAtRiskLabelIDs')
    self.mox.StubOutWithMock(settings, 'num_logical_shards')
    settings.num_logical_shards = 1

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def _verifySQL(self, cols, left_joins, where, group_by):
    for col in cols:
      self.assertTrue(sql._IsValidColumnName(col))
    for join_str, _ in left_joins:
      self.assertTrue(sql._IsValidJoin(join_str))
    for where_str, _ in where:
      self.assertTrue(sql._IsValidWhereCond(where_str))
    for groupby_str in group_by:
      self.assertTrue(sql._IsValidGroupByTerm(groupby_str))

  def testQueryIssueSnapshots_InvalidBucketBy(self):
    """Make sure the `bucketby` argument is checked."""
    project = fake.Project(project_id=789)
    perms = permissions.USER_PERMISSIONSET
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
      self.config_service, [10L, 20L], project, perms).AndReturn([91, 81])

    self.mox.ReplayAll()
    with self.assertRaises(ValueError):
      self.services.chart.QueryIssueSnapshots(self.cnxn, self.config_service,
        unixtime=1514764800, bucketby='rutabaga', effective_ids=[10L, 20L],
        project=project, perms=perms, label_prefix='rutabaga')
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_NoLabelPrefix(self):
    """Make sure the `label_prefix` argument is required."""
    project = fake.Project(project_id=789)
    perms = permissions.USER_PERMISSIONSET
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
      self.config_service, [10L, 20L], project, perms).AndReturn([91, 81])

    self.mox.ReplayAll()
    with self.assertRaises(ValueError):
      self.services.chart.QueryIssueSnapshots(self.cnxn, self.config_service,
        unixtime=1514764800, bucketby='label', effective_ids=[10L, 20L],
        project=project, perms=perms)
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_Components(self):
    """Test a burndown query from a regular user grouping by component."""
    project = fake.Project(project_id=789)
    perms = permissions.PermissionSet(['BarPerm'])
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
      self.config_service, [10L, 20L], project, perms).AndReturn([91, 81])

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
    self.services.chart.QueryIssueSnapshots(self.cnxn, self.config_service,
      unixtime=1514764800, bucketby='component', effective_ids=[10L, 20L],
      project=project, perms=perms)
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_Labels(self):
    """Test a burndown query from a regular user grouping by label."""
    project = fake.Project(project_id=789)
    perms = permissions.PermissionSet(['BarPerm'])
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
      self.config_service, [10L, 20L], project, perms).AndReturn([91, 81])

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
    self.services.chart.QueryIssueSnapshots(self.cnxn, self.config_service,
      unixtime=1514764800, bucketby='label', effective_ids=[10L, 20L],
      project=project, perms=perms, label_prefix='Foo')
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_LabelsNotLoggedInUser(self):
    """Tests fetching burndown snapshot counts grouped by labels
    for a user who is not logged in. Also no restricted labels are
    present.
    """
    project = fake.Project(project_id=789)
    perms = permissions.READ_ONLY_PERMISSIONSET
    search_helpers.GetPersonalAtRiskLabelIDs(self.cnxn, None,
      self.config_service, set(), project, perms).AndReturn([91, 81])

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
    self.services.chart.QueryIssueSnapshots(self.cnxn, self.config_service,
      unixtime=1514764800, bucketby='label', effective_ids=set([]),
      project=project, perms=perms, label_prefix='Foo')
    self.mox.VerifyAll()

  def testQueryIssueSnapshots_NoRestrictedLabels(self):
    """Test a label burndown query when the project has no restricted labels."""
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
    self.services.chart.QueryIssueSnapshots(self.cnxn, self.config_service,
      unixtime=1514764800, bucketby='label', effective_ids=[10L, 20L],
      project=project, perms=perms, label_prefix='Foo')
    self.mox.VerifyAll()
