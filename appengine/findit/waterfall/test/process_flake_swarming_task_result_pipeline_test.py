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
from waterfall.test import (
    process_base_swarming_task_result_pipeline_test as base_test)
from waterfall.test import wf_testcase


class ProcessFlakeSwarmingTaskResultPipelineTest(wf_testcase.WaterfallTestCase):

  def _MockedGetSwarmingTaskResultById(self, task_id, _):
    return base_test._SWARMING_TASK_RESULTS[task_id], None

  def setUp(self):
    super(ProcessFlakeSwarmingTaskResultPipelineTest, self).setUp()
    self.pipeline = ProcessFlakeSwarmingTaskResultPipeline()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121
    self.step_name = 'abc_tests on platform'
    self.test_name = 'TestSuite1.test1'
    self.version_number = 1
    self.mock(swarming_util, 'GetSwarmingTaskResultById',
              self._MockedGetSwarmingTaskResultById)

  def testCheckTestsRunStatuses(self):
    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    analysis.Save()

    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, self.test_name)
    task.put()

    call_params = ProcessFlakeSwarmingTaskResultPipeline._GetArgs(
        self.pipeline, self.master_name, self.builder_name,
        self.build_number, self.step_name, self.build_number,
        self.test_name, self.version_number)

    tests_statuses = (
        ProcessFlakeSwarmingTaskResultPipeline._CheckTestsRunStatuses(
            self.pipeline,
            base_test._SAMPLE_FAILURE_LOG, *call_params))
    self.assertEqual(base_test._EXPECTED_TESTS_STATUS, tests_statuses)

  def testCheckTestsRunStatusesWhenTestDoesNotExist(self):
    test_name = 'TestSuite1.new_test'
    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, test_name)
    analysis.Save()

    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, test_name)
    task.put()

    pipeline = ProcessFlakeSwarmingTaskResultPipeline()
    tests_statuses = pipeline._CheckTestsRunStatuses(
        base_test._SAMPLE_FAILURE_LOG, self.master_name, self.builder_name,
        self.build_number, self.step_name, self.build_number, test_name,
        self.version_number)

    self.assertEqual(base_test._EXPECTED_TESTS_STATUS, tests_statuses)

    task = FlakeSwarmingTask.Get(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, test_name)
    self.assertEqual(0, task.tries)
    self.assertEqual(0, task.successes)

    analysis = MasterFlakeAnalysis.GetVersion(
        self.master_name, self.builder_name,
        self.build_number, self.step_name, test_name, self.version_number)
    self.assertTrue(analysis.data_points[-1].pass_rate < 0)

  def _MockedGetSwarmingTaskFailureLog(self, *_):
    return base_test._SAMPLE_FAILURE_LOG, None

  def testProcessFlakeSwarmingTaskResultPipeline(self):
    # End to end test.
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
    analysis.Save()

    pipeline = ProcessFlakeSwarmingTaskResultPipeline()
    step_name, task_info = pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name,
        'task_id1', self.build_number, self.test_name,
        analysis.version_number)
    self.assertEqual('abc_tests', task_info)
    self.assertEqual(self.step_name, step_name)

    task = FlakeSwarmingTask.Get(
        self.master_name, self.builder_name, self.build_number,
        self.step_name, self.test_name)

    self.assertEqual(analysis_status.COMPLETED, task.status)
    self.assertEqual(base_test._EXPECTED_TESTS_STATUS, task.tests_statuses)

    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 6, 538220),
                     task.created_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 32, 9, 90550),
                     task.started_time)
    self.assertEqual(datetime.datetime(2016, 2, 10, 18, 33, 9),
                     task.completed_time)
