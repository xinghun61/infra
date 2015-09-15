# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap

import webapp2

from testing_utils import testing

from common.http_client_appengine import RetryHttpClient
from handlers import monitor_alerts
from waterfall import build_failure_analysis_pipelines
from waterfall import masters


class _MockedHttpClient(RetryHttpClient):
  def __init__(self, status_code, content):
    self.status_code = status_code
    self.content = content

  def _Get(self, *_):
    return self.status_code, self.content

  def _Post(self, *_):  # pragma: no cover
    pass


class MonitorAlertsTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/monitor-alerts', monitor_alerts.MonitorAlerts),
  ], debug=True)

  def setUp(self):
    super(MonitorAlertsTest, self).setUp()

    def MockMasterIsSupported(master_name):
      return master_name != 'm0'

    self.mock(masters, 'MasterIsSupported', MockMasterIsSupported)

  def testGetLatestBuildFailuresWhenFailedToPullAlerts(self):
    http_client = _MockedHttpClient(404, 'Not Found')
    self.assertEqual([], monitor_alerts._GetLatestBuildFailures(http_client))

  def testGetLatestBuildFailuresWhenIllegalMasterUrl(self):
    alerts_content = textwrap.dedent("""
        {
          "last_posted": 1434668974,
          "alerts": [
            {
              "master_url": "https://not/a/url/to/a/master",
              "builder_name": "b1",
              "last_failing_build": 1,
              "step_name": "s1",
              "reason": null
            }
          ]
        }""")
    http_client = _MockedHttpClient(200, alerts_content)
    self.assertEqual([], monitor_alerts._GetLatestBuildFailures(http_client))

  def testGetLatestBuildFailuresWhenMasterNotSupported(self):
    alerts_content = textwrap.dedent("""
        {
          "last_posted": 1434668974,
          "alerts": [
            {
              "master_url": "https://build.chromium.org/p/m0",
              "builder_name": "b2",
              "last_failing_build": 2,
              "step_name": "s2",
              "reason": null
            }
          ]
        }""")
    http_client = _MockedHttpClient(200, alerts_content)
    self.assertEqual([], monitor_alerts._GetLatestBuildFailures(http_client))

  def testGetLatestBuildFailuresWhenAlertsAreForTwoTestsInTheSameStep(self):
    alerts_content = textwrap.dedent("""
        {
          "last_posted": 1434668974,
          "alerts": [
            {
              "master_url": "https://build.chromium.org/p/m3",
              "builder_name": "b3",
              "last_failing_build": 3,
              "step_name": "s3",
              "reason": "suite1.test1"
            },
            {
              "master_url": "https://build.chromium.org/p/m3",
              "builder_name": "b3",
              "last_failing_build": 3,
              "step_name": "s3",
              "reason": "suite1.test2"
            }
          ]
        }""")
    expected_build_failures = [
        {
            'master_name': 'm3',
            'builder_name': 'b3',
            'build_number': 3,
            'failed_steps': ['s3'],
        },
    ]

    http_client = _MockedHttpClient(200, alerts_content)
    self.assertEqual(expected_build_failures,
                     monitor_alerts._GetLatestBuildFailures(http_client))

  def testGetLatestBuildFailuresWhenAlertsAreForTwoStepsInTheSameBuild(self):
    alerts_content = textwrap.dedent("""
        {
          "last_posted": 1434668974,
          "alerts": [
            {
              "master_url": "https://build.chromium.org/p/m3",
              "builder_name": "b3",
              "last_failing_build": 4,
              "step_name": "s1",
              "reason": null
            },
            {
              "master_url": "https://build.chromium.org/p/m3",
              "builder_name": "b3",
              "last_failing_build": 4,
              "step_name": "s2",
              "reason": null
            }
          ]
        }
        """)

    expected_build_failures = [
        {
            'master_name': 'm3',
            'builder_name': 'b3',
            'build_number': 4,
            'failed_steps': ['s1', 's2'],
        },
    ]

    http_client = _MockedHttpClient(200, alerts_content)
    build_failures = monitor_alerts._GetLatestBuildFailures(http_client)
    self.assertEqual(expected_build_failures, build_failures)

  def testAnalysisScheduled(self):
    build_failures = [
        {
            'master_name': 'm3',
            'builder_name': 'b3',
            'build_number': 3,
            'failed_steps': ['s3'],
        },
    ]

    def MockGetLatestBuildFailures(*_):
      return build_failures
    self.mock(
        monitor_alerts, '_GetLatestBuildFailures', MockGetLatestBuildFailures)

    expected_scheduled_analyses = [
        ('m3', 'b3', 3, ['s3'], False,
         monitor_alerts._BUILD_FAILURE_ANALYSIS_TASKQUEUE),
    ]

    scheduled_analyses = []
    def MockScheduleAnalysisIfNeeded(master_name, builder_name, build_number,
                                     failed_steps, force, queue_name):
      scheduled_analyses.append(
          (master_name, builder_name, build_number,
           failed_steps, force, queue_name))

    self.mock(build_failure_analysis_pipelines, 'ScheduleAnalysisIfNeeded',
              MockScheduleAnalysisIfNeeded)

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    response = self.test_app.get('/monitor-alerts')
    self.assertEqual(200, response.status_int)

    self.assertEqual(expected_scheduled_analyses, scheduled_analyses)
