# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import mock
import os
import urllib
import zlib

from common import http_client_util
from common.findit_http_client import FinditHttpClient
from libs.http.retry_http_client import RetryHttpClient
from model.wf_config import FinditConfig
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.swarming_task_request import SwarmingTaskRequest
from waterfall.test import wf_testcase

ALL_BOTS = [{'bot_id': 'bot%d' % b} for b in range(10)]
SOME_BOTS = [{'bot_id': 'bot%d' % b} for b in range(3)]
ONE_BOT = [{'bot_id': 'bot%d' % b} for b in range(1)]


class SwarmingHttpClient(RetryHttpClient):

  def __init__(self, interceptor=None):
    self.get_responses = dict()
    self.post_responses = dict()
    self.interceptor = interceptor

  def _GetData(self, data_type, file_name=None):
    file_name_map = {
        'step': 'sample_swarming_build_step_tasks.json',
        'task': 'sample_swarming_task.json'
    }
    file_name = file_name_map.get(data_type, file_name)

    swarming_tasks_file = os.path.join(
        os.path.dirname(__file__), 'data', file_name)
    with open(swarming_tasks_file, 'r') as f:
      return f.read()

  def _SetResponseForGetRequestIsolated(self, url, file_hash):
    self.get_responses[url] = self._GetData('isolated', file_hash)

  def _SetResponseForGetRequestSwarmingList(self, master_name, builder_name,
                                            build_number, step_name):
    if builder_name == 'download_failed':
      return

    url = ('https://%s/api/swarming/v1/tasks/'
           'list?tags=%s&tags=%s&tags=%s') % (
               FinditConfig().Get().swarming_settings.get('server_host'),
               urllib.quote('master:%s' % master_name),
               urllib.quote('buildername:%s' % builder_name),
               urllib.quote('buildnumber:%d' % build_number))

    url += '&tags=%s' % urllib.quote('stepname:%s' % step_name)
    response = self._GetData('step')

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

  def _SetResponseForGetRequestSwarmingResult(self, task_id):
    url = ('https://%s/api/swarming/v1/task/%s/result') % (
        FinditConfig().Get().swarming_settings.get('server_host'), task_id)

    response = self._GetData('task')
    self.get_responses[url] = response

  def _SetResponseForPostRequest(self, isolated_hash):
    if isolated_hash == 'not found':
      response = '{"content":"eJyrrgUAAXUA+Q=="}'
    else:
      response = self._GetData('isolated', isolated_hash)

    self.post_responses[isolated_hash] = response

  def _Get(self, url, *_):
    if url in self.get_responses:
      return 200, self.get_responses[url], {}
    return 404, 'Download Failed!', {}

  def _Post(self, url, data, *_):
    data = json.loads(data)
    if data and data.get('digest') and data['digest'] in self.post_responses:
      return 200, self.post_responses[data['digest']], {}
    return 404, 'Download Failed!', {}

  def _Put(self, *_):  # pragma: no cover
    pass


class _LoggedHttpClient(RetryHttpClient):

  def __init__(self, interceptor=None):
    self.responses = collections.defaultdict(dict)
    self.requests = {}
    self.interceptor = interceptor

  def _Get(self, url, _, headers):
    self.requests[url] = ('get', None, headers)
    return self.responses.get('get', {}).get(url)

  def _Post(self, url, responses, _, headers):
    self.requests[url] = ('post', responses, headers)
    return self.responses.get('post', {}).get(url, (None, 404))

  def _Put(self, *_):  # pragma: no cover
    pass

  def SetResponse(self, method, url, content=None, status_code=200):
    self.responses[method][url] = (status_code, content, {})

  def GetRequest(self, url):
    return self.requests.get(url)


class SwarmingUtilTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(SwarmingUtilTest, self).setUp()
    self.http_client = SwarmingHttpClient()
    self.logged_http_client = _LoggedHttpClient()
    self.step_name = 'browser_tests on platform'

  def testGetSwarmingTaskRequest(self):
    task_request_json = {
        'expiration_secs': 2,
        'name': 'name',
        'parent_task_id': 'pti',
        'priority': 1,
        'properties': {
            'command': 'cmd',
            'dimensions': [{
                'key': 'd',
                'value': 'dv'
            }],
            'env': [{
                'key': 'e',
                'value': 'ev'
            }],
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
        'pubsub_topic': None,
        'pubsub_auth_token': None,
        'pubsub_userdata': None,
    }
    task_id = '1'
    url = ('https://chromium-swarm.appspot.com/api/swarming/v1/task/%s/request'
           % task_id)
    self.logged_http_client.SetResponse('get', url,
                                        json.dumps(task_request_json), 200)

    task_request = swarming_util.GetSwarmingTaskRequest(task_id,
                                                        self.logged_http_client)

    self.assertEqual(task_request_json, task_request.Serialize())

  @mock.patch.object(
      http_client_util,
      'SendRequestToServer',
      return_value=(None, {
          'code': 1,
          'message': 'error'
      }))
  def testGetSwarmingTaskRequestError(self, _):
    self.assertIsNone(
        swarming_util.GetSwarmingTaskRequest('task_id1', FinditHttpClient()))

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

    url = 'https://chromium-swarm.appspot.com/api/swarming/v1/tasks/new'
    self.logged_http_client.SetResponse('post', url, json.dumps({
        'task_id': '1'
    }), 200)

    expected_task_request_json = {
        'expiration_secs': 72000,
        'name': 'name',
        'parent_task_id': 'pti',
        'priority': 150,
        'properties': {
            'command': 'cmd',
            'dimensions': [{
                'key': 'd',
                'value': 'dv'
            }],
            'env': [{
                'key': 'e',
                'value': 'ev'
            }],
            'execution_timeout_secs': 4,
            'extra_args': ['--flag'],
            'grace_period_secs': 5,
            'idempotent': True,
            'inputs_ref': {
                'isolated': 'i'
            },
            'io_timeout_secs': 3,
        },
        'tags': ['tag', 'findit:1', 'project:Chromium', 'purpose:post-commit'],
        'user': 'user',
        'pubsub_topic': None,
        'pubsub_auth_token': None,
        'pubsub_userdata': None,
    }

    task_id, error = swarming_util.TriggerSwarmingTask(request,
                                                       self.logged_http_client)
    self.assertEqual('1', task_id)
    self.assertIsNone(error)

    method, data, _ = self.logged_http_client.GetRequest(url)
    self.assertEqual('post', method)
    self.assertEqual(expected_task_request_json, json.loads(data))

  @mock.patch.object(
      http_client_util,
      'SendRequestToServer',
      return_value=(None, {
          'code': 1,
          'message': 'error'
      }))
  def testTriggerSwarmingTaskError(self, _):
    request = SwarmingTaskRequest()
    task_id, error = swarming_util.TriggerSwarmingTask(request,
                                                       FinditHttpClient())
    self.assertIsNone(task_id)
    self.assertIsNotNone(error)

  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags')
  def testGetIsolatedShaForStep(self, mocked_list_swarming_tasks_data):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    mocked_http_client = None
    isolated_sha = 'a1b2c3d4'

    mocked_list_swarming_tasks_data.return_value = [{
        'tags': ['data:%s' % isolated_sha]
    }]

    self.assertEqual(isolated_sha,
                     swarming_util.GetIsolatedShaForStep(
                         master_name, builder_name, build_number, step_name,
                         mocked_http_client))

  @mock.patch.object(
      swarming_util, 'ListSwarmingTasksDataByTags', return_value=None)
  def testGetIsolatedShaForStepNoData(self, _):
    mocked_http_client = None
    self.assertIsNone(
        swarming_util.GetIsolatedShaForStep('m', 'b', 123, 's',
                                            mocked_http_client))

  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags')
  def testGetIsolatedShaForStepNoShaFound(self,
                                          mocked_list_swarming_tasks_data):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    mocked_http_client = None

    mocked_list_swarming_tasks_data.return_value = [{
        'tags': ['some', 'random', 'tags']
    }]

    self.assertIsNone(
        swarming_util.GetIsolatedShaForStep(master_name, builder_name,
                                            build_number, step_name,
                                            mocked_http_client))

  def testGetIsolatedDataForStep(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    step_name = 'unit_tests'

    self.http_client._SetResponseForGetRequestSwarmingList(
        master_name, builder_name, build_number, step_name)
    data = swarming_util.GetIsolatedDataForStep(
        master_name, builder_name, build_number, step_name, self.http_client)
    expected_data = [{
        'digest':
            'isolatedhashunittests',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }]
    self.assertEqual(expected_data, data)

  def testGetIsolatedDataForStepNotOnlyFailure(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    step_name = 'unit_tests'

    self.http_client._SetResponseForGetRequestSwarmingList(
        master_name, builder_name, build_number, step_name)
    data = swarming_util.GetIsolatedDataForStep(
        master_name,
        builder_name,
        build_number,
        step_name,
        self.http_client,
        only_failure=False)
    expected_data = [{
        'digest':
            'isolatedhashunittests',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }, {
        'digest':
            'isolatedhashunittests1',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }]
    self.assertEqual(sorted(expected_data), sorted(data))

  def testGetIsolatedDataForStepFailed(self):
    master_name = 'm'
    builder_name = 'download_failed'
    build_number = 223
    step_name = 's1'

    self.http_client._SetResponseForGetRequestSwarmingList(
        master_name, builder_name, build_number, step_name)

    data = swarming_util.GetIsolatedDataForStep(
        master_name, builder_name, build_number, step_name, self.http_client)

    self.assertEqual([], data)

  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags')
  def testGetIsolatedDataForStepNoOutputsRef(self, mock_data):
    master_name = 'm'
    builder_name = 'download_failed'
    build_number = 223
    step_name = 's1'

    mock_data.return_value = [{'failure': True}, {'failure': False}]

    data = swarming_util.GetIsolatedDataForStep(
        master_name, builder_name, build_number, step_name, self.http_client)
    expected_data = []

    self.assertEqual(expected_data, data)

  def testDownloadTestResults(self):
    isolated_data = {
        'digest':
            'shard1_isolated',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }
    isolated_storage_url = waterfall_config.GetSwarmingSettings().get(
        'isolated_storage_url')
    self.http_client._SetResponseForPostRequest('shard1_isolated')
    self.http_client._SetResponseForPostRequest('shard1_url')
    self.http_client._SetResponseForGetRequestIsolated(
        'https://%s/default-gzip/shard1' % isolated_storage_url, 'shard1')

    result, error = swarming_util.DownloadTestResults(isolated_data,
                                                      self.http_client)

    expected_result = json.loads(
        zlib.decompress(self.http_client._GetData('isolated', 'shard1')))
    self.assertEqual(expected_result, result)
    self.assertIsNone(error)

  def testDownloadTestResultsFailedForSecondHash(self):
    isolated_data = {
        'digest':
            'not found',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }

    result, error = swarming_util.DownloadTestResults(isolated_data,
                                                      self.http_client)

    self.assertIsNone(result)
    self.assertIsNotNone(error)

  def testDownloadTestResultsFailedForParsingSecondHash(self):
    isolated_data = {
        'digest':
            'not found',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }

    self.http_client._SetResponseForPostRequest('not found')
    result, error = swarming_util.DownloadTestResults(isolated_data,
                                                      self.http_client)

    self.assertIsNone(result)
    self.assertIsNone(error)

  def testDownloadTestResultsFailedForFileUrl(self):
    isolated_data = {
        'digest':
            'shard1_isolated',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }
    self.http_client._SetResponseForPostRequest('shard1_isolated')
    result, error = swarming_util.DownloadTestResults(isolated_data,
                                                      self.http_client)

    self.assertIsNone(result)
    self.assertIsNotNone(error)

  def testDownloadTestResultsFailedForFile(self):
    isolated_data = {
        'digest':
            'shard1_isolated',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }
    self.http_client._SetResponseForPostRequest('shard1_isolated')
    self.http_client._SetResponseForPostRequest('shard1_url')
    result, error = swarming_util.DownloadTestResults(isolated_data,
                                                      self.http_client)

    self.assertIsNone(result)
    self.assertIsNone(error)

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  @mock.patch.object(swarming_util, '_FetchOutputJsonInfoFromIsolatedServer')
  def testDownloadTestResultsNeedRequestToUrl(self, mock_fetch, mock_send):
    isolated_data = {
        'digest':
            'shard1_isolated',
        'namespace':
            'default-gzip',
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server')
    }
    fetch_content1 = {'url': 'url_hash'}
    fetch_content2 = {'url': 'url_test_log'}
    mock_fetch.side_effect = [(json.dumps(fetch_content1), None),
                              (json.dumps(fetch_content2), None)]

    send_content1 = {'files': {'output.json': {'h': 'output_json_hash'}}}
    send_content2 = {'all_tests': []}
    mock_send.side_effect = [(zlib.compress(json.dumps(send_content1)), None),
                             (zlib.compress(json.dumps(send_content2)), None)]

    result, _ = swarming_util.DownloadTestResults(isolated_data,
                                                  self.http_client)

    self.assertEqual(send_content2, result)

  def testGetSwarmingTaskResultById(self):
    task_id = '2944afa502297110'

    self.http_client._SetResponseForGetRequestSwarmingResult(task_id)

    data, error = swarming_util.GetSwarmingTaskResultById(
        task_id, self.http_client)

    expected_outputs_ref = {
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server'),
        'namespace':
            'default-gzip',
        'isolated':
            'shard1_isolated'
    }

    self.assertEqual('COMPLETED', data['state'])
    self.assertEqual(expected_outputs_ref, data['outputs_ref'])
    self.assertIsNone(error)

  @mock.patch.object(
      http_client_util,
      'SendRequestToServer',
      return_value=(None, {
          'code': 1,
          'message': 'error'
      }))
  def testGetSwarmingTaskResultByIdError(self, _):
    data, error = swarming_util.GetSwarmingTaskResultById(
        'task_id', FinditHttpClient())
    self.assertEqual({}, data)
    self.assertIsNotNone(error)

  def testGetSwarmingTaskFailureLog(self):
    outputs_ref = {
        'isolatedserver':
            waterfall_config.GetSwarmingSettings().get('isolated_server'),
        'namespace':
            'default-gzip',
        'isolated':
            'shard1_isolated'
    }

    self.http_client._SetResponseForPostRequest('shard1_isolated')
    self.http_client._SetResponseForPostRequest('shard1_url')
    self.http_client._SetResponseForGetRequestIsolated(
        'https://%s/default-gzip/shard1' %
        (waterfall_config.GetSwarmingSettings().get('isolated_storage_url')),
        'shard1')

    result, error = swarming_util.GetSwarmingTaskFailureLog(
        outputs_ref, self.http_client)

    expected_result = json.loads(
        zlib.decompress(self.http_client._GetData('isolated', 'shard1')))
    self.assertEqual(expected_result, result)
    self.assertIsNone(error)

  def testProcessRetrievedContentGetDirectly(self):
    output_json_content = ('{"content": "eJyrVkpLzMwpLUotVrKKVgpJLS4xV'
                           'IrVUVAqS8zJTFGyUigpKk2tBQDr9wxZ"}')

    failure_log = swarming_util._ProcessRetrievedContent(
        output_json_content, self.http_client)

    expected_failure_log = {'failures': ['Test1'], 'valid': True}

    self.assertEqual(expected_failure_log, failure_log)

  def testGetTagValueInvalidTag(self):
    tags = ['a:1', 'b:2']
    self.assertIsNone(swarming_util.GetTagValue(tags, 'c'))

  def testGenerateIsolatedDataOutputsrefNone(self):
    self.assertEqual({}, swarming_util.GenerateIsolatedData(None))

  def testFetchOutputJsonInfoFromIsolatedServerReturnNone(self):
    self.assertIsNone(
        swarming_util._FetchOutputJsonInfoFromIsolatedServer(
            None, self.http_client))

  @mock.patch.object(
      swarming_util,
      'GetSwarmingTaskResultById',
      return_value=({
          'outputs_ref': 'ref'
      }, None))
  @mock.patch.object(
      swarming_util, 'GetSwarmingTaskFailureLog', return_value=(None, 'error'))
  def testGetIsolatedOutputForTaskIsolatedError(self, *_):
    self.assertIsNone(swarming_util.GetIsolatedOutputForTask(None, None))

  @mock.patch.object(
      swarming_util,
      'GetSwarmingTaskResultById',
      return_value=({
          'a': []
      }, None))
  def testGetIsolatedOutputForTaskNoOutputRef(self, _):
    self.assertIsNone(swarming_util.GetIsolatedOutputForTask(None, None))

  @mock.patch.object(
      swarming_util, 'GetSwarmingTaskResultById', return_value=(None, 'error'))
  def testGetIsolatedOutputForTaskDataError(self, _):
    self.assertIsNone(swarming_util.GetIsolatedOutputForTask(None, None))

  def testGetIsolatedOutputForTask(self):
    task_id = '2944afa502297110'
    self.http_client._SetResponseForGetRequestSwarmingResult(task_id)
    self.http_client._SetResponseForPostRequest('shard1_isolated')
    self.http_client._SetResponseForPostRequest('shard1_url')
    self.http_client._SetResponseForGetRequestIsolated(
        'https://%s/default-gzip/shard1' %
        (waterfall_config.GetSwarmingSettings().get('isolated_storage_url')),
        'shard1')

    result = swarming_util.GetIsolatedOutputForTask(task_id, self.http_client)

    expected_result = json.loads(
        zlib.decompress(self.http_client._GetData('isolated', 'shard1')))
    self.assertEqual(expected_result, result)

  def testDimensionsToQueryString(self):
    self.assertEqual(
        swarming_util.DimensionsToQueryString({
            'bot_id': 'slave1'
        }), swarming_util.DimensionsToQueryString(['bot_id:slave1']))
    self.assertEqual(
        '?dimensions=bot_id:slave1&dimensions=cpu:x86_64&dimensions=os:Mac',
        # Use Ordered dict to preserve the order of the dimensions.
        swarming_util.DimensionsToQueryString(
            collections.OrderedDict([('bot_id', 'slave1'), ('cpu', 'x86_64'),
                                     ('os', 'Mac')])))
    self.assertEqual(
        '?dimensions=bot_id:slave1&dimensions=cpu:x86_64&dimensions=os:Mac',
        swarming_util.DimensionsToQueryString(
            ['bot_id:slave1', 'cpu:x86_64', 'os:Mac']))

  def testGetSwarmingBotCountsNodimentsions(self):
    self.assertEqual({}, swarming_util.GetSwarmingBotCounts(None, None))

  @mock.patch.object(http_client_util, 'SendRequestToServer')
  def testGetSwarmingBotCounts(self, mock_fn):

    dimensions = {'os': 'OS', 'cpu': 'cpu'}

    content_data = {'count': '10', 'dead': '1', 'quarantined': '0', 'busy': '5'}
    mock_fn.return_value = (json.dumps(content_data), None)

    expected_counts = {
        'count': 10,
        'dead': 1,
        'quarantined': 0,
        'busy': 5,
        'available': 4
    }

    self.assertEqual(expected_counts,
                     swarming_util.GetSwarmingBotCounts(dimensions, None))

  @mock.patch.object(
      http_client_util,
      'SendRequestToServer',
      return_value=(None, {
          'code': 1,
          'message': 'error'
      }))
  def testGetSwarmingBotCountsError(self, _):

    dimensions = {'os': 'OS', 'cpu': 'cpu'}
    self.assertEqual({}, swarming_util.GetSwarmingBotCounts(dimensions, None))
