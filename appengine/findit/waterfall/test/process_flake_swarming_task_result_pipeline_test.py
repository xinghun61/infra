# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock

from model import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.wf_build import WfBuild
from waterfall import build_util
from waterfall import swarming_util
from waterfall import (
    process_flake_swarming_task_result_pipeline as flake_result_pipeline)
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

  @mock.patch.object(flake_result_pipeline,
                     '_GetCommitPositionAndGitHash',
                     return_value=(12345, 'git_hash'))
  def testCheckTestsRunStatuses(self, _):
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

  @mock.patch.object(flake_result_pipeline,
                     '_GetCommitPositionAndGitHash',
                     return_value=(12345, 'git_hash'))
  def testCheckTestsRunStatusesWhenTestDoesNotExist(self, _):
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
  @mock.patch.object(flake_result_pipeline,
                     '_GetCommitPositionAndGitHash',
                     return_value=(12345, 'git_hash'))
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

  @mock.patch.object(build_util, '_BuildDataNeedUpdating', return_value=False)
  def testGetCommitPositionAndGitHash(self, _):
    build = WfBuild.Create('m', 'b', 123)
    build.data = json.dumps({
        'properties': [
            ['got_revision', 'a_git_hash'],
            ['got_revision_cp', 'refs/heads/master@{#12345}']
        ],
    })
    build.put()
    self.assertEqual(
        (12345, 'a_git_hash'),
        flake_result_pipeline._GetCommitPositionAndGitHash('m', 'b', 123))
    self.assertEqual(
        (None, None),
        flake_result_pipeline._GetCommitPositionAndGitHash('m', 'b', -1))

  @mock.patch.object(build_util, '_BuildDataNeedUpdating', return_value=False)
  def testGetCommitPositionAndGitHashNoBuildDataAvailable(self, _):
    build = WfBuild.Create('m', 'b', 123)
    build.data = {}
    build.put()

    self.assertEqual(
        (None, None),
        flake_result_pipeline._GetCommitPositionAndGitHash('m', 'b', 123))

  @mock.patch.object(flake_result_pipeline,
                     '_GetCommitPositionAndGitHash',
                     return_value=(12345, 'git_hash'))
  def testNoGitHashForPreviousBuildNumberIfZero(self, _):
    analysis = MasterFlakeAnalysis.Create(
        self.master_name, self.builder_name, 0, self.step_name, self.test_name)
    analysis.Save()

    task = FlakeSwarmingTask.Create(
        self.master_name, self.builder_name, 0, self.step_name, self.test_name)
    task.put()

    call_params = ProcessFlakeSwarmingTaskResultPipeline._GetArgs(
        self.pipeline, self.master_name, self.builder_name, 0, self.step_name,
        0, self.test_name, self.version_number)

    ProcessFlakeSwarmingTaskResultPipeline._CheckTestsRunStatuses(
        self.pipeline, base_test._SAMPLE_FAILURE_LOG, *call_params)

    self.assertIsNone(analysis.data_points[0].previous_build_commit_position)
    self.assertIsNone(analysis.data_points[0].previous_build_git_hash)
