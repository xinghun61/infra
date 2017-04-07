# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock

from libs import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.wf_swarming_task import WfSwarmingTask
from waterfall import build_util
from waterfall import process_flake_swarming_task_result_pipeline
from waterfall import swarming_util
from waterfall.build_info import BuildInfo
from waterfall.process_base_swarming_task_result_pipeline import (
    ProcessBaseSwarmingTaskResultPipeline)
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.process_swarming_task_result_pipeline import (
    ProcessSwarmingTaskResultPipeline)
from waterfall.test import wf_testcase
from waterfall.trigger_base_swarming_task_pipeline import NO_TASK
from waterfall.trigger_base_swarming_task_pipeline import NO_TASK_EXCEPTION


_ISOLATED_SERVER = 'https://isolateserver.appspot.com'
_ISOLATED_STORAGE_URL = 'isolateserver.storage.googleapis.com'
_SAMPLE_FAILURE_LOG = {
    'per_iteration_data': [
        {
            'TestSuite1.test1': [
                {
                    'status': 'SUCCESS',
                    'other_info': 'N/A'
                }
            ],
            'TestSuite1.test2': [
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                },
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                },
                {
                    'status': 'SUCCESS',
                    'other_info': 'N/A'
                }
            ],
            'TestSuite1.test3': [
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                },
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                },
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                }
            ]
        },
        {
            'TestSuite1.test1': [
                {
                    'status': 'SUCCESS',
                    'other_info': 'N/A'
                }
            ],
            'TestSuite1.test2': [
                {
                    'status': 'SUCCESS',
                    'other_info': 'N/A'
                }
            ],
            'TestSuite1.test3': [
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                },
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                },
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                }
            ]
        }
    ]
}


_SWARMING_TASK_RESULTS = {
    'task_id1': {
        'state': 'COMPLETED',
        'exit_code': '1',
        'tags': [
            'priority:25',
            'ref_name:abc_tests'
        ],
        'outputs_ref': {
            'isolatedserver': _ISOLATED_SERVER,
            'namespace': 'default-gzip',
            'isolated': 'shard1_isolated'
        },
        'created_ts': '2016-02-10T18:32:06.538220',
        'started_ts': '2016-02-10T18:32:09.090550',
        'completed_ts': '2016-02-10T18:33:09'
    },
    'task_id2': {
        'state': 'TIMED_OUT',
        'outputs_ref': None
    },
    'task_id3': {
        'state': 'COMPLETED',
        'exit_code': '2',  # Swarming task failed.
    },
    'task_id4': {
        'state': 'COMPLETED',
        'exit_code': '1',
    },
}


_EXPECTED_TESTS_STATUS = {
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
}


_EXPECTED_CLASSIFIED_TESTS = {
    'flaky_tests': ['TestSuite1.test2', 'TestSuite1.test1'],
    'reliable_tests': ['TestSuite1.test3']
}


