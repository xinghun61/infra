# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import os
import zlib

from infra_api_clients.swarming import swarming_util as i_swarming_util
from libs.http.retry_http_client import RetryHttpClient
from model.wf_config import FinditConfig
from waterfall import swarming_util
from waterfall import waterfall_config
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

  def _SetResponseForGetRequestSwarmingResult(self, task_id):
    url = ('https://%s/api/swarming/v1/task/%s/result') % (
        FinditConfig().Get().swarming_settings.get('server_host'), task_id)

    response = self._GetData('task')
    self.get_responses[url] = response

  def _SetResponseForPostRequest(self, isolated_hash):
    response = self._GetData('isolated', isolated_hash)

    self.post_responses[isolated_hash] = response

  def _Get(self, url, *_):
    return 200, self.get_responses[url], {}

  def _Post(self, url, data, *_):
    data = json.loads(data)
    return 200, self.post_responses[data['digest']], {}

  def _Put(self, *_):  # pragma: no cover
    pass


class SwarmingUtilTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(SwarmingUtilTest, self).setUp()
    self.http_client = SwarmingHttpClient()
    self.step_name = 'browser_tests on platform'

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

  @mock.patch.object(
      i_swarming_util,
      'GetSwarmingTaskResultById',
      return_value=({
          'outputs_ref': 'ref'
      }, None))
  @mock.patch.object(
      swarming_util, 'GetSwarmingTaskFailureLog', return_value=(None, 'error'))
  def testGetIsolatedOutputForTaskIsolatedError(self, *_):
    self.assertIsNone(swarming_util.GetIsolatedOutputForTask(None, None))

  @mock.patch.object(
      i_swarming_util,
      'GetSwarmingTaskResultById',
      return_value=({
          'a': []
      }, None))
  def testGetIsolatedOutputForTaskNoOutputRef(self, _):
    self.assertIsNone(swarming_util.GetIsolatedOutputForTask(None, None))

  @mock.patch.object(
      i_swarming_util,
      'GetSwarmingTaskResultById',
      return_value=(None, 'error'))
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
