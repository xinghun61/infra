# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import os
import urllib
import zlib

from testing_utils import testing

from common.retry_http_client import RetryHttpClient
from model.wf_step import WfStep
from waterfall import swarming_util
from waterfall.swarming_task_request import SwarmingTaskRequest


class SwarmingHttpClient(RetryHttpClient):
  def __init__(self):
    self.get_responses = dict()
    self.post_responses = dict()

  def _GetData(self, data_type, file_name=None):
    file_name_map = {
        'build': 'sample_swarming_build_tasks.json',
        'step': 'sample_swarming_build_step_tasks.json'
    }
    file_name = file_name_map.get(data_type, file_name)

    swarming_tasks_file = os.path.join(
        os.path.dirname(__file__), 'data', file_name)
    with open(swarming_tasks_file, 'r') as f:
      return f.read()

  def _SetResponseForGetRequestIsolated(self, url, file_hash):
    self.get_responses[url] = self._GetData('isolated', file_hash)

  def _SetResponseForGetRequestSwarming(
      self, master_name, builder_name, build_number, step_name=None):
    if builder_name == 'download_failed':
      return

    url = ('https://chromium-swarm.appspot.com/_ah/api/swarming/v1/tasks/'
           'list?tags=%s&tags=%s&tags=%s') % (
               urllib.quote('master:%s' % master_name),
               urllib.quote('buildername:%s' % builder_name),
               urllib.quote('buildnumber:%d' % build_number))

    if step_name:
      url += '&tags=%s' % urllib.quote('stepname:%s' % step_name)
      response = self._GetData('step')
    else:
      response = self._GetData('build')

    cursor_swarming_data = {
        'cursor': None,
        'items': [],
        'state': 'all',
        'limit': 100,
        'sort': 'created_ts'
    }
    cursor_url = ('%s&cursor=thisisacursor') % url

    self.get_responses[url] = response
    self.get_responses[cursor_url] = json.dumps(cursor_swarming_data)

  def _SetResponseForPostRequest(self, isolated_hash):
    if isolated_hash == 'not found':
      response = '{"content":"eJyrrgUAAXUA+Q=="}'
    else:
      response = self._GetData('isolated', isolated_hash)

    self.post_responses[isolated_hash] = response

  def _Get(self, url, *_):
    if url in self.get_responses:
      return 200, self.get_responses[url]
    return 404, 'Download Failed!'

  def _Post(self, url, data, *_):
    data = json.loads(data)
    if data and data.get('digest') and data['digest'] in self.post_responses:
      return 200, self.post_responses[data['digest']]
    return 404, 'Download Failed!'

  def _Put(self, *_):  # pragma: no cover
    pass


class _LoggedHttpClient(RetryHttpClient):
  def __init__(self):
    self.responses = collections.defaultdict(dict)
    self.requests = {}

  def _Get(self, url, _, headers):
    self.requests[url] = ('get', None, headers)
    return self.responses.get('get', {}).get(url)

  def _Post(self, url, responses, _, headers):
    self.requests[url] = ('post', responses, headers)
    return self.responses.get('post', {}).get(url, (None, 404))

  def _Put(self, *_):  # pragma: no cover
    pass

  def SetResponse(self, method, url, content=None, status_code=200):
    self.responses[method][url] = (status_code, content)

  def GetRequest(self, url):
    return self.requests.get(url)


