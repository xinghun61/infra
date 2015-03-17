# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from testing_utils import testing

from common.retry_http_client import RetryHttpClient
from waterfall import alerts
from waterfall import masters


class _MockedHttpClient(RetryHttpClient):
  def __init__(self, status, content):
    self.status = status
    self.content = content

  def _Get(self, *_):
    return self.status, self.content


class AlertsTest(testing.AppengineTestCase):
  def testGetlatestAlertsOn404(self):
    http_client = _MockedHttpClient(404, '')
    self.assertIsNone(alerts.GetLatestAlerts(http_client))

  def testGetlatestAlertsException(self):
    http_client = _MockedHttpClient(200, '')
    self.assertIsNone(alerts.GetLatestAlerts(http_client))

  def testGetlatestAlertsSuccess(self):
    data_json = {"a" : 1}
    http_client = _MockedHttpClient(200, json.dumps(data_json, indent=2))
    self.assertEqual(data_json, alerts.GetLatestAlerts(http_client))

  def testGetBuildFailureAlerts(self):
    alert_data = {
        'alerts': [
            {
                'master_url': 'not_a_master_url',
            },
            {
                'master_url': 'https://build.chromium.org/p/unsupported_master',
            },
            {
                'master_url': 'https://build.chromium.org/p/master',
                'builder_name': 'builder1',
                'failing_build': 2,
                'last_failing_build': 2,
                'step_name': 'stepX',
                'reason': None,
            },
            {
                'master_url': 'https://build.chromium.org/p/master',
                'builder_name': 'builder1',
                'failing_build': 1,
                'last_failing_build': 3,
                'step_name': 'step1',
                'reason': '1',
            },
            {
                'master_url': 'https://build.chromium.org/p/master',
                'builder_name': 'builder1',
                'failing_build': 3,
                'last_failing_build': 3,
                'step_name': 'step2',
                'reason': '2',
            },
            {
                'master_url': 'https://build.chromium.org/p/master',
                'builder_name': 'builder1',
                'failing_build': 2,
                'last_failing_build': 3,
                'step_name': 'step2',
                'reason': '3',
            },
        ]
    }
    expected_failures = {
        'master': {
            'builder1': {
                'earliest_build': 1,
                'latest_build': 3,
                'failed_steps': ['step1', 'step2', 'stepX'],
            }
        }
    }

    self.mock(masters, '_SUPPORTED_MASTERS', ['master'])
    failures = alerts.GetBuildFailureAlerts(alert_data)
    self.assertEqual(expected_failures, failures)

  def testGetNewFailures(self):
    old_failures = {
        'master': {
            'b1': {
                'earliest_build': 1,
                'latest_build': 1,
                'failed_steps': ['step1'],
            },
            'b2': {
                'earliest_build': 2,
                'latest_build': 2,
                'failed_steps': ['test1'],
            },
            'b3': {
                'earliest_build': 3,
                'latest_build': 4,
                'failed_steps': ['test1'],
            },
        }
    }
    failures = {
        'master': {
            'b1': {
                'earliest_build': 1,
                'latest_build': 1,
                'failed_steps': ['step1'],
            },
            'b2': {
                'earliest_build': 2,
                'latest_build': 3,
                'failed_steps': ['test1'],
            },
            'b3': {
                'earliest_build': 3,
                'latest_build': 4,
                'failed_steps': ['test1', 'test2'],
            },
            'b4': {
                'earliest_build': 5,
                'latest_build': 5,
                'failed_steps': ['compile'],
            },
        }
    }
    expected_new_failures = {
        'master': {
            'b2': 3,
            'b3': 4,
            'b4': 5,
        }
    }

    new_failures = alerts.GetNewFailures(failures, old_failures)
    self.assertEqual(expected_new_failures, new_failures)
