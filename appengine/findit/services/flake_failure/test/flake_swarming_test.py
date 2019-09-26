# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import mock

from dto import swarming_task_error
from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from dto.swarming_task_error import SwarmingTaskError
from infra_api_clients.swarming import swarming_util
from infra_api_clients.swarming import swarming_task_request
from infra_api_clients.swarming.swarming_task_request import (
    SwarmingTaskInputsRef)
from infra_api_clients.swarming.swarming_task_request import (
    SwarmingTaskProperties)
from infra_api_clients.swarming.swarming_task_request import SwarmingTaskRequest
from libs.list_of_basestring import ListOfBasestring
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskInput)
from services import constants
from services import swarmed_test_util
from services import swarming
from services.flake_failure import flake_swarming
from services.flake_failure import flake_test_results
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
            '--gtest_repeat=50',
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


class FlakeSwarmingTest(wf_testcase.WaterfallTestCase):

  def testParseFlakeSwarmingTaskOutputNoOutput(self):
    task_data = {
        'created_ts': '2018-04-02T18:32:06.538220',
        'started_ts': '2018-04-02T19:32:06.538220',
        'completed_ts': '2018-04-02T20:32:06.538220',
        'task_id': 'task_id'
    }
    error = SwarmingTaskError(code=1, message='m')

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200
    parameters = RunFlakeSwarmingTaskInput(
        builder_name='b',
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        master_name='m',
        reference_build_number=123,
        step_name='s',
        test_name='t',
        timeout_seconds=timeout_seconds)

    expected_result = FlakeSwarmingTaskOutput(
        task_id='task_id',
        started_time=datetime(2018, 4, 2, 19, 32, 6, 538220),
        completed_time=datetime(2018, 4, 2, 20, 32, 6, 538220),
        iterations=None,
        error=error,
        pass_count=None)

    self.assertEqual(
        expected_result,
        flake_swarming._ParseFlakeSwarmingTaskOutput(task_data, None, error,
                                                     parameters))

  @mock.patch.object(
      flake_test_results,
      'GetCountsFromSwarmingRerun',
      return_value=(None, None))
  def testParseFlakeSwarmingTaskOutputUndetectedError(self, _):
    task_data = {
        'created_ts': '2018-04-02T18:32:06.538220',
        'started_ts': '2018-04-02T19:32:06.538220',
        'completed_ts': '2018-04-02T20:32:06.538220',
        'task_id': 'task_id'
    }

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200
    parameters = RunFlakeSwarmingTaskInput(
        builder_name='b',
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        master_name='m',
        reference_build_number=123,
        step_name='s',
        test_name='t',
        timeout_seconds=timeout_seconds)

    expected_result = FlakeSwarmingTaskOutput(
        task_id='task_id',
        started_time=datetime(2018, 4, 2, 19, 32, 6, 538220),
        completed_time=datetime(2018, 4, 2, 20, 32, 6, 538220),
        iterations=None,
        error=SwarmingTaskError(code=1000, message='Unknown error'),
        pass_count=None)

    self.assertEqual(
        expected_result,
        flake_swarming._ParseFlakeSwarmingTaskOutput(task_data, {'bla': 'bla'},
                                                     None, parameters))

  @mock.patch.object(
      flake_test_results, 'GetCountsFromSwarmingRerun', return_value=(1, 0))
  def testParseFlakeSwarmingTaskOutputConsolidatedResult(self, _):
    task_data = {
        'created_ts': '2018-04-02T18:32:06.538220',
        'started_ts': '2018-04-02T19:32:06.538220',
        'task_id': 'task_id',
        'state': 'COMPLETED',
        'failure': False,
        'internal_failure': False
    }

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200
    parameters = RunFlakeSwarmingTaskInput(
        builder_name='b',
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        master_name='m',
        reference_build_number=123,
        step_name='s',
        test_name='t',
        timeout_seconds=timeout_seconds)

    expected_result = FlakeSwarmingTaskOutput(
        task_id='task_id',
        started_time=datetime(2018, 4, 2, 19, 32, 6, 538220),
        completed_time=None,
        iterations=50,
        error=None,
        pass_count=0)

    self.assertEqual(
        expected_result,
        flake_swarming._ParseFlakeSwarmingTaskOutput(task_data, {'bla': 'bla'},
                                                     None, parameters))

  @mock.patch.object(flake_test_results, 'GetCountsFromSwarmingRerun')
  def testParseFlakeSwarmingTaskOutput(self, mocked_pass_fail):
    iterations = 50
    pass_count = 25
    task_data = {
        'created_ts': '2018-04-02T18:32:06.538220',
        'started_ts': '2018-04-02T19:32:06.538220',
        'completed_ts': '2018-04-02T20:32:06.538220',
        'task_id': 'task_id'
    }

    mocked_pass_fail.return_value = (iterations, pass_count)

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    parameters = RunFlakeSwarmingTaskInput(
        builder_name='b',
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        master_name='m',
        reference_build_number=123,
        step_name='s',
        test_name='t',
        timeout_seconds=timeout_seconds)

    expected_result = FlakeSwarmingTaskOutput(
        task_id='task_id',
        started_time=datetime(2018, 4, 2, 19, 32, 6, 538220),
        completed_time=datetime(2018, 4, 2, 20, 32, 6, 538220),
        iterations=iterations,
        error=None,
        pass_count=pass_count)

    self.assertEqual(
        expected_result,
        flake_swarming._ParseFlakeSwarmingTaskOutput(task_data, 'content', None,
                                                     parameters))

  @mock.patch.object(swarmed_test_util, 'GetSwarmingTaskDataAndResult')
  def testOnSwarmingTaskTimeoutNoTaskId(self, mocked_result):
    error = SwarmingTaskError(
        code=350, message='Runner to run swarming task timed out')
    mocked_result.return_value = None, None, error

    expected_result = FlakeSwarmingTaskOutput(
        task_id=None,
        started_time=None,
        completed_time=None,
        iterations=None,
        error=error,
        pass_count=None)

    self.assertEqual(expected_result,
                     flake_swarming.OnSwarmingTaskTimeout(None, None))

  @mock.patch.object(swarmed_test_util, 'GetSwarmingTaskDataAndResult')
  def testOnSwarmingTaskTimeoutNoData(self, mocked_result):
    error = SwarmingTaskError(code=1000, message='Unknown error')
    mocked_result.return_value = None, None, error
    task_id = 'task_id'

    expected_result = FlakeSwarmingTaskOutput(
        task_id=task_id,
        started_time=None,
        completed_time=None,
        iterations=None,
        error=error,
        pass_count=None)

    self.assertEqual(expected_result,
                     flake_swarming.OnSwarmingTaskTimeout(None, task_id))

  @mock.patch.object(swarmed_test_util, 'GetSwarmingTaskDataAndResult')
  @mock.patch.object(flake_swarming, '_ParseFlakeSwarmingTaskOutput')
  def testOnSwarmingTaskTimeout(self, mocked_parse, mocked_result):
    error = SwarmingTaskError.GenerateError(swarming_task_error.RUNNER_TIMEOUT)
    task_id = 'task_id'

    task_data = {
        'state': 'COMPLETE',
    }
    mocked_result.return_value = task_data, 'content', None

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    parameters = RunFlakeSwarmingTaskInput(
        builder_name='b',
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        master_name='m',
        reference_build_number=123,
        step_name='s',
        test_name='t',
        timeout_seconds=timeout_seconds)

    flake_swarming.OnSwarmingTaskTimeout(parameters, task_id)
    mocked_parse.assert_called_once_with(task_data, 'content', error,
                                         parameters)

  def testOnSwarmingTaskError(self):
    task_id = 'task_id'
    error = SwarmingTaskError(code=1000, message='Unknown error')
    expected_result = FlakeSwarmingTaskOutput(
        task_id=task_id,
        started_time=None,
        completed_time=None,
        iterations=None,
        error=error,
        pass_count=None)

    self.assertEqual(expected_result,
                     flake_swarming.OnSwarmingTaskError(task_id, error))

  @mock.patch.object(swarmed_test_util, 'GetSwarmingTaskDataAndResult')
  @mock.patch.object(flake_swarming, 'OnSwarmingTaskError')
  def testOnSwarmingTaskStateChangedNoTaskData(self, mocked_error,
                                               mocked_result):

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    parameters = RunFlakeSwarmingTaskInput(
        builder_name='b',
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        master_name='m',
        reference_build_number=123,
        step_name='s',
        test_name='t',
        timeout_seconds=timeout_seconds)

    task_id = 'task_id'
    mocked_result.return_value = None, None, None

    flake_swarming.OnSwarmingTaskStateChanged(parameters, task_id)
    mocked_error.assert_called_once_with(task_id, None)

  @mock.patch.object(swarmed_test_util, 'GetSwarmingTaskDataAndResult')
  def testOnSwarmingTaskStateChangedRunning(self, mocked_result):
    task_id = 'task_id'
    task_data = {'state': constants.STATE_RUNNING}
    mocked_result.return_value = task_data, None, None

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    parameters = RunFlakeSwarmingTaskInput(
        builder_name='b',
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        master_name='m',
        reference_build_number=123,
        step_name='s',
        test_name='t',
        timeout_seconds=timeout_seconds)

    self.assertIsNone(
        flake_swarming.OnSwarmingTaskStateChanged(parameters, task_id))

  @mock.patch.object(swarmed_test_util, 'GetSwarmingTaskDataAndResult')
  @mock.patch.object(flake_swarming, '_ParseFlakeSwarmingTaskOutput')
  def testOnSwarmingTaskStateChangedCompleted(self, mocked_parse,
                                              mocked_result):
    task_id = 'task_id'
    task_data = {
        'state': constants.STATE_COMPLETED,
    }
    mocked_result.return_value = task_data, None, None

    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 1200

    parameters = RunFlakeSwarmingTaskInput(
        builder_name='b',
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        master_name='m',
        reference_build_number=123,
        step_name='s',
        test_name='t',
        timeout_seconds=timeout_seconds)

    flake_swarming.OnSwarmingTaskStateChanged(parameters, task_id)
    mocked_parse.assert_called_once_with(task_data, None, None, parameters)

  @mock.patch.object(swarming, 'CreateNewSwarmingTaskRequestTemplate')
  def testCreateNewSwarmingTaskRequest(self, mocked_template):
    mocked_template.return_value = SwarmingTaskRequest.FromSerializable(
        _SAMPLE_REQUEST_JSON)

    runner_id = 'pipeline_id'
    ref_task_id = 'ref_task_id'
    ref_request = SwarmingTaskRequest.GetSwarmingTaskRequestTemplate()
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    iterations = 50
    timeout_seconds = 3600
    isolate_sha = 'sha1'

    expected_request = SwarmingTaskRequest(
        created_ts=None,
        name='findit/ref_task_id/ref_task_id/2018-03-15 00:00:00 000000',
        tags=ListOfBasestring.FromSerializable([
            'ref_master:m',
            'ref_buildername:b',
            'ref_buildnumber:4',
            'ref_stepname:s',
            'ref_name:test',
            'purpose:identify-regression-range',
        ]),
        pubsub_topic='projects/app-id/topics/swarming',
        properties=SwarmingTaskProperties(
            dimensions=[{
                'value': 'v',
                'key': 'k'
            }],
            idempotent=False,
            inputs_ref=SwarmingTaskInputsRef(
                isolatedserver='isolatedserver',
                namespace=None,
                isolated='sha1'),
            extra_args=ListOfBasestring.FromSerializable([
                '--flag=value', '--gtest_filter=a.b:a.c', '--gtest_repeat=50',
                '--test-launcher-retry-limit=0',
                '--gtest_also_run_disabled_tests'
            ]),
            io_timeout_secs='1200',
            command='cmd',
            env=[{
                'value': '1',
                'key': 'a'
            }],
            execution_timeout_secs='3600',
            env_prefixes=[],
            grace_period_secs='30',
            caches=None,
            cipd_input=swarming_task_request.CIPDInput(
                packages=swarming_task_request.CIPDPackages(),
                client_package=swarming_task_request.CIPDClientPackage(
                    version=None,
                    package_name=None,
                ),
                server=None)),
        priority='25',
        parent_task_id='',
        user='',
        service_account=None,
        pubsub_userdata='{"runner_id": "runner_id"}',
        expiration_secs='3600',
        pubsub_auth_token='auth_token')

    self.assertEqual(
        expected_request,
        flake_swarming.CreateNewSwarmingTaskRequest(
            runner_id, ref_task_id, ref_request, master_name, builder_name,
            step_name, test_name, isolate_sha, iterations, timeout_seconds))

  @mock.patch.object(swarming, 'GetReferredSwarmingTaskRequestInfo')
  @mock.patch.object(swarming_util, 'TriggerSwarmingTask')
  @mock.patch.object(flake_swarming, 'CreateNewSwarmingTaskRequest')
  def testTriggerSwarmingTask(self, mocked_request, mocked_trigger,
                              mocked_reference_info):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 3600
    runner_id = 'pipeline_id'
    ref_task_id = 'ref_task_id'
    ref_request = SwarmingTaskRequest.FromSerializable(_SAMPLE_REQUEST_JSON)
    task_id = 'task_id'

    request = SwarmingTaskRequest(
        created_ts=None,
        name='findit/ref_task_id/ref_task_id/2018-03-15 00:00:00 000000',
        tags=ListOfBasestring.FromSerializable([
            'ref_master:m',
            'ref_buildername:b',
            'ref_buildnumber:4',
            'ref_stepname:s',
            'ref_name:test',
            'purpose:identify-regression-range',
        ]),
        pubsub_topic='projects/app-id/topics/swarming',
        properties=SwarmingTaskProperties(
            dimensions=[{
                'value': 'v',
                'key': 'k'
            }],
            idempotent=False,
            inputs_ref=SwarmingTaskInputsRef(
                isolatedserver='isolatedserver',
                namespace=None,
                isolated='sha1'),
            extra_args=ListOfBasestring.FromSerializable([
                '--flag=value', '--gtest_filter=a.b:a.c', '--gtest_repeat=50',
                '--test-launcher-retry-limit=0',
                '--gtest_also_run_disabled_tests'
            ]),
            io_timeout_secs='1200',
            command='cmd',
            env=[{
                'value': '1',
                'key': 'a'
            }],
            execution_timeout_secs='3600',
            env_prefixes=[],
            grace_period_secs='30',
            caches=None),
        priority='25',
        parent_task_id='',
        user='',
        service_account=None,
        pubsub_userdata='{"runner_id": "runner_id"}',
        expiration_secs='3600',
        pubsub_auth_token='auth_token')

    mocked_reference_info.return_value = (ref_task_id, ref_request)
    mocked_request.return_value = request
    mocked_trigger.return_value = (task_id, None)

    self.assertEqual(
        task_id,
        flake_swarming.TriggerSwarmingTask(
            master_name, builder_name, build_number, step_name, test_name,
            isolate_sha, iterations, timeout_seconds, runner_id))

    mocked_request.assert_called_once_with(
        runner_id, ref_task_id, ref_request, master_name, builder_name,
        step_name, test_name, isolate_sha, iterations, timeout_seconds)
