# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from waterfall import swarming_util
from waterfall.process_swarming_task_result_pipeline import (
    ProcessSwarmingTaskResultPipeline)
from waterfall.test import (process_base_swarming_task_result_pipeline_test as
                            base_test)
from waterfall.test import wf_testcase


class ProcessSwarmingTaskResultPipelineTest(wf_testcase.WaterfallTestCase):

  def _MockedGetSwarmingTaskResultById(self, task_id, _):
    return base_test._SWARMING_TASK_RESULTS[task_id], None

  def setUp(self):
    super(ProcessSwarmingTaskResultPipelineTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121
    self.step_name = 'abc_tests on platform'
    self.mock(swarming_util, 'GetSwarmingTaskResultById',
              self._MockedGetSwarmingTaskResultById)

  def _MockedGetSwarmingTaskFailureLog(self, *_):
    return base_test._SAMPLE_FAILURE_LOG, None

  def testProcessSwarmingTaskResultPipeline(self):
    # End to end test.
    self.mock(swarming_util, 'GetSwarmingTaskFailureLog',
              self._MockedGetSwarmingTaskFailureLog)

    task = WfSwarmingTask.Create(self.master_name, self.builder_name,
                                 self.build_number, self.step_name)
    task.task_id = 'task_id1'
    task.put()

    analysis = WfAnalysis.Create(self.master_name, self.builder_name,
                                 self.build_number)
    analysis.result = {
        'failures': [
            {
                'step_name': 'another_step1'
            },
            {
                'tests': [
                    {
                        'last_pass': self.build_number,
                        'first_failure': self.build_number,
                        'suspected_cls': [],
                        'test_name': 'TestSuite1.test1'
                    },
                    {
                        'last_pass': self.build_number,
                        'first_failure': self.build_number,
                        'suspected_cls': [],
                        'test_name': 'TestSuite1.test2'
                    },
                    {
                        'last_pass': self.build_number,
                        'first_failure': self.build_number,
                        'suspected_cls': [],
                        'test_name': 'TestSuite1.test3'
                    },
                ],
                'step_name':
                    self.step_name
            },
            {
                'step_name': 'another_step2'
            },
        ]
    }
    analysis.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(self.master_name, self.builder_name, self.build_number,
                 self.step_name)
    pipeline.callback(callback_params=pipeline.last_params)
    # Reload from ID to get all internal properties in sync.
    pipeline = ProcessSwarmingTaskResultPipeline.from_id(pipeline.pipeline_id)
    step_name, flaky_tests = pipeline.outputs.default.value

    self.assertEqual(self.step_name, step_name)
    self.assertEqual(base_test._EXPECTED_CLASSIFIED_TESTS['flaky_tests'],
                     flaky_tests)

    task = WfSwarmingTask.Get(self.master_name, self.builder_name,
                              self.build_number, self.step_name)
    self.assertEqual(analysis_status.COMPLETED, task.status)
    self.assertEqual(base_test._EXPECTED_TESTS_STATUS, task.tests_statuses)
    self.assertEqual(base_test._EXPECTED_CLASSIFIED_TESTS,
                     task.classified_tests)
    self.assertEqual(
        datetime.datetime(2016, 2, 10, 18, 32, 6, 538220), task.created_time)
    self.assertEqual(
        datetime.datetime(2016, 2, 10, 18, 32, 9, 90550), task.started_time)
    self.assertEqual(
        datetime.datetime(2016, 2, 10, 18, 33, 9), task.completed_time)
    self.assertEqual('abc_tests', task.canonical_step_name)

  def testProcessSwarmingTaskResultPipelineTaskNotRunning(self):

    task = WfSwarmingTask.Create(self.master_name, self.builder_name,
                                 self.build_number, self.step_name)
    task.task_id = 'task_id2'
    task.put()

    pipeline = ProcessSwarmingTaskResultPipeline()
    pipeline.start_test()
    pipeline.run(self.master_name, self.builder_name, self.build_number,
                 self.step_name)
    pipeline.callback(callback_params=pipeline.last_params)
    # Reload from ID to get all internal properties in sync.
    pipeline = ProcessSwarmingTaskResultPipeline.from_id(pipeline.pipeline_id)
    step_name, flaky_tests = pipeline.outputs.default.value

    self.assertEqual(self.step_name, step_name)
    self.assertEqual([], flaky_tests)

    task = WfSwarmingTask.Get(self.master_name, self.builder_name,
                              self.build_number, self.step_name)

    self.assertEqual(analysis_status.ERROR, task.status)
    self.assertEqual({}, task.tests_statuses)
    self.assertEqual({}, task.classified_tests)
