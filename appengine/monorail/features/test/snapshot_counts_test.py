# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for snapshot counts query handler."""

import mox
import unittest
import urllib
import webapp2

from features import snapshot_counts
from framework import urls
from services import service_manager
from services import chart_svc
from testing import fake
from testing import testing_helpers

class SnapshotCountsTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.mox = mox.Mox()
    self.services = service_manager.Services(
      chart=chart_svc.ChartService(fake.ConfigService()))
    self.servlet = snapshot_counts.SnapshotCounts('req', 'res',
      services=self.services)
    self.path_base = '/p/proj%s' % urls.SNAPSHOT_COUNTS
    self.default_timestamp = 1514764800
    self.mox.StubOutWithMock(self.services.chart, 'QueryIssueSnapshots')

  def makeMonorailGETRequest(self, url_params):
    """Utility method for generating snapshot requests."""
    url_param_str = urllib.urlencode(url_params)
    path = '%s?%s' % (self.path_base, url_param_str)
    return testing_helpers.MakeMonorailRequest(path=path,
      project=fake.Project(project_name='proj'),
      method='GET')

  def testSnapshotCounts_TimestampRequired(self):
    """Tests that url param `timestamp` is required."""
    mr = self.makeMonorailGETRequest({
      'group_by': 'component',
    })
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
    self.services.chart.QueryIssueSnapshots(mox.IgnoreArg(),
      self.default_timestamp, mox.IgnoreArg(), mox.IgnoreArg(),
      mox.IgnoreArg(), group_by='label', label_prefix='Type').AndReturn([])

    self.mox.ReplayAll()
    response = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(response, [])

  def testSnapshotCounts_Label(self):
    """Tests the case when bucketing by label."""
    mr = self.makeMonorailGETRequest({
      'timestamp': self.default_timestamp,
      'group_by': 'label',
      'label_prefix': 'Type',
    })
    self.services.chart.QueryIssueSnapshots(mox.IgnoreArg(),
      self.default_timestamp, mox.IgnoreArg(), mox.IgnoreArg(),
      mox.IgnoreArg(), group_by='label', label_prefix='Type').AndReturn([
      ('name1', 12),
      ('name2', 14),
    ])

    self.mox.ReplayAll()
    response = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(response, [
      ('name1', 12),
      ('name2', 14),
    ])

  def testSnapshotCounts_Component(self):
    """Tests the case when bucketing by label."""
    mr = self.makeMonorailGETRequest({
      'timestamp': self.default_timestamp,
      'group_by': 'component',
    })
    self.services.chart.QueryIssueSnapshots(mox.IgnoreArg(),
      self.default_timestamp, mox.IgnoreArg(), mox.IgnoreArg(),
      mox.IgnoreArg(), group_by='component', label_prefix=None).AndReturn([
      ('name>name1', 12),
      ('name>name2', 14),
    ])

    self.mox.ReplayAll()
    response = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertEqual(response, [
      ('name>name1', 12),
      ('name>name2', 14),
    ])
