# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock

from google.appengine.ext import ndb

from common.waterfall import failure_type
from dto import swarming_task_error
from dto.collect_swarming_task_results_inputs import (
    CollectSwarmingTaskResultsInputs)
from dto.collect_swarming_task_results_outputs import (
    CollectSwarmingTaskResultsOutputs)
from dto.run_swarming_task_parameters import RunSwarmingTaskParameters
from dto.run_swarming_tasks_input import RunSwarmingTasksInput
from dto.swarming_task_error import SwarmingTaskError
from infra_api_clients.swarming.swarming_task_request import SwarmingTaskRequest
from infra_api_clients.swarming import swarming_util
from libs import analysis_status
from model.wf_swarming_task import WfSwarmingTask
from services import constants
from services.parameters import BuildKey
from services.parameters import TestFailureInfo
from services.parameters import TestHeuristicAnalysisOutput
from services.parameters import TestHeuristicResult
from services import swarmed_test_util
from services import swarming
from services import test_results
from services.test_failure import test_failure_analysis
from services.test_failure import test_swarming
from waterfall.test import wf_testcase

_SAMPLE_REQUEST_JSON = {
    'expiration_secs':
        '3600',
    'name':
        'findit/ref_task_id/ref_task_id/2018-03-15 00:00:00 000000',
    'parent_task_id':
        '',
    'priority':
        '25',
    'properties': {
        'command':
            'cmd',
        'dimensions': [{
            'key': 'k',
            'value': 'v'
        }],
        'env': [{
            'key': 'a',
            'value': '1'
        },],
        'execution_timeout_secs':
            '10',
        'extra_args': [
            '--flag=value',
            '--gtest_filter=a.b:a.c',
            '--gtest_repeat=30',
            '--test-launcher-retry-limit=0',
            '--gtest_also_run_disabled_tests',
        ],
        'grace_period_secs':
            '30',
        'idempotent':
            False,
        'inputs_ref': {
            'isolatedserver': 'isolatedserver',
            'isolated': 'sha'
        },
        'io_timeout_secs':
            '1200',
    },
    'tags': [
        'ref_master:m',
        'ref_buildername:b',
        'ref_buildnumber:4',
        'ref_stepname:s',
        'ref_name:test',
    ],
    'user':
        '',
    'pubsub_auth_token':
        'auth_token',
    'pubsub_topic':
        'projects/app-id/topics/swarming',
    'pubsub_userdata':
        json.dumps({
            'runner_id': 'runner_id'
        }),
}


