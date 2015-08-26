# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os

from testing_utils import testing

from common.retry_http_client import RetryHttpClient
from waterfall import buildbot
from waterfall import swarming_util


class SwarmingHttpClient(RetryHttpClient):
  def __init__(self):
    self.responses = dict()

  def _ResponseForUrl(
      self, master_name, builder_name, build_number):
    if builder_name == 'download_failed':
      return

    url = swarming_util.TEMPLATE_URL.format(
        master=master_name, buildername=builder_name, buildnumber=build_number)

    swarming_tasks_file = os.path.join(
        os.path.dirname(__file__), 'data', 'sample_swarming_build_tasks.json')
    with open(swarming_tasks_file, 'r') as f:
      response = f.read()

    cursor_swarming_data = {
      'cursor': None,
      'items': [],
      'state': 'all',
      'limit': 100,
      'sort': 'created_ts'
    }
    cursor_url = ('%s?cursor=thisisacursor') % url

    self.responses[url] = response
    self.responses[cursor_url] = json.dumps(cursor_swarming_data)

  def _Get(self, url, *_):
    if url not in self.responses:
      return 404, 'Download Failed!'
    return 200, self.responses[url]


class SwarmingUtilTest(testing.AppengineTestCase):
  def setUp(self):
    super(SwarmingUtilTest, self).setUp()
    self.http_client = SwarmingHttpClient()

  def testUpdateSwarmingTaskIdForFailedSteps(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'compile':{
            'current_failure': 2,
            'first_failure': 0
        }
    }

    self.http_client._ResponseForUrl(master_name, builder_name, build_number)

    result = swarming_util.UpdateSwarmingTaskIdForFailedSteps(
        master_name, builder_name, build_number, failed_steps, self.http_client)
    expected_failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'swarming_task_ids': ['2944af95a8b97f10']
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'swarming_task_ids': ['2944afa502297110', '2944afa502297111']
        },
        'compile':{
            'current_failure': 2,
            'first_failure': 0
        }
    }
    self.assertTrue(result)
    self.assertEqual(expected_failed_steps, failed_steps)

  def testUpdateSwarmingTaskIdForFailedStepsDownloadFailed(self):
    master_name = 'm'
    builder_name = 'download_failed'
    build_number = 123
    failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0
        }
    }

    self.http_client._ResponseForUrl(master_name, builder_name, build_number)

    result = swarming_util.UpdateSwarmingTaskIdForFailedSteps(
        master_name, builder_name, build_number, failed_steps, self.http_client)
    expected_failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0
        }
    }
    self.assertFalse(result)
    self.assertEqual(expected_failed_steps, failed_steps)
