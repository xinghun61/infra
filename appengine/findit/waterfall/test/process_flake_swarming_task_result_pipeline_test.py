# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import build_util
from waterfall import process_flake_swarming_task_result_pipeline
from waterfall import swarming_util
from waterfall.build_info import BuildInfo
from waterfall import process_flake_swarming_task_result_pipeline
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

  @mock.patch.object(
      process_flake_swarming_task_result_pipeline,
      '_GetCommitsBetweenRevisions', return_value=['r4', 'r3', 'r2', 'r1'])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testCheckTestsRunStatuses(self, mocked_fn, _):
    build_info = BuildInfo(
        self.master_name, self.build_number, self.build_number)
    build_info.commit_position = 12345
    build_info.chromium_revision = 'a1b2c3d4'
    mocked_fn.return_value = build_info
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

  @mock.patch.object(
      process_flake_swarming_task_result_pipeline,
      '_GetCommitsBetweenRevisions', return_value=['r4', 'r3', 'r2', 'r1'])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testCheckTestsRunStatusesZeroBuildNumber(self, mocked_fn, _):
    build_info = BuildInfo(self.master_name, self.build_number, 0)
    build_info.commit_position = 12345
    build_info.chromium_revision = 'a1b2c3d4'
    mocked_fn.return_value = build_info

    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name, 0, self.step_name, self.test_name)
    analysis.Save()

    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name, 0, self.step_name, self.test_name)
    task.put()

    ProcessFlakeSwarmingTaskResultPipeline()._CheckTestsRunStatuses(
        {}, self.master_name, self.builder_name, 0, self.step_name, 0,
        self.test_name, 1)
    self.assertIsNone(analysis.data_points[0].previous_build_commit_position)

  @mock.patch.object(
      process_flake_swarming_task_result_pipeline,
      '_GetCommitsBetweenRevisions', return_value=['r4', 'r3', 'r2', 'r1'])
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testCheckTestsRunStatusesWhenTestDoesNotExist(self, mocked_fn, _):
    build_info = BuildInfo(
        self.master_name, self.builder_name, self.build_number)
    build_info.commit_position = 12345
    build_info.chromium_revision = 'a1b2c3d4'
    mocked_fn.return_value = build_info

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

  @mock.patch.object(swarming_util, 'GetSwarmingTaskFailureLog',
                     return_value=(base_test._SAMPLE_FAILURE_LOG, None))
  @mock.patch.object(build_util, 'GetBuildInfo',
                     return_value=BuildInfo('m', 'b', 123))
  def testProcessFlakeSwarmingTaskResultPipeline(self, *_):
    # End to end test.
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
    pipeline.start_test()
    pipeline.run(
        self.master_name, self.builder_name,
        self.build_number, self.step_name,
        'task_id1', self.build_number, self.test_name,
        analysis.version_number)
    pipeline.callback(callback_params=pipeline.last_params)
    # Reload from ID to get all internal properties in sync.
    pipeline = ProcessFlakeSwarmingTaskResultPipeline.from_id(
        pipeline.pipeline_id)
    step_name, task_info = pipeline.outputs.default.value
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
    self.assertEqual(analysis.last_attempted_swarming_task_id, 'task_id1')

  @mock.patch.object(CachedGitilesRepository, 'GetCommitsBetweenRevisions',
                     return_value=['r4', 'r3', 'r2', 'r1'])
  def testGetCommitsBetweenRevisions(self, _):
    self.assertEqual(
        process_flake_swarming_task_result_pipeline._GetCommitsBetweenRevisions(
            'r0', 'r4'),
        ['r1', 'r2', 'r3', 'r4'])
