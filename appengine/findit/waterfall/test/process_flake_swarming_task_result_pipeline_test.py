# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from model import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import swarming_util
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.test import wf_testcase


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
_EXPECTED_TESTS_STATUESE = {
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
    }
}


class ProcessFlakeSwarmingTaskResultPipelineTest(wf_testcase.WaterfallTestCase):

  def _MockedGetSwarmingTaskResultById(self, task_id, _):
    swarming_task_results = {
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
        }
    }

    mocked_result = swarming_task_results[task_id]
    return mocked_result

  def setUp(self):
    super(ProcessFlakeSwarmingTaskResultPipelineTest, self).setUp()
    self.pipeline = ProcessFlakeSwarmingTaskResultPipeline()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121
    self.step_name = 'abc_tests on platform'
    self.test_name = 'TestSuite1.test1'
    self.mock(swarming_util, 'GetSwarmingTaskResultById',
              self._MockedGetSwarmingTaskResultById)

  def testCheckTestsRunStatusesNoOutPutJson(self):
    call_params = ProcessFlakeSwarmingTaskResultPipeline._GetArgs(
        self.pipeline, self.master_name, self.builder_name,
        self.build_number, self.step_name, self.build_number,
        self.test_name)
    tests_statuses = (
        ProcessFlakeSwarmingTaskResultPipeline._CheckTestsRunStatuses(
            self.pipeline, None, *call_params
        ))
    self.assertEqual({}, tests_statuses)

  def testCheckTestsRunStatuses(self):
    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    analysis.put()

    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    task.put()

    call_params = ProcessFlakeSwarmingTaskResultPipeline._GetArgs(
        self.pipeline, self.master_name, self.builder_name,
        self.build_number, self.step_name, self.build_number,
        self.test_name)

    tests_statuses = (
        ProcessFlakeSwarmingTaskResultPipeline._CheckTestsRunStatuses(
            self.pipeline,
            _SAMPLE_FAILURE_LOG, *call_params))
    self.assertEqual(_EXPECTED_TESTS_STATUESE, tests_statuses)

  def testCheckTestsRunStatusesWhenTestNotExist(self):
    test_name = 'TestSuite1.new_test'
    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, test_name)
    analysis.put()

    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, test_name)
    task.put()

    pipeline = ProcessFlakeSwarmingTaskResultPipeline()
    tests_statuses = pipeline._CheckTestsRunStatuses(
        _SAMPLE_FAILURE_LOG, self.master_name, self.builder_name,
        self.build_number, self.step_name, self.build_number, test_name)

    self.assertEqual(_EXPECTED_TESTS_STATUESE, tests_statuses)

    task = FlakeSwarmingTask.Get(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, test_name)
    self.assertEqual(0, task.tries)
    self.assertEqual(0, task.successes)

    analysis = MasterFlakeAnalysis.Get(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, test_name)
    self.assertTrue(analysis.success_rates[-1] < 0)

  def _MockedGetSwarmingTaskFailureLog(self, *_):
    return _SAMPLE_FAILURE_LOG

  def testProcessFlakeSwarmingTaskResultPipeline(self):

    self.mock(swarming_util, 'GetSwarmingTaskFailureLog',
              self._MockedGetSwarmingTaskFailureLog)

    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    task.task_id = 'task_id1'
    task.put()

    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    analysis.put()

    pipeline = ProcessFlakeSwarmingTaskResultPipeline()
    step_name, task_info = pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name,
        'task_id1', self.build_number, self.test_name)
    self.assertEqual('abc_tests', task_info)
    self.assertEqual(self.step_name, step_name)

    task = FlakeSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number,
        self.step_name, self.test_name)

    self.assertEqual(analysis_status.COMPLETED, task.status)
    self.assertEqual(_EXPECTED_TESTS_STATUESE, task.tests_statuses)

    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 6, 538220),
                     task.created_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 9, 90550),
                     task.started_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 33, 9),
                     task.completed_time)

  def testProcessFlakeSwarmingTaskResultPipelineTaskNotRunning(self):
    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    task.task_id = 'task_id2'
    task.put()

    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    analysis.put()

    pipeline = ProcessFlakeSwarmingTaskResultPipeline()
    step_name, task_info = pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name,
        'task_id2', self.build_number, self.test_name)
    self.assertEqual(None, task_info)
    self.assertEqual(self.step_name, step_name)

    task = FlakeSwarmingTask.Get(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)

    self.assertEqual(analysis_status.ERROR, task.status)

  def testProcessFlakeSwarmingTaskResultPipelineTaskTimeOut(self):
    # Override swarming config settings to force a timeout.
    override_swarming_settings = {
        'task_timeout_hours': -1
    }
    self.UpdateUnitTestConfigSettings(
        'swarming_settings', override_swarming_settings)

    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    task.task_id = 'task_id1'
    task.put()

    pipeline = ProcessFlakeSwarmingTaskResultPipeline()
    step_name, task_info = pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name,
        'task_id1', self.build_number, self.test_name)
    self.assertEqual('abc_tests', task_info)
    self.assertEqual(self.step_name, step_name)

    task = FlakeSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number,
        self.step_name, self.test_name)
    self.assertEqual(analysis_status.ERROR, task.status)
    self.assertEqual({}, task.tests_statuses)
