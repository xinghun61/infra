# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from model import analysis_status
from model.wf_swarming_task import WfSwarmingTask
from waterfall import process_swarming_task_result_pipeline
from waterfall import swarming_util
from waterfall.process_swarming_task_result_pipeline import (
    ProcessSwarmingTaskResultPipeline)
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
_EXPECTED_CLASSIFIED_TESTS = {
    'flaky_tests': ['TestSuite1.test2', 'TestSuite1.test1'],
    'reliable_tests': ['TestSuite1.test3']
}


class ProcessSwarmingTaskResultPipelineTest(wf_testcase.WaterfallTestCase):

  def _MockedGetSwarmingTaskResultById(self, task_id, _):
    swarming_task_results = {
        'task_id1': {
            'state': 'COMPLETED',
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
    super(ProcessSwarmingTaskResultPipelineTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121
    self.step_name = 'abc_tests on platform'
    self.mock(swarming_util, 'GetSwarmingTaskResultById',
              self._MockedGetSwarmingTaskResultById)

  def testCheckTestsRunStatusesNoOutPutJson(self):
    tests_statuses = (
        process_swarming_task_result_pipeline._CheckTestsRunStatuses(None))
    self.assertEqual({}, tests_statuses)

  def testCheckTestsRunStatuses(self):
    tests_statuses = (
        process_swarming_task_result_pipeline._CheckTestsRunStatuses(
            _SAMPLE_FAILURE_LOG))
    self.assertEqual(_EXPECTED_TESTS_STATUESE, tests_statuses)

  def _MockedGetSwarmingTaskFailureLog(self, *_):
    return _SAMPLE_FAILURE_LOG

  def testProcessSwarmingTaskResultPipeline(self):
    task_id = 'task_id1'

    self.mock(swarming_util, 'GetSwarmingTaskFailureLog',
              self._MockedGetSwarmingTaskFailureLog)

    WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name).put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    step_name, task_info = pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, task_id)

    self.assertEqual(self.step_name, step_name)
    self.assertEqual('abc_tests', task_info[0])
    self.assertEqual(_EXPECTED_CLASSIFIED_TESTS, task_info[1])

    task = WfSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.COMPLETED, task.status)
    self.assertEqual(_EXPECTED_TESTS_STATUESE, task.tests_statuses)
    self.assertEqual(_EXPECTED_CLASSIFIED_TESTS, task.classified_tests)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 6, 538220),
                     task.created_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 9, 90550),
                     task.started_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 33, 9),
                     task.completed_time)

  def testProcessSwarmingTaskResultPipelineTaskNotRunning(self):
    task_id = 'task_id2'

    WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name).put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    step_name, task_info = pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, task_id)

    self.assertEqual(self.step_name, step_name)
    self.assertIsNone(task_info[0])
    self.assertEqual({}, task_info[1])

    task = WfSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.ERROR, task.status)
    self.assertEqual({}, task.tests_statuses)
    self.assertEqual({}, task.classified_tests)

  def testProcessSwarmingTaskResultPipelineTaskTimeOut(self):
    task_id = 'task_id1'

    # Override swarming config settings to force a timeout.
    override_swarming_settings = {
        'task_timeout_hours': -1
    }
    self.UpdateUnitTestConfigSettings(
        'swarming_settings', override_swarming_settings)

    WfSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name).put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    step_name, task_info = pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, task_id)

    self.assertEqual(self.step_name, step_name)
    self.assertEqual('abc_tests', task_info[0])
    self.assertEqual({}, task_info[1])

    task = WfSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number, self.step_name)

    self.assertEqual(analysis_status.ERROR, task.status)
    self.assertEqual({}, task.tests_statuses)
    self.assertEqual({}, task.classified_tests)