class TestSwarmingTest(wf_testcase.WaterfallTestCase):

  def testNeedANewSwarmingTaskCreateANewOne(self):
    need, urlsafe_task_key = test_swarming.NeedANewSwarmingTask(
        'm', 'b', 1, 's', False)
    self.assertTrue(need)

    swarming_task = ndb.Key(urlsafe=urlsafe_task_key).get()
    self.assertIsNotNone(swarming_task)

  def testNeedANewSwarmingTaskForce(self):
    swarming_task = WfSwarmingTask.Create('m', 'b', 2, 's')
    swarming_task.status = analysis_status.ERROR
    swarming_task.put()
    need, urlsafe_task_key = test_swarming.NeedANewSwarmingTask(
        'm', 'b', 2, 's', True)
    self.assertTrue(need)
    swarming_task = ndb.Key(urlsafe=urlsafe_task_key).get()
    self.assertEqual(analysis_status.PENDING, swarming_task.status)

  def testNotNeedANewSwarmingTask(self):
    swarming_task = WfSwarmingTask.Create('m', 'b', 3, 's')
    swarming_task.status = analysis_status.ERROR
    swarming_task.put()
    need, _ = test_swarming.NeedANewSwarmingTask('m', 'b', 3, 's', False)
    self.assertFalse(need)

  @mock.patch.object(test_swarming, 'FinditHttpClient', return_value=None)
  @mock.patch.object(
      swarming_util, 'TriggerSwarmingTask', return_value=('new_task_id', None))
  @mock.patch.object(swarming, 'CreateNewSwarmingTaskRequestTemplate')
  @mock.patch.object(
      swarming,
      'GetReferredSwarmingTaskRequestInfo',
      return_value=('task_id', 'ref_request'))
  def testTriggerSwarmingTask(self, mock_ref, mock_create, mock_trigger, _):
    runner_id = 'runner_id'
    master_name = 'm'
    builder_name = 'b'
    build_number = 6
    step_name = 's'
    tests = ['test']
    WfSwarmingTask.Create(master_name, builder_name, build_number,
                          step_name).put()
    parameters = RunSwarmingTaskParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        step_name=step_name,
        tests=tests)
    new_request = SwarmingTaskRequest.FromSerializable(_SAMPLE_REQUEST_JSON)
    mock_create.return_value = new_request
    task_id = test_swarming.TriggerSwarmingTask(parameters, runner_id)
    self.assertEqual('new_task_id', task_id)

    mock_ref.assert_called_once_with(master_name, builder_name, build_number,
                                     step_name, None)
    mock_create.assert_called_once_with(
        'runner_id',
        'task_id',
        'ref_request',
        master_name,
        builder_name,
        step_name,
        tests,
        10,
        use_new_pubsub=True)
    mock_trigger.assert_called_once_with('chromium-swarm.appspot.com',
                                         new_request, None)

  def testOnSwarmingTaskTriggered(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 6
    step_name = 's'
    task = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                 step_name)
    task.put()
    task_id = 'task_id'
    tests = ['t']
    iterations = 100
    new_request = {
        'expiration_secs':
            '3600',
        'name':
            'findit/ref_task_id/ref_task_id/2018-03-15 00:00:00 000000',
        'parent_task_id':
            '',
        'priority':
            '25',
        'properties': {
            'command':
                'cmd',
            'dimensions': [{
                'key': 'k',
                'value': 'v'
            }],
            'env': [{
                'key': 'a',
                'value': '1'
            },],
            'execution_timeout_secs':
                '10',
            'extra_args': [
                '--flag=value',
                '--gtest_filter=a.b:a.c',
                '--gtest_repeat=30',
                '--test-launcher-retry-limit=0',
                '--gtest_also_run_disabled_tests',
            ],
            'grace_period_secs':
                '30',
            'idempotent':
                False,
            'inputs_ref': {
                'isolatedserver': 'isolatedserver',
                'isolated': 'sha'
            },
            'io_timeout_secs':
                '1200',
        },
        'tags': [
            'ref_master:m',
            'ref_buildername:b',
            'ref_buildnumber:4',
            'ref_stepname:s',
            'ref_name:test',
        ],
        'user':
            '',
        'pubsub_auth_token':
            'auth_token',
        'pubsub_topic':
            'projects/app-id/topics/swarming',
        'pubsub_userdata':
            json.dumps({
                'runner_id': 'runner_id'
            }),
    }
    test_swarming.OnSwarmingTaskTriggered(
        master_name, builder_name, build_number, step_name, tests, 'task_id',
        iterations, SwarmingTaskRequest.FromSerializable(new_request))
    task = WfSwarmingTask.Get(master_name, builder_name, build_number,
                              step_name)
    self.assertEqual(task.task_id, task_id)

  @mock.patch.object(
      test_results, 'GetTestsRunStatuses', return_value='tests_statuses')
  @mock.patch.object(test_results, 'IsTestResultsValid', return_value=True)
  @mock.patch.object(
      swarmed_test_util,
      'GetSwarmingTaskDataAndResult',
      return_value=({
          'state': constants.STATE_COMPLETED
      }, 'content', None))
  def testOnSwarmingTaskTimeoutGotResult(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 15
    step_name = 's'
    swarming_task = WfSwarmingTask.Create(master_name, builder_name,
                                          build_number, step_name)
    swarming_task.put()
    parameters = RunSwarmingTaskParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        step_name=step_name,
        tests=['tests'])

    test_swarming.OnSwarmingTaskTimeout(parameters, 'task_id')

    swarming_task = WfSwarmingTask.Get(master_name, builder_name, build_number,
                                       step_name)
    self.assertEqual(analysis_status.COMPLETED, swarming_task.status)
    self.assertEqual('tests_statuses', swarming_task.tests_statuses)
    self.assertEqual({
        'code': swarming_task_error.RUNNER_TIMEOUT,
        'message': 'Runner to run swarming task timed out'
    }, swarming_task.error)

  @mock.patch.object(
      swarmed_test_util,
      'GetSwarmingTaskDataAndResult',
      return_value=(None, None, 'error'))
  def testOnSwarmingTaskTimeout(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 16
    step_name = 's'
    swarming_task = WfSwarmingTask.Create(master_name, builder_name,
                                          build_number, step_name)
    swarming_task.put()
    parameters = RunSwarmingTaskParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        step_name=step_name,
        tests=['tests'])
    test_swarming.OnSwarmingTaskTimeout(parameters, 'task_id')

    swarming_task = WfSwarmingTask.Get(master_name, builder_name, build_number,
                                       step_name)
    self.assertEqual(analysis_status.ERROR, swarming_task.status)
    self.assertEqual({
        'code': swarming_task_error.RUNNER_TIMEOUT,
        'message': 'Runner to run swarming task timed out'
    }, swarming_task.error)

  @mock.patch.object(
      test_results, 'GetTestsRunStatuses', return_value='tests_statuses')
  def testOnSwarmingTaskCompleted(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 13
    step_name = 's'
    WfSwarmingTask.Create(master_name, builder_name, build_number,
                          step_name).put()

    data = {
        'state': constants.STATE_COMPLETED,
        'created_ts': '2015-07-30T18:11:16.743220',
        'started_ts': '2015-07-30T18:12:16.743220',
        'completed_ts': '2015-07-30T18:15:16.743220'
    }

    test_swarming.OnSwarmingTaskCompleted(
        master_name, builder_name, build_number, step_name, data, 'output_json')

    swarming_task = WfSwarmingTask.Get(master_name, builder_name, build_number,
                                       step_name)
    self.assertEqual('tests_statuses', swarming_task.tests_statuses)
    self.assertEqual(analysis_status.COMPLETED, swarming_task.status)
    self.assertEqual(
        datetime.datetime(2015, 7, 30, 18, 11, 16, 743220),
        swarming_task.created_time)
    self.assertEqual(
        datetime.datetime(2015, 7, 30, 18, 12, 16, 743220),
        swarming_task.started_time)
    self.assertEqual(
        datetime.datetime(2015, 7, 30, 18, 15, 16, 743220),
        swarming_task.completed_time)

  @mock.patch.object(test_results, 'IsTestResultsValid', return_value=True)
  @mock.patch.object(
      swarmed_test_util,
      'GetSwarmingTaskDataAndResult',
      return_value=({
          'state': constants.STATE_COMPLETED
      }, 'content', None))
  @mock.patch.object(
      test_swarming, 'OnSwarmingTaskCompleted', return_value=True)
  def testOnSwarmingTaskStateChangedCompleted(self, mock_complete, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 8
    step_name = 's'
    task = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                 step_name)
    task.put()
    parameters = RunSwarmingTaskParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        step_name=step_name,
        tests=['test'])

    result = test_swarming.OnSwarmingTaskStateChanged(parameters, 'task_id')
    self.assertTrue(result)
    mock_complete.assert_called_once_with(
        master_name, builder_name, build_number, step_name,
        {'state': constants.STATE_COMPLETED}, 'content')

  @mock.patch.object(
      swarmed_test_util,
      'GetSwarmingTaskDataAndResult',
      return_value=({
          'state': constants.STATE_RUNNING
      }, None, None))
  @mock.patch.object(test_swarming, '_UpdateSwarmingTaskEntity')
  def testOnSwarmingTaskStateChangedRunning(self, mock_update, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 9
    step_name = 's'
    task = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                 step_name)
    task.put()
    parameters = RunSwarmingTaskParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        step_name=step_name,
        tests=['test'])

    result = test_swarming.OnSwarmingTaskStateChanged(parameters, 'task_id')
    self.assertIsNone(result)
    mock_update.assert_called_once_with(
        master_name,
        builder_name,
        build_number,
        step_name,
        status=analysis_status.RUNNING)

  @mock.patch.object(
      swarmed_test_util,
      'GetSwarmingTaskDataAndResult',
      return_value=({
          'state': constants.STATE_COMPLETED
      }, None,
                    SwarmingTaskError.FromSerializable({
                        'code': 1,
                        'message': 'message'
                    })))
  def testOnSwarmingTaskStateChangedError(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 10
    step_name = 's'
    WfSwarmingTask.Create(master_name, builder_name, build_number,
                          step_name).put()
    parameters = RunSwarmingTaskParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        step_name=step_name,
        tests=['test'])

    self.assertFalse(
        test_swarming.OnSwarmingTaskStateChanged(parameters, 'task_id'))

  @mock.patch.object(
      swarmed_test_util,
      'GetSwarmingTaskDataAndResult',
      return_value=(None, None, 'error'))
  @mock.patch.object(test_swarming, 'OnSwarmingTaskError')
  def testOnSwarmingTaskStateChangedNoTaskData(self, mock_error, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 11
    step_name = 's'
    task = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                 step_name)
    task.put()
    parameters = RunSwarmingTaskParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        step_name=step_name,
        tests=['test'])

    result = test_swarming.OnSwarmingTaskStateChanged(parameters, 'task_id')
    self.assertIsNone(result)
    mock_error.assert_called_once_with(master_name, builder_name, build_number,
                                       step_name, 'error', False)

  def testOnSwarmingTaskErrorShouldCompletePipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 11
    step_name = 's'
    WfSwarmingTask.Create(master_name, builder_name, build_number,
                          step_name).put()
    error = {'code': 1, 'message': 'error'}
    self.assertFalse(
        test_swarming.OnSwarmingTaskError(
            master_name, builder_name, build_number, step_name,
            SwarmingTaskError.FromSerializable(error)))

    swarming_task = WfSwarmingTask.Get(master_name, builder_name, build_number,
                                       step_name)
    self.assertEqual(error, swarming_task.error)
    self.assertEqual(analysis_status.ERROR, swarming_task.status)

  def testOnSwarmingTaskErrorShouldNotCompletePipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 12
    step_name = 's'
    WfSwarmingTask.Create(master_name, builder_name, build_number,
                          step_name).put()
    error = {'code': 1, 'message': 'error'}
    test_swarming.OnSwarmingTaskError(
        master_name, builder_name, build_number, step_name,
        SwarmingTaskError.FromSerializable(error), False)

    swarming_task = WfSwarmingTask.Get(master_name, builder_name, build_number,
                                       step_name)
    self.assertEqual(error, swarming_task.error)
    self.assertEqual(analysis_status.PENDING, swarming_task.status)

  @mock.patch.object(
      test_failure_analysis, 'GetFirstTimeFailedSteps', return_value=['step'])
  def testGetStepsToCollectSwarmingTaskResults(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 13
    params = CollectSwarmingTaskResultsInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True)

    self.assertEqual(['step'],
                     test_swarming.GetStepsToCollectSwarmingTaskResults(params))
    mock_fn.assert_called_once_with(master_name, builder_name, build_number)

  @mock.patch.object(test_failure_analysis, 'GetFirstTimeFailedSteps')
  def testGetStepsToCollectSwarmingTaskResultsBuildNotComplete(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 14
    params = CollectSwarmingTaskResultsInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=False)

    self.assertEqual([],
                     test_swarming.GetStepsToCollectSwarmingTaskResults(params))
    self.assertFalse(mock_fn.called)

  def testCollectSwarmingTaskResultsTaskRunning(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 15
    params = CollectSwarmingTaskResultsInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True)
    steps = ['step1', 'step2']

    task1 = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                  'step2')
    task1.status = analysis_status.COMPLETED
    task1.put()
    WfSwarmingTask.Create(master_name, builder_name, build_number,
                          'step1').put()
    self.assertIsNone(
        test_swarming.GetConsistentFailuresWhenAllTasksComplete(params, steps))

  def testCollectSwarmingTaskResultsError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 15
    params = CollectSwarmingTaskResultsInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True)
    steps = ['step1', 'step2']

    task1 = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                  'step1')
    task1.status = analysis_status.ERROR
    task1.put()
    task2 = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                  'step2')
    task2.status = analysis_status.COMPLETED
    task2.tests_statuses = {
        'TestSuite1.test1': {
            'total_run': 2,
            'SUCCESS': 2
        },
        'TestSuite1.test2': {
            'total_run': 4,
            'SUCCESS': 2,
            'FAILURE': 2
        },
        'TestSuite1.test3': {
            'total_run': 6,
            'FAILURE': 6
        },
        'TestSuite1.test4': {
            'total_run': 6,
            'SKIPPED': 6
        },
        'TestSuite1.test5': {
            'total_run': 6,
            'UNKNOWN': 6
        }
    }
    task2.put()

    expected_result_json = {
        'consistent_failures': {
            'step2': ['TestSuite1.test3', 'TestSuite1.test4']
        }
    }
    self.assertEqual(
        CollectSwarmingTaskResultsOutputs.FromSerializable(
            expected_result_json),
        test_swarming.GetConsistentFailuresWhenAllTasksComplete(params, steps))

  def testCollectSwarmingTaskResultsNoResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 16
    params = CollectSwarmingTaskResultsInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True)
    steps = ['step1']

    task1 = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                  'step1')
    task1.status = analysis_status.COMPLETED
    task1.put()

    self.assertEqual(
        CollectSwarmingTaskResultsOutputs.FromSerializable({}),
        test_swarming.GetConsistentFailuresWhenAllTasksComplete(params, steps))

  def testCollectSwarmingTaskResultsAllFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 17
    params = CollectSwarmingTaskResultsInputs(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        build_completed=True)
    steps = ['step2']

    task2 = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                  'step2')
    task2.status = analysis_status.COMPLETED
    task2.tests_statuses = {
        'TestSuite1.test1': {
            'total_run': 2,
            'SUCCESS': 2
        },
        'TestSuite1.test2': {
            'total_run': 4,
            'SUCCESS': 2,
            'FAILURE': 2
        },
    }
    task2.put()

    self.assertEqual(
        CollectSwarmingTaskResultsOutputs.FromSerializable({}),
        test_swarming.GetConsistentFailuresWhenAllTasksComplete(params, steps))

  @mock.patch.object(
      test_swarming, 'NeedANewSwarmingTask', side_effect=[True, False])
  @mock.patch.object(
      test_failure_analysis,
      'GetsFirstFailureAtTestLevel',
      return_value={
          'step': ['test'],
          'step1': ['test1']
      })
  def testGetFirstTimeTestFailuresToRunSwarmingTasks(self, mock_fn, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 13
    step_name = 'step'

    failure_info_json = {
        'failure_type': failure_type.TEST,
        'failed_steps': {
            step_name: {}
        }
    }
    failure_info = TestFailureInfo.FromSerializable(failure_info_json)

    heuristic_result = TestHeuristicAnalysisOutput(
        failure_info=failure_info,
        heuristic_result=TestHeuristicResult.FromSerializable({}))

    params = RunSwarmingTasksInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=heuristic_result,
        force=False)
    self.assertEqual({
        'step': ['test']
    }, test_swarming.GetFirstTimeTestFailuresToRunSwarmingTasks(params))
    mock_fn.assert_called_once_with(master_name, builder_name, build_number,
                                    failure_info, False)

  @mock.patch.object(test_failure_analysis, 'GetsFirstFailureAtTestLevel')
  def testGetFirstTimeTestFailuresToRunSwarmingTasksBailOut(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 14

    params = RunSwarmingTasksInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=TestHeuristicAnalysisOutput.FromSerializable({}),
        force=False)
    self.assertEqual(
        {}, test_swarming.GetFirstTimeTestFailuresToRunSwarmingTasks(params))
    self.assertFalse(mock_fn.called)
