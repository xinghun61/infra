# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for snapshot counts query handler."""

import mox
import unittest
import urllib
import webapp2

from features import savedqueries_helpers
from features import snapshot_counts
from framework import urls
from search import searchpipeline
from services import service_manager
from services import chart_svc
from testing import fake
from testing import testing_helpers

class SnapshotCountsTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = fake.MonorailConnection()
    self.mox = mox.Mox()
    self.services = service_manager.Services(
      chart=chart_svc.ChartService(fake.ConfigService()))
    self.servlet = snapshot_counts.SnapshotCounts('req', 'res',
      services=self.services)
    self.path_base = '/p/proj%s' % urls.SNAPSHOT_COUNTS
    self.default_timestamp = 1514764800
    self.mox.StubOutWithMock(self.services.chart, 'QueryIssueSnapshots')
    self.mox.StubOutWithMock(savedqueries_helpers, 'SavedQueryIDToCond')
    self.mox.StubOutWithMock(searchpipeline, 'ReplaceKeywordsWithUserID')
    self.project = fake.Project(project_name='proj')
    self.basic_results = {
      'name1': 11,
      'name2': 12,
    }
    self.unsupported_conds = ['rutabaga1', 'rutabaga2']

  def makeMonorailGETRequest(self, url_params):
    """Utility method for generating snapshot requests."""
    url_param_str = urllib.urlencode(url_params)
    path = '%s?%s' % (self.path_base, url_param_str)
    return testing_helpers.MakeMonorailRequest(path=path, project=self.project,
        method='GET')

  def testSnapshotCounts_TimestampRequired(self):
    """Tests that url param `timestamp` is required."""
    mr = self.makeMonorailGETRequest({})
    response = self.servlet.HandleRequest(mr)
    self.assertEqual(response, { 'error': 'Param `timestamp` required.' })

  def testSnapshotCounts_LabelPrefixRequired(self):
    """Tests that url param `label_prefix` is required."""
    mr = self.makeMonorailGETRequest({
      'timestamp': self.default_timestamp,
      'group_by': 'label',
    })
    response = self.servlet.HandleRequest(mr)
    self.assertEqual(response, { 'error': 'Param `label_prefix` required.' })

  def testSnapshotCounts_Empty(self):
    """Tests the case when there are no snapshots."""
    mr = self.makeMonorailGETRequest({
      'timestamp': self.default_timestamp,
      'group_by': 'label',
      'label_prefix': 'Type',
    })
    self.services.chart.QueryIssueSnapshots(mr.cnxn,
        self.services, self.default_timestamp, mr.auth.effective_ids,
        self.project, mr.perms, group_by='label', label_prefix='Type',
        query='', canned_query=None).AndReturn([{}, []])

    self.mox.ReplayAll()
    response = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(response, {
      'results': {},
      'unsupported_fields': [],
    })

  def testSnapshotCounts_Basic(self):
    """Tests the case when there is no group_by."""
    mr = self.makeMonorailGETRequest({
      'timestamp': self.default_timestamp,
    })
    self.services.chart.QueryIssueSnapshots(mr.cnxn,
        self.services, self.default_timestamp, mr.auth.effective_ids,
        self.project, mr.perms, group_by=None, label_prefix=None,
        query='', canned_query=None).AndReturn([self.basic_results, []])

    self.mox.ReplayAll()
    response = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(response, {
      'results': self.basic_results,
      'unsupported_fields': [],
    })

  def testSnapshotCounts_GroupByLabel(self):
    """Tests the case when bucketing by label."""
    mr = self.makeMonorailGETRequest({
      'timestamp': self.default_timestamp,
      'group_by': 'label',
      'label_prefix': 'Type',
    })
    self.services.chart.QueryIssueSnapshots(mr.cnxn,
        self.services, self.default_timestamp, mr.auth.effective_ids,
        self.project, mr.perms, group_by='label', label_prefix='Type',
        query='', canned_query=None).AndReturn([self.basic_results, []])

    self.mox.ReplayAll()
    response = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(response, {
      'results': self.basic_results,
      'unsupported_fields': [],
    })

  def testSnapshotCounts_Component(self):
    """Tests the case when bucketing by label."""
    mr = self.makeMonorailGETRequest({
      'timestamp': self.default_timestamp,
      'group_by': 'component',
    })
    self.services.chart.QueryIssueSnapshots(mr.cnxn,
        self.services, self.default_timestamp, mr.auth.effective_ids,
        self.project, mr.perms, group_by='component', label_prefix=None,
        query='', canned_query=None).AndReturn([self.basic_results, []])

    self.mox.ReplayAll()
    response = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(response, {
      'results': self.basic_results,
      'unsupported_fields': [],
    })

  def testSnapshotCounts_Query(self):
    """Tests the case with a query."""
    mr = self.makeMonorailGETRequest({
      'timestamp': self.default_timestamp,
      'q': 'component:Rutabaga',
      'can': '2',
    })
    mr.me_user_id = 111L
    savedqueries_helpers.SavedQueryIDToCond(mr.cnxn, self.services.features,
        mr.can).AndReturn(['cannedq'])
    searchpipeline.ReplaceKeywordsWithUserID(mox.IgnoreArg(),
        ['cannedq']).AndReturn(['cannedq', []])
    self.services.chart.QueryIssueSnapshots(mr.cnxn,
        self.services, self.default_timestamp, mr.auth.effective_ids,
        self.project, mr.perms, group_by=None, label_prefix=None,
        query='component:Rutabaga',
        canned_query='cannedq').AndReturn([self.basic_results, []])

    self.mox.ReplayAll()
    response = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(response, {
      'results': self.basic_results,
      'unsupported_fields': [],
    })

  def testSnapshotCounts_QueryUnsupportedConds(self):
    """Tests the case when some conditions are unsupported."""
    query = 'rutabaga:Rutabaga rutabaga1:Rutabaga rutabaga2:56'
    mr = self.makeMonorailGETRequest({
      'timestamp': self.default_timestamp,
      'group_by': 'component',
      'q': query,
      'can': '2',
    })
    mr.me_user_id = 111L
    savedqueries_helpers.SavedQueryIDToCond(mr.cnxn, self.services.features,
        mr.can).AndReturn(['cannedq'])
    searchpipeline.ReplaceKeywordsWithUserID(mox.IgnoreArg(),
        ['cannedq']).AndReturn(['cannedq', []])
    self.services.chart.QueryIssueSnapshots(mr.cnxn,
        self.services, self.default_timestamp, mr.auth.effective_ids,
        self.project, mr.perms, group_by='component', label_prefix=None,
        query=query, canned_query='cannedq').AndReturn([
            self.basic_results, self.unsupported_conds])

    self.mox.ReplayAll()
    response = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(response, {
      'results': self.basic_results,
      'unsupported_fields': ['rutabaga1', 'rutabaga2'],
    })
