#!/usr/bin/env python
# Copyright 2011 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for buildbucket client."""

import json
import logging
import unittest

import setup
setup.process_args()


from google.appengine.ext import ndb

from utils import TestCase

from codereview import buildbucket
from codereview import common
from codereview import models
from codereview import net


class BuildbucketTryJobResultTest(TestCase):
  """Test buildbucket build -> TryJobResult conversion."""

  def test_convert_status_to_result(self):
    statuses = buildbucket.BuildbucketTryJobResult

    def status_test(build, expected):
      actual = buildbucket.BuildbucketTryJobResult.convert_status_to_result(
          build)
      self.assertEqual(actual, expected)

    status_test({'status': 'SCHEDULED'}, statuses.TRYPENDING)
    status_test({'status': 'STARTED'}, statuses.STARTED)
    status_test({'status': 'COMPLETED', 'result': 'SUCCESS'}, statuses.SUCCESS)
    status_test(
        {
          'status': 'COMPLETED',
          'result': 'FAILURE',
          'failure_reason': 'BUILD_FAILURE',
        },
        statuses.FAILURE)
    status_test(
        {
          'status': 'COMPLETED',
          'result': 'FAILURE',
          'failure_reason': 'INFRA_FAILURE',
        },
        statuses.EXCEPTION)
    status_test(
        {
          'status': 'COMPLETED',
          'result': 'FAILURE',
          'failure_reason': 'INVALID_BUILD_DEFINITION',
        },
        statuses.EXCEPTION)
    status_test({'status': 'UNKNOWN_STATUS'}, None)
    status_test({}, None)

  def test_from_build(self):
    properties = {
      'buildnumber': 2,
      'category': 'cq_experimental',
      'clobber': False,
      'project': 'chromium',
      'reason': 'because I can',
      'requester': 'chrome-bot@chromium.org',
      'revision': 'deadbeef',
      'slavename': 'vm1-m1',
      'testfilter': ['defaulttests'],
    }
    build = {
      'id': '1234567890',
      'status': 'SCHEDULED',
      'status_changed_ts': 1430511441000,
      'tags': [
        'buildset:patch/rietveld/codereview.chromium.org/1/2',
        'master:tryserver.chromium.linux',
      ],
      'url': 'http://tryserver.com/1',
      'parameters_json': json.dumps({
        'builder_name': 'Release',
        'properties': properties,
      }),
    }
    result = buildbucket.BuildbucketTryJobResult.from_build(build)
    self.assertIsNotNone(result)
    self.assertEqual(result.build_id, '1234567890')
    self.assertEqual(result.url, 'http://tryserver.com/1')
    self.assertEqual(
        result.result, buildbucket.BuildbucketTryJobResult.TRYPENDING)
    self.assertEqual(result.master, 'tryserver.chromium.linux')
    self.assertEqual(result.builder, 'Release')
    self.assertEqual(result.slave, 'vm1-m1')
    self.assertEqual(result.buildnumber, 2)
    self.assertEqual(result.reason, 'because I can')
    self.assertEqual(result.revision, 'deadbeef')
    self.assertEqual(result.clobber, False)
    self.assertEqual(result.tests, ['defaulttests'])
    self.assertEqual(result.project, 'chromium')
    self.assertEqual(result.requester.email(), 'chrome-bot@chromium.org')
    self.assertEqual(result.category, 'cq_experimental')
    self.assertEqual(result.category, 'cq_experimental')
    self.assertEqual(json.loads(result.build_properties), properties)

  def test_from_build_with_result_details(self):
    build = {
      'id': '1234567890',
      'status': 'COMPLETED',
      'status_changed_ts': 1430511441000,
      'result': 'SUCCESS',
      'parameters_json': json.dumps({
        'builder_name': 'Release',
        'properties': {'source': 'parameters'},
      }),
      'result_details_json': json.dumps({
        'properties': {'source': 'result_details'},
      }),
    }
    result = buildbucket.BuildbucketTryJobResult.from_build(build)
    properties = json.loads(result.build_properties)
    self.assertEqual(properties['source'], 'result_details')

  def test_from_build_with_weird_input(self):
    properties = {
      'buildnumber': 'not number',
      'category': 1,
      'clobber': 'sdfsdf',
      'reason': 234,
      'testfilter': 'not a list',
    }
    build = {
      'id': 'not an int',
      'status': 'SCHEDULED',
      'status_changed_ts': 1430511441000,
      'tags': [
        # no master name
        'weirdtag:a:b:c',
      ],
      'parameters_json': json.dumps({
        # no builder_name
        'properties': properties,
      }),
    }
    # Should not raise an exception
    buildbucket.BuildbucketTryJobResult.from_build(build)


class BuildbucketFunctionsTest(TestCase):
  """Test buildbucket module functions."""

  def setUp(self):
    self.fake_responses = []
    def json_request_async(*_, **__):
      future = ndb.Future()
      future.set_result(self.fake_responses.pop(0))
      return future

    self.mock(net, 'json_request_async', json_request_async)
    self.mock(common, 'get_preferred_domain',
              lambda *_, **__: 'codereview.chromium.org')

  def test_get_try_job_results_for_patchset(self):
    response_data = {
      'builds': [
        {'id': '1', 'status': 'SCHEDULED'},
        {'id': '2', 'status': 'SCHEDULED'},
      ]
    }
    self.fake_responses = [response_data]
    actual_builds = buildbucket.get_builds_for_patchset_async(
        'project', 1, 2).get_result()
    self.assertEqual(actual_builds, response_data['builds'])


if __name__ == '__main__':
  unittest.main()
