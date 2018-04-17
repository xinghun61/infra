# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import time

from dto import swarming_task_error
from dto.swarming_task_error import SwarmingTaskError
from dto.test_location import TestLocation
from infra_api_clients.swarming import swarming_util
from libs import analysis_status
from libs.test_results import test_results_util
from libs.test_results.gtest_test_results import GtestTestResults
from model.wf_swarming_task import WfSwarmingTask
from services import constants
from services import isolate
from services import swarmed_test_util
from waterfall import waterfall_config
from waterfall.test import wf_testcase

_GTEST_RESULTS = GtestTestResults(None)


class SwarmedTestUtilTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(
      swarmed_test_util, 'GetTestResultForSwarmingTask', return_value={})
  def testGetTestLocationNoTestLocations(self, _):
    self.assertIsNone(swarmed_test_util.GetTestLocation('task', 'test'))

  @mock.patch.object(
      GtestTestResults, 'IsTestResultsInExpectedFormat', return_value=True)
  @mock.patch.object(swarmed_test_util, 'GetTestResultForSwarmingTask')
  def testGetTestLocation(self, mock_get_isolated_output, _):
    test_name = 'test'
    expected_test_location = {
        'line': 123,
        'file': '/path/to/test_file.cc',
    }
    mock_get_isolated_output.return_value = {
        'test_locations': {
            test_name: expected_test_location,
        }
    }

    self.assertEqual(
        TestLocation.FromSerializable(expected_test_location),
        swarmed_test_util.GetTestLocation('task', test_name))

  @mock.patch.object(
      isolate,
      'DownloadFileFromIsolatedServer',
      return_value=(json.dumps({
          'all_tests': ['test1']
      }), None))
  def testGetOutputJsonByOutputsRef(self, _):
    outputs_ref = {
        'isolatedserver': 'isolated_server',
        'namespace': 'default-gzip',
        'isolated': 'shard1_isolated'
    }

    result, error = swarmed_test_util.GetOutputJsonByOutputsRef(
        outputs_ref, None)

    self.assertEqual({'all_tests': ['test1']}, result)
    self.assertIsNone(error)

  @mock.patch.object(
      swarmed_test_util,
      'GetTestResultForSwarmingTask',
      return_value='test_result_log')
  @mock.patch.object(_GTEST_RESULTS, 'IsTestEnabled', return_value=True)
  @mock.patch.object(
      test_results_util, 'GetTestResultObject', return_value=_GTEST_RESULTS)
  def testIsTestEnabled(self, *_):
    self.assertTrue(swarmed_test_util.IsTestEnabled('test', '123'))

  def testRetrieveShardedTestResultsFromIsolatedServerNoLog(self):
    self.assertEqual(
        [],
        swarmed_test_util.RetrieveShardedTestResultsFromIsolatedServer([],
                                                                       None))

  @mock.patch.object(
      GtestTestResults, 'IsTestResultsInExpectedFormat', return_value=True)
  @mock.patch.object(isolate, 'DownloadFileFromIsolatedServer')
  def testRetrieveShardedTestResultsFromIsolatedServer(self, mock_data, _):
    isolated_data = [{
        'digest': 'shard1_isolated',
        'namespace': 'default-gzip',
        'isolatedserver': 'isolated_server'
    }, {
        'digest': 'shard2_isolated',
        'namespace': 'default-gzip',
        'isolatedserver': 'isolated_server'
    }]

    mock_data.side_effect = [(json.dumps({
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test1': [{
                'output_snippet': '[ RUN ] test1.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }), 200), (json.dumps({
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test2': [{
                'output_snippet': '[ RUN ] test2.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }), 200)]
    result = swarmed_test_util.RetrieveShardedTestResultsFromIsolatedServer(
        isolated_data, None)
    expected_result = {
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test1': [{
                'output_snippet': '[ RUN ] test1.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }],
            'test2': [{
                'output_snippet': '[ RUN ] test2.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }

    self.assertEqual(expected_result, result)

  @mock.patch.object(
      GtestTestResults, 'IsTestResultsInExpectedFormat', return_value=True)
  @mock.patch.object(isolate, 'DownloadFileFromIsolatedServer')
  def testRetrieveShardedTestResultsFromIsolatedServerOneShard(
      self, mock_data, _):
    isolated_data = [{
        'digest': 'shard1_isolated',
        'namespace': 'default-gzip',
        'isolatedserver': 'isolated_server'
    }]
    data_json = {'all_tests': ['test'], 'per_iteration_data': []}
    data_str = json.dumps(data_json)
    mock_data.return_value = (data_str, 200)

    result = swarmed_test_util.RetrieveShardedTestResultsFromIsolatedServer(
        isolated_data, None)

    self.assertEqual(data_json, result)

  @mock.patch.object(
      GtestTestResults, 'IsTestResultsInExpectedFormat', return_value=True)
  @mock.patch.object(isolate, 'DownloadFileFromIsolatedServer')
  def testRetrieveShardedTestResultsFromIsolatedServerFailed(
      self, mock_data, _):
    isolated_data = [{
        'digest': 'shard1_isolated',
        'namespace': 'default-gzip',
        'isolatedserver': 'isolated_server'
    }]
    mock_data.return_value = (None, 404)

    result = swarmed_test_util.RetrieveShardedTestResultsFromIsolatedServer(
        isolated_data, None)

    self.assertIsNone(result)

  def testGetTaskIdFromSwarmingTaskEntity(self):
    swarming_task = WfSwarmingTask.Create('m', 'b', 123, 's')
    swarming_task.task_id = 'task_id'
    swarming_task.put()

    self.assertEqual('task_id',
                     swarmed_test_util.GetTaskIdFromSwarmingTaskEntity(
                         swarming_task.key.urlsafe()))

  def testGetTaskIdFromSwarmingTaskEntityNoTask(self):
    swarming_task = WfSwarmingTask.Create('m', 'b', 200, 's')
    swarming_task.put()
    key = swarming_task.key.urlsafe()
    swarming_task.key.delete()
    with self.assertRaises(Exception):
      swarmed_test_util.GetTaskIdFromSwarmingTaskEntity(key)

  @mock.patch.object(
      waterfall_config,
      'GetSwarmingSettings',
      return_value={
          'get_swarming_task_id_wait_seconds': 0,
          'get_swarming_task_id_timeout_seconds': -1
      })
  def testGetTaskIdFromSwarmingTaskEntityTimeOut(self, _):
    swarming_task = WfSwarmingTask.Create('m', 'b', 123, 's')
    swarming_task.put()
    with self.assertRaises(Exception):
      swarmed_test_util.GetTaskIdFromSwarmingTaskEntity(
          swarming_task.key.urlsafe())

  def testWaitingForTheTaskId(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'

    swarming_task = WfSwarmingTask.Create(master_name, builder_name,
                                          build_number, step_name)
    swarming_task.status = analysis_status.PENDING
    swarming_task.put()

    def MockedSleep(*_):
      swarming_task = WfSwarmingTask.Get(master_name, builder_name,
                                         build_number, step_name)
      self.assertEqual(analysis_status.PENDING, swarming_task.status)
      swarming_task.status = analysis_status.RUNNING
      swarming_task.task_id = 'task_id'
      swarming_task.put()

    self.mock(time, 'sleep', MockedSleep)

    self.assertEqual('task_id',
                     swarmed_test_util.GetTaskIdFromSwarmingTaskEntity(
                         swarming_task.key.urlsafe()))

  @mock.patch.object(swarming_util, 'GetSwarmingTaskResultById')
  def testGetSwarmingTaskDataAndResultNoData(self, mock_fn):
    error = {'code': 1, 'message': 'error'}
    mock_fn.return_value = (None, error)
    self.assertEqual((None, None, SwarmingTaskError.FromSerializable(error)),
                     swarmed_test_util.GetSwarmingTaskDataAndResult(
                         'task_id', None))

  @mock.patch.object(swarming_util, 'GetSwarmingTaskResultById')
  def testGetSwarmingTaskDataAndResultFailedState(self, mock_fn):
    data = {'state': 'BOT_DIED', 'outputs_ref': 'outputs_ref'}
    mock_fn.return_value = (data, None)
    error = SwarmingTaskError.FromSerializable({
        'code': swarming_task_error.BOT_DIED,
        'message': 'BOT_DIED'
    })
    self.assertEqual((data, None, error),
                     swarmed_test_util.GetSwarmingTaskDataAndResult(
                         'task_id', None))

  @mock.patch.object(swarming_util, 'GetSwarmingTaskResultById')
  def testGetSwarmingTaskDataAndResultRunning(self, mock_fn):
    data = {'state': constants.STATE_RUNNING, 'outputs_ref': 'outputs_ref'}
    mock_fn.return_value = (data, None)
    self.assertEqual((data, None, None),
                     swarmed_test_util.GetSwarmingTaskDataAndResult(
                         'task_id', None))

  @mock.patch.object(
      swarmed_test_util,
      'GetOutputJsonByOutputsRef',
      return_value=(None, 'error'))
  @mock.patch.object(swarming_util, 'GetSwarmingTaskResultById')
  def testGetSwarmingTaskDataAndResultIsolatedError(self, mock_fn, _):
    data = {'outputs_ref': 'ref', 'state': constants.STATE_COMPLETED}
    mock_fn.return_value = (data, None)

    self.assertEqual((data, None, 'error'),
                     swarmed_test_util.GetSwarmingTaskDataAndResult(None, None))

  @mock.patch.object(
      swarming_util,
      'GetSwarmingTaskResultById',
      return_value=({
          'state': constants.STATE_COMPLETED
      }, None))
  def testGetSwarmingTaskDataAndResultNoOutputRef(self, mock_fn):
    data = {'state': constants.STATE_COMPLETED}
    mock_fn.return_value = (data, None)

    error = SwarmingTaskError.FromSerializable({
        'code': swarming_task_error.NO_TASK_OUTPUTS,
        'message': 'outputs_ref is None'
    })
    self.assertEqual((data, None, error),
                     swarmed_test_util.GetSwarmingTaskDataAndResult(None, None))

  @mock.patch.object(test_results_util, 'IsTestResultsValid', return_value=True)
  @mock.patch.object(
      swarmed_test_util,
      'GetOutputJsonByOutputsRef',
      return_value=('content', None))
  @mock.patch.object(
      swarming_util,
      'GetSwarmingTaskResultById',
      return_value=({
          'outputs_ref': 'ref',
          'state': constants.STATE_COMPLETED
      }, None))
  def testGetSwarmingTaskDataAndResult(self, mock_fn, *_):
    task_id = '2944afa502297110'
    data, result, error = swarmed_test_util.GetSwarmingTaskDataAndResult(
        task_id, None)

    self.assertEqual({
        'outputs_ref': 'ref',
        'state': constants.STATE_COMPLETED
    }, data)
    self.assertEqual('content', result)
    self.assertIsNone(error)
    mock_fn.assert_called_once_with('chromium-swarm.appspot.com', task_id, None)

  @mock.patch.object(
      swarmed_test_util,
      'GetSwarmingTaskDataAndResult',
      return_value=('data', 'content', 'error'))
  def testGetTestResultForSwarmingTask(self, mock_fn):
    self.assertEqual('content',
                     swarmed_test_util.GetTestResultForSwarmingTask(
                         'task_id', None))
    mock_fn.assert_called_once_with('task_id', None)
