# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import testbed
import webapp2
import webtest

from testing_utils import testing

from handlers import monitor_alerts
from waterfall import alerts
from waterfall import build_failure_analysis_pipelines
from waterfall import masters


class MonitorAlertsTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/monitor-alerts', monitor_alerts.MonitorAlerts),
  ], debug=True)

  def testTriggerAnalysis(self):
    def MockMasterIsSupported(*_):
      return True

    self.mock(masters, 'MasterIsSupported', MockMasterIsSupported)

    old_failures = {
        'date': 111111,
        'build_failures': {
            'master': {
                'b1': {
                    'earliest_build': 1,
                    'latest_build': 1,
                    'failed_steps': ['step2'],
                }
            }
        }
    }
    monitor_alerts._CacheAlerts(old_failures)

    latest_alerts = {
        'date': 222222,
        'alerts': [
            {
                'master_url': 'https://build.chromium.org/p/master',
                'builder_name': 'b2',
                'failing_build': 2,
                'last_failing_build': 2,
                'step_name': 'step1',
                'reason': None,
            },
        ]
    }
    def MockGetLatestAlerts(*_):
      return latest_alerts
    self.mock(alerts, 'GetLatestAlerts', MockGetLatestAlerts)

    expected_new_cached_alerts = {
        'date': 222222,
        'build_failures': {
            'master': {
                'b2': {
                    'earliest_build': 2,
                    'latest_build': 2,
                    'failed_steps': ['step1'],
                }
            }
        }
    }

    scheduled_analysis = []
    def MockScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, force, *_, **__):
      scheduled_analysis.append(
          (master_name, builder_name, build_number, force))

    self.mock(build_failure_analysis_pipelines, 'ScheduleAnalysisIfNeeded',
              MockScheduleAnalysisIfNeeded)

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    response = self.test_app.get('/monitor-alerts')
    self.assertEqual(200, response.status_int)

    self.assertEqual([('master', 'b2', 2, True)], scheduled_analysis)
    cached_alerts = monitor_alerts._GetCachedAlerts()
    self.assertEqual(expected_new_cached_alerts, cached_alerts)