class ProcessBaseSwarmingTaskResultPipelineTest(wf_testcase.WaterfallTestCase):

  def _MockedGetSwarmingTaskResultById(self, task_id, _):
    return _SWARMING_TASK_RESULTS[task_id], None

  def setUp(self):
    super(ProcessBaseSwarmingTaskResultPipelineTest, self).setUp()
    self.pipeline = ProcessBaseSwarmingTaskResultPipeline()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121
    self.step_name = 'abc_tests on platform'
    self.test_name = 'test'
    self.mock(swarming_util, 'GetSwarmingTaskResultById',
              self._MockedGetSwarmingTaskResultById)

  def testConvertDateTime(self):
    fmt = '%Y-%m-%dT%H:%M:%S.%f'
    time_string = '2016-02-10T18:32:06.538220'
    test_time = self.pipeline._ConvertDateTime(time_string)
    time = datetime.datetime.strptime(time_string, fmt)
    self.assertEqual(test_time, time)

  def testConvertDateTimeNone(self):
    time_string = ''
    test_time = self.pipeline._ConvertDateTime(time_string)
    self.assertIsNone(test_time)

  def testConvertDateTimefailure(self):
    with self.assertRaises(ValueError):
      self.pipeline._ConvertDateTime('abc')

  def testCheckTestsRunStatusesNoOutPutJson(self):
    self.assertEqual(
        {},
        ProcessBaseSwarmingTaskResultPipeline._CheckTestsRunStatuses(
            self.pipeline, None, ()))

  def testCheckTestsRunStatuses(self):
    tests_statuses = (
        ProcessSwarmingTaskResultPipeline()._CheckTestsRunStatuses(
            _SAMPLE_FAILURE_LOG))
    self.assertEqual(_EXPECTED_TESTS_STATUS, tests_statuses)

  @mock.patch.object(
      process_flake_swarming_task_result_pipeline,
      '_GetCommitsBetweenRevisions', return_value=['r4', 'r3', 'r2', 'r1'])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testMonitorSwarmingTaskTimeOut(self, mocked_fn, _):
    build_info = BuildInfo(
        self.master_name, self.builder_name, self.build_number)
    build_info.commit_position = 12345
    build_info.chromium_revision = 'a1b2c3d4'
    mocked_fn.return_value = build_info

    # Override swarming config settings to force a timeout.
    override_swarming_settings = {
        'task_timeout_hours': -1
    }
    self.UpdateUnitTestConfigSettings(
        'swarming_settings', override_swarming_settings)

    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name, self.build_number, self.step_name,
        self.test_name)
    task.task_id = 'task_id1'
    task.put()

    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name, self.build_number, self.step_name,
        self.test_name)
    analysis.Save()

    pipeline = ProcessFlakeSwarmingTaskResultPipeline(
        self.master_name, self.builder_name, self.build_number, self.step_name,
        self.build_number, self.test_name, 1, task_id='task_id1')
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, self.step_name,
        'task_id1', self.build_number, self.test_name, 1)
    pipeline.callback(callback_params=pipeline.last_params)
    # Reload from ID to get all internal properties in sync.
    pipeline = ProcessFlakeSwarmingTaskResultPipeline.from_id(
        pipeline.pipeline_id)
    pipeline.finalized()
    step_name, task_info = pipeline.outputs.default.value
    self.assertEqual('abc_tests', task_info)
    self.assertEqual(self.step_name, step_name)

    task = FlakeSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number, self.step_name,
        self.test_name)
    self.assertEqual(analysis_status.ERROR, task.status)
    self.assertEqual({}, task.tests_statuses)

  def testMonitorSwarmingTaskNotRunning(self):
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id2'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    # Reload from ID to get all internal properties in sync.
    pipeline = ProcessSwarmingTaskResultPipeline.from_id(pipeline.pipeline_id)
    pipeline.finalized()
    step_name, task_info = pipeline.outputs.default.value

    self.assertEqual(self.step_name, step_name)
    self.assertIsNone(task_info[0])
    self.assertEqual([], task_info[1])

    task = WfSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.ERROR, task.status)
    self.assertEqual({}, task.tests_statuses)
    self.assertEqual({}, task.classified_tests)

  @mock.patch.object(swarming_util, 'GetSwarmingTaskResultById',
                     return_value=({}, {'code': 1, 'message': 'error'}))
  def testMonitorSwarmingTaskGetSwarmingTaskResultIdError(self, _):
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id2'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.ERROR, task.status)
    self.assertEqual(task.error, {'code': 1, 'message': 'error'})

  @mock.patch.object(swarming_util, 'GetSwarmingTaskResultById',
                     return_value=(_SWARMING_TASK_RESULTS['task_id1'],
                                   {'code': 1, 'message': 'error'}))
  @mock.patch.object(swarming_util, 'GetSwarmingTaskFailureLog',
                     return_value=(_SAMPLE_FAILURE_LOG, None))
  def testMonitorSwarmingTaskGetSwarmingTaskResultIdErrorRecovered(self, *_):
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id1'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.COMPLETED, task.status)
    self.assertEqual(task.error, {'code': 1, 'message': 'error'})

  @mock.patch.object(swarming_util, 'GetSwarmingTaskFailureLog',
                     return_value=(_SAMPLE_FAILURE_LOG,
                                   {'code': 1, 'message': 'error'}))
  def testMonitorSwarmingTaskGetSwarmingTaskFailureLogErrorRecovered(self, _):
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id1'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.COMPLETED, task.status)
    self.assertEqual(task.error, {'code': 1, 'message': 'error'})

  @mock.patch.object(swarming_util, 'GetSwarmingTaskFailureLog',
                     return_value=(None, {'code': 1, 'message': 'error'}))
  def testMonitorSwarmingTaskGetSwarmingTaskFailureLogError(self, _):
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id1'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.ERROR, task.status)
    self.assertEqual(task.error, {'code': 1, 'message': 'error'})

  def testMonitorSwarmingTaskWhereTaskFailed(self):
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id3'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.ERROR, task.status)
    self.assertEqual(
        task.error,
        {
            'code': swarming_util.TASK_FAILED,
            'message': swarming_util.EXIT_CODE_DESCRIPTIONS[
                swarming_util.TASK_FAILED]
        })

  def testMonitorSwarmingTaskWhereNoTaskOutputs(self):
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id4'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.ERROR, task.status)
    self.assertEqual(
        task.error,
        {
            'code': swarming_util.NO_TASK_OUTPUTS,
            'message': 'outputs_ref is None'
        })

  @mock.patch.object(swarming_util, 'GetSwarmingTaskFailureLog',
                     return_value=(_SAMPLE_FAILURE_LOG, None))
  def testProcessSwarmingTaskResultPipeline(self, _):
    # End to end test.
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id1'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    pipeline.callback(callback_params=pipeline.last_params)
    # Reload from ID to get all internal properties in sync.
    pipeline = ProcessSwarmingTaskResultPipeline.from_id(pipeline.pipeline_id)
    pipeline.finalized()
    step_name, task_info = pipeline.outputs.default.value

    self.assertEqual(self.step_name, step_name)
    self.assertEqual('abc_tests', task_info[0])
    self.assertEqual(
        _EXPECTED_CLASSIFIED_TESTS['reliable_tests'], task_info[1])

    task = WfSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.COMPLETED, task.status)
    self.assertEqual(_EXPECTED_TESTS_STATUS, task.tests_statuses)
    self.assertEqual(
        _EXPECTED_CLASSIFIED_TESTS, task.classified_tests)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 6, 538220),
                     task.created_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 9, 90550),
                     task.started_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 33, 9),
                     task.completed_time)

  @mock.patch.object(swarming_util, 'GetSwarmingTaskFailureLog',
                     return_value=(_SAMPLE_FAILURE_LOG, None))
  def testProcessSwarmingTaskResultPipelineSerializedCallback(self, _):
    # End to end test.
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id1'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    pipeline.callback(callback_params=json.dumps(pipeline.last_params))
    # Reload from ID to get all internal properties in sync.
    pipeline = ProcessSwarmingTaskResultPipeline.from_id(pipeline.pipeline_id)
    pipeline.finalized()
    step_name, task_info = pipeline.outputs.default.value

    self.assertEqual(self.step_name, step_name)
    self.assertEqual('abc_tests', task_info[0])
    self.assertEqual(
        _EXPECTED_CLASSIFIED_TESTS['reliable_tests'], task_info[1])

    task = WfSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.COMPLETED, task.status)
    self.assertEqual(_EXPECTED_TESTS_STATUS, task.tests_statuses)
    self.assertEqual(
        _EXPECTED_CLASSIFIED_TESTS, task.classified_tests)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 6, 538220),
                     task.created_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 9, 90550),
                     task.started_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 33, 9),
                     task.completed_time)

  @mock.patch.object(
      process_flake_swarming_task_result_pipeline,
      '_GetCommitsBetweenRevisions', return_value=['r4', 'r3', 'r2', 'r1'])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testMonitorSwarmingTaskStepNotExist(self, mocked_fn, _):
    task_id = NO_TASK

    build_info = BuildInfo(
        self.master_name, self.build_number, self.build_number)
    build_info.commit_position = 12345
    build_info.chromium_revision = 'a1b2c3d4'
    mocked_fn.return_value = build_info

    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name, self.build_number, self.step_name,
        self.test_name)
    task.put()

    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    analysis.Save()

    pipeline = ProcessFlakeSwarmingTaskResultPipeline(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, task_id, self.build_number,
        self.test_name, 1)
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, task_id, self.build_number,
        self.test_name, 1)
    # Reload from ID to get all internal properties in sync.
    pipeline = ProcessFlakeSwarmingTaskResultPipeline.from_id(
        pipeline.pipeline_id)
    pipeline.finalized()
    _, step_name_no_platform = pipeline.outputs.default.value

    self.assertIsNone(task.task_id)
    self.assertEqual(analysis_status.SKIPPED, task.status)
    self.assertEqual(-1, analysis.data_points[-1].pass_rate)
    self.assertIsNone(step_name_no_platform)

  @mock.patch.object(
      process_flake_swarming_task_result_pipeline,
      '_GetCommitsBetweenRevisions', return_value=['r4', 'r3', 'r2', 'r1'])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testMonitorSwarmingTaskBuildException(self, mocked_fn, _):
    task_id = NO_TASK_EXCEPTION

    build_info = BuildInfo(
        self.master_name, self.build_number, self.build_number)
    build_info.commit_position = 12345
    build_info.chromium_revision = 'a1b2c3d4'
    mocked_fn.return_value = build_info

    task = FlakeSwarmingTask.Create(
      self.master_name, self.builder_name, self.build_number, self.step_name,
      self.test_name)
    task.put()

    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    analysis.Save()

    pipeline = ProcessFlakeSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, task_id, self.build_number,
        self.test_name, 1)

    self.assertIsNone(task.task_id)
    self.assertEqual(analysis_status.SKIPPED, task.status)
    self.assertEqual(-1, analysis.data_points[-1].pass_rate)
    self.assertFalse(analysis.data_points[-1].has_valid_artifact)

  @mock.patch.object(swarming_util, 'GetSwarmingTaskFailureLog',
                     return_value=(_SAMPLE_FAILURE_LOG, None))
  def testProcessSwarmingTaskResultPipelineIdempotency(self, _):
    # End to end test.
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id1'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    # NB, run is called twice.
    pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    pipeline.callback(callback_params=pipeline.last_params)
    # Reload from ID to get all internal properties in sync.
    pipeline = ProcessSwarmingTaskResultPipeline.from_id(pipeline.pipeline_id)
    pipeline.finalized()
    step_name, task_info = pipeline.outputs.default.value

    self.assertEqual(self.step_name, step_name)
    self.assertEqual('abc_tests', task_info[0])
    self.assertEqual(
        _EXPECTED_CLASSIFIED_TESTS['reliable_tests'], task_info[1])

    task = WfSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.COMPLETED, task.status)
    self.assertEqual(_EXPECTED_TESTS_STATUS, task.tests_statuses)
    self.assertEqual(
        _EXPECTED_CLASSIFIED_TESTS, task.classified_tests)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 6, 538220),
                     task.created_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 9, 90550),
                     task.started_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 33, 9),
                     task.completed_time)

  @mock.patch.object(swarming_util, 'GetSwarmingTaskFailureLog',
                     return_value=(_SAMPLE_FAILURE_LOG, None))
  def testProcessSwarmingTaskResultPipelineBackwardCompatibleCallback(self, _):
    # End to end test.
    task = WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    task.task_id = 'task_id1'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name)
    pipeline.callback(**pipeline.last_params)
    # Reload from ID to get all internal properties in sync.
    pipeline = ProcessSwarmingTaskResultPipeline.from_id(pipeline.pipeline_id)
    pipeline.finalized()
    step_name, task_info = pipeline.outputs.default.value

    self.assertEqual(self.step_name, step_name)
    self.assertEqual('abc_tests', task_info[0])
    self.assertEqual(
        _EXPECTED_CLASSIFIED_TESTS['reliable_tests'], task_info[1])

    task = WfSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.COMPLETED, task.status)
    self.assertEqual(_EXPECTED_TESTS_STATUS, task.tests_statuses)
    self.assertEqual(
        _EXPECTED_CLASSIFIED_TESTS, task.classified_tests)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 6, 538220),
                     task.created_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 9, 90550),
                     task.started_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 33, 9),
                     task.completed_time)
