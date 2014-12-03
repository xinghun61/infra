# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit test for alerts module."""
import datetime
import json
import unittest
import webapp2
import webtest

from google.appengine.ext import testbed

from appengine_module.trooper_o_matic import alerts
from appengine_module.trooper_o_matic import models


class AlertsTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    # needed because some appengine libraries expects a . in this value
    self.testbed.setup_env(current_version_id='testbed.version')
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    app = webapp2.WSGIApplication([('/alerts', alerts.AlertsHandler)])
    self.testapp = webtest.TestApp(app)

  def testAlertsExitCriteriaNotMet(self):
    chromium_project = models.Project(id='chromium').put()
    blink_project = models.Project(id='blink').put()
    chromium_tree = models.Tree(id='chromium').put()
    blink_tree = models.Tree(id='blink').put()
    # Shouldn't use this one--too old
    models.TreeOpenStat(
        num_days=7, percent_open=99.9, parent=chromium_project,
        timestamp=datetime.datetime.utcnow()-datetime.timedelta(days=10)).put()
    # Should use this one
    models.TreeOpenStat(
        num_days=7, percent_open=75, parent=chromium_project).put()
    # Shouldn't use this one, num_days=1
    models.TreeOpenStat(
        num_days=1, percent_open=55, parent=chromium_project).put()
    # Should use this for blink.
    models.TreeOpenStat(num_days=7, percent_open=66, parent=blink_project).put()

    # Shouldn't use this one--too old
    models.CqStat(
        parent=chromium_project, p50=70, p90=200, length=10,
        timestamp=datetime.datetime.utcnow()-datetime.timedelta(hours=3)).put()
    # Should use this one
    models.CqStat(parent=chromium_project, p50=30, p90=190, length=5).put()
    models.CqStat(parent=blink_project, p50=70, p90=100, length=8).put()

    models.BuildTimeStat(
        parent=chromium_tree, num_builds=30,
        num_over_median_slo=5, num_over_max_slo=1).put()
    models.BuildTimeStat(
        parent=blink_tree, num_builds=20,
        num_over_median_slo=15, num_over_max_slo=0).put()
    response = self.testapp.get('/alerts')
    data = json.loads(response.body)
    self.assertIn('tree_status', data)
    self.assertIn('blink', data['tree_status'])
    self.assertEqual(True, data['tree_status']['blink']['should_alert'])
    self.assertEqual('Tree 66.00% open over last 7 days (must be > 80.0)',
                     data['tree_status']['blink']['details'])
    self.assertIn('chromium', data['tree_status'])
    self.assertEqual(
        True, data['tree_status']['chromium']['should_alert'])
    self.assertEqual('Tree 75.00% open over last 7 days (must be > 80.0)',
                     data['tree_status']['chromium']['details'])
    self.assertIn('cq_latency', data)
    self.assertIn('blink', data['cq_latency'])
    self.assertEqual(True, data['cq_latency']['blink']['should_alert'])
    self.assertEqual(('CQ latency is median 70m and 90th 100m '
                      '(must be less than median 60m and 90th 180m'),
                     data['cq_latency']['blink']['details'])
    self.assertIn('chromium', data['cq_latency'])
    self.assertEqual(True, data['cq_latency']['chromium']['should_alert'])
    self.assertEqual(('CQ latency is median 30m and 90th 190m '
                      '(must be less than median 60m and 90th 180m'),
                     data['cq_latency']['chromium']['details'])
    self.assertIn('cycle_time', data)
    self.assertIn('blink', data['cycle_time'])
    self.assertEqual(True, data['cycle_time']['blink']['should_alert'])
    self.assertEqual('0 builds over their max, 15 builds over their median',
                     data['cycle_time']['blink']['details'])
    self.assertIn('chromium', data['cycle_time'])
    self.assertEqual(True, data['cycle_time']['chromium']['should_alert'])
    self.assertEqual('1 builds over their max, 5 builds over their median',
                     data['cycle_time']['chromium']['details'])

  def testAlertsExitCriteriaMet(self):
    chromium_project = models.Project(id='chromium').put()
    blink_project = models.Project(id='blink').put()
    chromium_tree = models.Tree(id='chromium').put()
    blink_tree = models.Tree(id='blink').put()
    # Shouldn't use this one--too old
    models.TreeOpenStat(
        num_days=7, percent_open=99.9, parent=chromium_project,
        timestamp=datetime.datetime.now() - datetime.timedelta(days=10)).put()
    # Should use this one
    models.TreeOpenStat(
        num_days=7, percent_open=90, parent=chromium_project).put()
    # Should use this for blink.
    models.TreeOpenStat(num_days=7, percent_open=99, parent=blink_project).put()

    models.CqStat(parent=chromium_project, p50=30, p90=50, length=5).put()
    models.CqStat(parent=blink_project, p50=25, p90=40, length=8).put()

    models.BuildTimeStat(
        parent=chromium_tree, num_builds=30,
        num_over_median_slo=5, num_over_max_slo=0).put()
    models.BuildTimeStat(
        parent=blink_tree, num_builds=20,
        num_over_median_slo=6, num_over_max_slo=0).put()
    response = self.testapp.get('/alerts')
    data = json.loads(response.body)
    self.assertIn('tree_status', data)
    self.assertIn('blink', data['tree_status'])
    self.assertEqual(False, data['tree_status']['blink']['should_alert'])
    self.assertIn('chromium', data['tree_status'])
    self.assertEqual(
        False, data['tree_status']['chromium']['should_alert'])
    self.assertIn('cq_latency', data)
    self.assertIn('blink', data['cq_latency'])
    self.assertEqual(False, data['cq_latency']['blink']['should_alert'])
    self.assertIn('chromium', data['cq_latency'])
    self.assertEqual(False, data['cq_latency']['chromium']['should_alert'])
    self.assertIn('cycle_time', data)
    self.assertIn('blink', data['cycle_time'])
    self.assertEqual(False, data['cycle_time']['blink']['should_alert'])
    self.assertIn('chromium', data['cycle_time'])
    self.assertEqual(False, data['cycle_time']['chromium']['should_alert'])


if __name__ == '__main__':
  unittest.main()
