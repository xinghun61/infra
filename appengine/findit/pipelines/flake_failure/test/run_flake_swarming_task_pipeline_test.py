# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from dto.swarming_task_error import SwarmingTaskError
from gae_libs import pipelines
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskInput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskOutput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskPipeline)
from waterfall import build_util
from waterfall.build_info import BuildInfo
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)
from waterfall.test.wf_testcase import WaterfallTestCase


class RunFlakeSwarmingTaskResultPipeline(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testGetElapsedSecondsNoStartEndTimes(self):
    task_output = RunFlakeSwarmingTaskOutput(
        completed_time=None,
        error=None,
        has_valid_artifact=True,
        iterations=50,
        pass_count=25,
        started_time=None,
        task_id='task_id')
    self.assertIsNone(task_output.GetElapsedSeconds())

  def testGetElapsedSeconds(self):
    task_output = RunFlakeSwarmingTaskOutput(
        completed_time=datetime(2018, 2, 21, 0, 1, 0),
        error=None,
        has_valid_artifact=True,
        iterations=50,
        pass_count=25,
        started_time=datetime(2018, 2, 21, 0, 0, 0),
        task_id='task_id')
    self.assertEqual(60, task_output.GetElapsedSeconds())

  @mock.patch.object(build_util, 'GetBoundingBuilds')
  def testRunFlakeSwarmingTaskResultPipeline(self, mocked_builds):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 3600
    pass_count = 25
    task_id = 'task_id'

    lower_bound_build = BuildInfo(master_name, builder_name, build_number - 1)
    upper_bound_build = BuildInfo(master_name, builder_name, build_number)
    mocked_builds.return_value = (lower_bound_build, upper_bound_build)

    mock_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, commit_position, step_name, test_name)
    mock_swarming_task.error = None
    mock_swarming_task.has_valid_artifact = True
    mock_swarming_task.tries = iterations
    mock_swarming_task.successes = pass_count
    mock_swarming_task.task_id = task_id
    mock_swarming_task.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    run_flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    self.MockPipeline(
        TriggerFlakeSwarmingTaskPipeline,
        task_id,
        expected_args=[
            master_name, builder_name, build_number, step_name, [test_name],
            isolate_sha
        ],
        expected_kwargs={
            'iterations_to_rerun': iterations,
            'hard_timeout_seconds': timeout_seconds,
            'force': True
        })
    self.MockPipeline(
        ProcessFlakeSwarmingTaskResultPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, step_name, task_id,
            build_number, test_name, 1
        ])

    pipeline_job = RunFlakeSwarmingTaskPipeline(run_flake_swarming_task_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    run_flake_swarming_task_output = pipeline_job.outputs.default.value

    self.assertFalse(pipeline_job.was_aborted)
    self.assertIsNone(run_flake_swarming_task_output['error'])
    self.assertTrue(run_flake_swarming_task_output['has_valid_artifact'])
    self.assertEqual(iterations, run_flake_swarming_task_output['iterations'])
    self.assertEqual(pass_count, run_flake_swarming_task_output['pass_count'])
    self.assertEqual(task_id, run_flake_swarming_task_output['task_id'])

  @mock.patch.object(build_util, 'GetBoundingBuilds')
  def testRunFlakeSwarmingTaskResultPipelineWithError(self, mocked_builds):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    isolate_sha = 'sha1'
    iterations = 50
    timeout_seconds = 3600
    pass_count = 25
    task_id = 'task_id'

    lower_bound_build = BuildInfo(master_name, builder_name, build_number - 1)
    upper_bound_build = BuildInfo(master_name, builder_name, build_number)
    mocked_builds.return_value = (lower_bound_build, upper_bound_build)

    mock_swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, commit_position, step_name, test_name)
    mock_swarming_task.error = {'code': 1, 'message': 'message'}
    mock_swarming_task.has_valid_artifact = True
    mock_swarming_task.tries = iterations
    mock_swarming_task.successes = pass_count
    mock_swarming_task.task_id = task_id
    mock_swarming_task.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    run_flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    self.MockPipeline(
        TriggerFlakeSwarmingTaskPipeline,
        task_id,
        expected_args=[
            master_name, builder_name, build_number, step_name, [test_name],
            isolate_sha
        ],
        expected_kwargs={
            'iterations_to_rerun': iterations,
            'hard_timeout_seconds': timeout_seconds,
            'force': True
        })
    self.MockPipeline(
        ProcessFlakeSwarmingTaskResultPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, step_name, task_id,
            build_number, test_name, analysis.version_number
        ])

    pipeline_job = RunFlakeSwarmingTaskPipeline(run_flake_swarming_task_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    run_flake_swarming_task_output = pipeline_job.outputs.default.value

    self.assertFalse(pipeline_job.was_aborted)
    self.assertIsNotNone(run_flake_swarming_task_output['error'])
    self.assertTrue(run_flake_swarming_task_output['has_valid_artifact'])
    self.assertEqual(iterations, run_flake_swarming_task_output['iterations'])
    self.assertEqual(pass_count, run_flake_swarming_task_output['pass_count'])
    self.assertEqual(task_id, run_flake_swarming_task_output['task_id'])