class SwarmingUtilTest(testing.AppengineTestCase):
  def setUp(self):
    super(SwarmingUtilTest, self).setUp()
    self.http_client = SwarmingHttpClient()
    self.logged_http_client = _LoggedHttpClient()

  def testGetSwarmingTaskRequest(self):
    task_request_json = {
        'expiration_secs': 2,
        'name': 'name',
        'parent_task_id': 'pti',
        'priority': 1,
        'properties': {
            'command': 'cmd',
            'dimensions': [{'key': 'd', 'value': 'dv'}],
            'env': [{'key': 'e', 'value': 'ev'}],
            'execution_timeout_secs': 4,
            'extra_args': ['--flag'],
            'grace_period_secs': 5,
            'idempotent': True,
            'inputs_ref': {
                'isolated': 'i',
                'isolatedserver': 'is',
                'namespace': 'ns',
            },
            'io_timeout_secs': 3,
        },
        'tags': ['tag'],
        'user': 'user',
    }
    task_id = '1'
    url = ('https://chromium-swarm.appspot.com/'
           '_ah/api/swarming/v1/task/%s/request' % task_id)
    self.logged_http_client.SetResponse(
        'get', url, json.dumps(task_request_json), 200)

    task_request = swarming_util.GetSwarmingTaskRequest(
        task_id, self.logged_http_client)

    self.assertEqual(task_request_json, task_request.Serialize())

  def testTriggerSwarmingTask(self):
    request = SwarmingTaskRequest()
    request.expiration_secs = 2
    request.name = 'name'
    request.parent_task_id = 'pti'
    request.priority = 1
    request.tags = ['tag']
    request.user = 'user'
    request.command = 'cmd'
    request.dimensions = [{'key': 'd', 'value': 'dv'}]
    request.env = [{'key': 'e', 'value': 'ev'}]
    request.execution_timeout_secs = 4
    request.extra_args = ['--flag']
    request.grace_period_secs = 5
    request.idempotent = True
    request.inputs_ref = {'isolated': 'i'}
    request.io_timeout_secs = 3

    url = 'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/tasks/new'
    self.logged_http_client.SetResponse(
        'post', url, json.dumps({'task_id': '1'}), 200)

    expected_task_request_json = {
        'expiration_secs': 72000,
        'name': 'name',
        'parent_task_id': 'pti',
        'priority': 150,
        'properties': {
            'command': 'cmd',
            'dimensions': [{'key': 'd', 'value': 'dv'}],
            'env': [{'key': 'e', 'value': 'ev'}],
            'execution_timeout_secs': 4,
            'extra_args': ['--flag'],
            'grace_period_secs': 5,
            'idempotent': True,
            'inputs_ref': {'isolated': 'i'},
            'io_timeout_secs': 3,
        },
        'tags': ['tag', 'findit:1', 'project:Chromium', 'purpose:post-commit'],
        'user': 'user',
    }

    task_id = swarming_util.TriggerSwarmingTask(
        request, self.logged_http_client)
    self.assertEqual('1', task_id)

    method, data, _ = self.logged_http_client.GetRequest(url)
    self.assertEqual('post', method)
    self.assertEqual(expected_task_request_json, json.loads(data))

  def testGetIsolatedDataForFailedBuild(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'compile': {
            'current_failure': 2,
            'first_failure': 0
        }
    }

    self.http_client._SetResponseForGetRequestSwarming(
        master_name, builder_name, build_number)
    result = swarming_util.GetIsolatedDataForFailedBuild(
        master_name, builder_name, build_number, failed_steps,
        self.http_client)

    expected_failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'list_isolated_data': [
                {
                    'digest': 'isolatedhashatests',
                    'namespace': 'default-gzip',
                    'isolatedserver': 'https://isolateserver.appspot.com'
                }
            ]
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0,
            'list_isolated_data': [
                {
                    'digest': 'isolatedhashunittests',
                    'namespace': 'default-gzip',
                    'isolatedserver': 'https://isolateserver.appspot.com'
                },
                {
                    'digest': 'isolatedhashunittests1',
                    'namespace': 'default-gzip',
                    'isolatedserver': 'https://isolateserver.appspot.com'
                }
            ]
        },
        'compile': {
            'current_failure': 2,
            'first_failure': 0
        }
    }

    for step_name in failed_steps:
      step = WfStep.Get(master_name, builder_name, build_number, step_name)
      if step_name == 'compile':
        self.assertIsNone(step)
      else:
        self.assertIsNotNone(step)

    self.assertTrue(result)
    self.assertEqual(expected_failed_steps, failed_steps)

  def testGetIsolatedDataForFailedBuildDownloadFailed(self):
    master_name = 'm'
    builder_name = 'download_failed'
    build_number = 223
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

    self.http_client._SetResponseForGetRequestSwarming(
        master_name, builder_name, build_number)

    result = swarming_util.GetIsolatedDataForFailedBuild(
        master_name, builder_name, build_number, failed_steps,
        self.http_client)
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

  def testGetIsolatedDataForStep(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    step_name = 'unit_tests'

    self.http_client._SetResponseForGetRequestSwarming(
        master_name, builder_name, build_number, step_name)
    data = swarming_util.GetIsolatedDataForStep(
        master_name, builder_name, build_number, step_name,
        self.http_client)
    expected_data = [
        {
            'digest': 'isolatedhashunittests',
            'namespace': 'default-gzip',
            'isolatedserver': 'https://isolateserver.appspot.com'
        }
    ]
    self.assertEqual(expected_data, data)

  def testGetIsolatedDataForStepFailed(self):
    master_name = 'm'
    builder_name = 'download_failed'
    build_number = 223
    step_name = 's1'

    self.http_client._SetResponseForGetRequestSwarming(
        master_name, builder_name, build_number, step_name)
    task_ids = swarming_util.GetIsolatedDataForStep(
        master_name, builder_name, build_number, step_name,
        self.http_client)
    expected_task_ids = []

    self.assertEqual(expected_task_ids, task_ids)

  def testDownloadTestResults(self):
    isolated_data = {
        'digest': 'shard1_isolated',
        'namespace': 'default-gzip',
        'isolatedserver': 'https://isolateserver.appspot.com'
    }
    self.http_client._SetResponseForPostRequest('shard1_isolated')
    self.http_client._SetResponseForPostRequest('shard1_url')
    self.http_client._SetResponseForGetRequestIsolated(
        'https://isolateserver.storage.googleapis.com/default-gzip/shard1',
        'shard1')

    result = swarming_util._DownloadTestResults(
        isolated_data, self.http_client)

    expected_result = json.loads(zlib.decompress(
        self.http_client._GetData('isolated', 'shard1')))
    self.assertEqual(expected_result, result)

  def testDownloadTestResultsFailedForSecondHash(self):
    isolated_data = {
        'digest': 'not found',
        'namespace': 'default-gzip',
        'isolatedserver': 'https://isolateserver.appspot.com'
    }

    result = swarming_util._DownloadTestResults(
        isolated_data, self.http_client)

    self.assertIsNone(result)


  def testDownloadTestResultsFailedForParsingSecondHash(self):
    isolated_data = {
        'digest': 'not found',
        'namespace': 'default-gzip',
        'isolatedserver': 'https://isolateserver.appspot.com'
    }

    self.http_client._SetResponseForPostRequest('not found')
    result = swarming_util._DownloadTestResults(
        isolated_data, self.http_client)

    self.assertIsNone(result)

  def testDownloadTestResultsFailedForFileUrl(self):
    isolated_data = {
        'digest': 'shard1_isolated',
        'namespace': 'default-gzip',
        'isolatedserver': 'https://isolateserver.appspot.com'
    }
    self.http_client._SetResponseForPostRequest('shard1_isolated')
    result = swarming_util._DownloadTestResults(
        isolated_data, self.http_client)

    self.assertIsNone(result)


  def testDownloadTestResultsFailedForFile(self):
    isolated_data = {
        'digest': 'shard1_isolated',
        'namespace': 'default-gzip',
        'isolatedserver': 'https://isolateserver.appspot.com'
    }
    self.http_client._SetResponseForPostRequest('shard1_isolated')
    self.http_client._SetResponseForPostRequest('shard1_url')
    result = swarming_util._DownloadTestResults(
        isolated_data, self.http_client)

    self.assertIsNone(result)

  def testRetrieveShardedTestResultsFromIsolatedServer(self):
    isolated_data = [
        {
            'digest': 'shard1_isolated',
            'namespace': 'default-gzip',
            'isolatedserver': 'https://isolateserver.appspot.com'
        },
        {
            'digest': 'shard2_isolated',
            'namespace': 'default-gzip',
            'isolatedserver': 'https://isolateserver.appspot.com'
        },
        {
            'digest': 'shard3_isolated',
            'namespace': 'default-gzip',
            'isolatedserver': 'https://isolateserver.appspot.com'
        }
    ]
    self.http_client._SetResponseForPostRequest('shard1_isolated')
    self.http_client._SetResponseForPostRequest('shard1_url')
    self.http_client._SetResponseForGetRequestIsolated(
        'https://isolateserver.storage.googleapis.com/default-gzip/shard1',
        'shard1')
    self.http_client._SetResponseForPostRequest('shard2_isolated')
    self.http_client._SetResponseForPostRequest('shard2_url')
    self.http_client._SetResponseForGetRequestIsolated(
        'https://isolateserver.storage.googleapis.com/default-gzip/shard2',
        'shard2')
    self.http_client._SetResponseForPostRequest('shard3_isolated')
    self.http_client._SetResponseForPostRequest('shard3_url')
    self.http_client._SetResponseForGetRequestIsolated(
        'https://isolateserver.storage.googleapis.com/default-gzip/shard3',
        'shard3')

    result = swarming_util.RetrieveShardedTestResultsFromIsolatedServer(
        isolated_data, self.http_client)
    expected_results_file = os.path.join(
        os.path.dirname(__file__), 'data', 'expected_collect_results')
    with open(expected_results_file, 'r') as f:
      expected_result = json.loads(f.read())

    self.assertEqual(expected_result, result)

  def testRetrieveShardedTestResultsFromIsolatedServerSingleShard(self):
    isolated_data = [
        {
            'digest': 'shard1_isolated',
            'namespace': 'default-gzip',
            'isolatedserver': 'https://isolateserver.appspot.com'
        }
    ]
    self.http_client._SetResponseForPostRequest('shard1_isolated')
    self.http_client._SetResponseForPostRequest('shard1_url')
    self.http_client._SetResponseForGetRequestIsolated(
        'https://isolateserver.storage.googleapis.com/default-gzip/shard1',
        'shard1')

    result = swarming_util.RetrieveShardedTestResultsFromIsolatedServer(
        isolated_data, self.http_client)

    expected_result = json.loads(zlib.decompress(
        self.http_client._GetData('isolated', 'shard1')))
    self.assertEqual(expected_result, result)

  def testRetrieveShardedTestResultsFromIsolatedServerFailed(self):
    isolated_data = [
        {
            'digest': 'shard1_isolated',
            'namespace': 'default-gzip',
            'isolatedserver': 'https://isolateserver.appspot.com'
        }
    ]

    result = swarming_util.RetrieveShardedTestResultsFromIsolatedServer(
        isolated_data, self.http_client)

    self.assertIsNone(result)

  def testRetrieveOutputJsonFileGetDirectly(self):
    output_json_content = ('{"content": "eJyrVkpLzMwpLUotVrKKVgpJLS4xV'
                           'IrVUVAqS8zJTFGyUigpKk2tBQDr9wxZ"}')

    failure_log = swarming_util._RetrieveOutputJsonFile(
        output_json_content, self.http_client)

    expected_failure_log = {
        'failures': ['Test1'],
        'valid': True
    }

    self.assertEqual(expected_failure_log, failure_log)
