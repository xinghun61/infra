# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for cron handlers.

This test requires the WebTest module. To install:
sudo apt-get install python-pip
sudo pip install WebTest
"""
import datetime
import json
import unittest
import webapp2
import webtest

from google.appengine.ext import testbed

from appengine_module.trooper_o_matic import cron
from appengine_module.trooper_o_matic import models
from appengine_module.trooper_o_matic.test import testing_common
from appengine_module.trooper_o_matic.test import test_data




def MockNow():
  return datetime.datetime(2014, 1, 1, 12)

# Fill in empty data for all 24 hour periods not mocked out.
for hour in range(0, 24):
  for master in ['chromium', 'chromium.win']:
    h = (MockNow() - datetime.timedelta(hours=hour)).strftime('%Y-%m-%dT%H:%MZ')
    url = ('https://chrome-infra-stats.appspot.com/_ah/api/stats/v1/steps/%s/'
           'overall__build__result__/%s') % (master, h)
    if not test_data.URLFETCH_RESPONSES.get(url):
      test_data.URLFETCH_RESPONSES[url] = {
          'content': json.dumps({'step_records': []}),
          'statuscode': 200,
      }


class CronTest(unittest.TestCase):

  def setUp(self):
    super(CronTest, self).setUp()
    self.testbed = testbed.Testbed()
    # needed because some appengine libraries expects a . in this value
    self.testbed.setup_env(current_version_id='testbed.version')
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_urlfetch_stub()
    testing_common.StubUrlfetch(test_data.URLFETCH_RESPONSES,
                                stub=self.testbed.get_stub('urlfetch'))
    app = webapp2.WSGIApplication([
        ('/check-cq', cron.CheckCQHandler),
        ('/check-tree/(.*)', cron.CheckTreeHandler),
        ('/check-tree-status/([^/]*)/(.*)', cron.CheckTreeStatusHandler),
    ])
    self.testapp = webtest.TestApp(app)
    cron.datetime_now = MockNow

  def tearDown(self):
    try:
      self.testbed.deactivate()
    finally:
      super(CronTest, self).tearDown()

  def testCheckCq(self):
    self.testapp.get('/check-cq')
    stats = models.CqStat.query().fetch()
    self.assertEqual(2, len(stats))
    self.assertEqual('blink', stats[0].key.parent().id())
    self.assertEqual(27, stats[0].min)
    self.assertEqual(45, stats[0].max)
    self.assertEqual(3, stats[0].length)
    self.assertEqual('chromium', stats[1].key.parent().id())
    self.assertEqual(5, stats[1].length)
    self.assertEqual(20, stats[1].min)
    self.assertEqual(61, stats[1].max)
    in_queue_stats = models.CqTimeInQueueForPatchStat().query().fetch()
    self.assertEqual(2, len(in_queue_stats))
    self.assertEqual(45, in_queue_stats[0].min)
    self.assertEqual(56, in_queue_stats[0].max)
    self.assertEqual(5, in_queue_stats[1].length)
    total_time_stats = models.CqTotalTimeForPatchStat().query().fetch()
    self.assertEqual(45, total_time_stats[0].min)
    self.assertEqual(59, total_time_stats[0].max)
    self.assertEqual(2, len(total_time_stats))
    self.assertEqual(5, total_time_stats[1].length)

  def testCheckTree(self):
    self.testapp.get('/check-tree/chromium')
    trees = models.Tree.query().fetch()
    self.assertEqual(1, len(trees))
    self.assertEqual('chromium', trees[0].key.id())
    stats = models.BuildTimeStat.query().fetch()
    self.assertEqual(1, len(stats))
    self.assertEqual(5, stats[0].num_builds)
    self.assertEqual(4, stats[0].num_over_median_slo)
    self.assertEqual(1, stats[0].num_over_max_slo)
    self.assertEqual(4, len(stats[0].slo_offenders))
    self.assertEqual('chromium', stats[0].slo_offenders[0].tree)
    self.assertEqual('chromium', stats[0].slo_offenders[1].tree)
    self.assertEqual('chromium', stats[0].slo_offenders[2].tree)
    self.assertEqual('chromium', stats[0].slo_offenders[0].master)
    self.assertEqual('chromium', stats[0].slo_offenders[1].master)
    self.assertEqual('chromium.win', stats[0].slo_offenders[2].master)
    self.assertEqual('Linux', stats[0].slo_offenders[0].builder)
    self.assertEqual('Android', stats[0].slo_offenders[1].builder)
    self.assertEqual('Windows 8', stats[0].slo_offenders[2].builder)
    self.assertEqual(500, stats[0].slo_offenders[0].buildnumber)
    self.assertEqual(2500, stats[0].slo_offenders[1].buildnumber)
    self.assertEqual(5500, stats[0].slo_offenders[2].buildnumber)
    self.assertEqual(5500, stats[0].slo_offenders[0].buildtime)
    self.assertEqual(28900, stats[0].slo_offenders[1].buildtime)
    self.assertEqual(5500, stats[0].slo_offenders[2].buildtime)
    self.assertEqual(0, stats[0].slo_offenders[0].result)
    self.assertEqual(0, stats[0].slo_offenders[1].result)
    self.assertEqual(1, stats[0].slo_offenders[2].result)
    self.assertEqual(5400, stats[0].slo_offenders[0].slo_median_buildtime)
    self.assertEqual(28800, stats[0].slo_offenders[0].slo_max_buildtime)

  def testCheckTreeStatusSevenDays(self):
    self.testapp.get('/check-tree-status/chromium/7')
    projects = models.Project.query().fetch()
    self.assertEqual(len(projects), 1)
    self.assertEqual('chromium', projects[0].key.id())
    stats = models.TreeOpenStat.query().fetch()
    self.assertEqual(1, len(stats))
    self.assertEqual(7, stats[0].num_days)
    self.assertEqual(78.57142857142857, stats[0].percent_open)

  def testCheckTreeStatusOneDayNoChanges(self):
    self.testapp.get('/check-tree-status/chromium/1')
    projects = models.Project.query().fetch()
    self.assertEqual(1, len(projects))
    self.assertEqual('chromium', projects[0].key.id())
    stats = models.TreeOpenStat.query().fetch()
    self.assertEqual(1, len(stats))
    self.assertEqual(1, stats[0].num_days)
    self.assertEqual(100.0, stats[0].percent_open)


if __name__ == '__main__':
  unittest.main()
