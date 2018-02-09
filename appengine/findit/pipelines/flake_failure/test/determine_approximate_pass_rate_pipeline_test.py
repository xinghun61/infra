# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from dto.swarming_task_error import SwarmingTaskError
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRateInput)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRatePipeline)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRatePipelineWrapper)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    UpdateFlakeAnalysisDataPointsInput)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    UpdateFlakeAnalysisDataPointsPipeline)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskInput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskOutput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskPipeline)
from services.flake_failure import data_point_util
from services.flake_failure import pass_rate_util
from services.flake_failure import run_swarming_util
from waterfall.flake import flake_constants
from waterfall.test.wf_testcase import WaterfallTestCase


class DetermineApproximatePassRatePipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testDetermineApproximatePassRateFirstRunNewDataPoint(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()
    commit_position = 1000
    incoming_pass_count = 15
    iterations = 30
    isolate_sha = 'sha1'
    timeout_seconds = 3600
    revision = 'r1000'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        previous_swarming_task_output=None,
        revision=revision)

    flake_swarming_task_input = RunFlakeSwarmingTaskInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        iterations=iterations,
        timeout_seconds=timeout_seconds)

    flake_swarming_task_output = RunFlakeSwarmingTaskOutput(
        error=None,
        pass_count=incoming_pass_count,
        iterations=iterations,
        completed_time=completed_time,
        started_time=started_time,
        has_valid_artifact=True,
        task_id='task_id')

    update_data_points_input = UpdateFlakeAnalysisDataPointsInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        revision=revision,
        swarming_task_output=flake_swarming_task_output)

    recursive_input = DetermineApproximatePassRateInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        previous_swarming_task_output=flake_swarming_task_output,
        revision=revision)

    self.MockAsynchronousPipeline(RunFlakeSwarmingTaskPipeline,
                                  flake_swarming_task_input,
                                  flake_swarming_task_output)
    self.MockSynchronousPipeline(UpdateFlakeAnalysisDataPointsPipeline,
                                 update_data_points_input, None)
    self.MockGeneratorPipeline(DetermineApproximatePassRatePipelineWrapper,
                               recursive_input, None)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

  @mock.patch.object(
      data_point_util, 'MaximumSwarmingTaskRetriesReached', return_value=True)
  @mock.patch.object(run_swarming_util, 'ReportSwarmingTaskError')
  def testDetermineApproximatePassRateMaximumRetriesPerSwarmingTaskReached(
      self, mocked_error_reporting, _):
    commit_position = 1000
    incoming_pass_count = 15
    iterations = 30
    incoming_pass_rate = float(incoming_pass_count / iterations)
    isolate_sha = 'sha1'
    revision = 'r1000'
    task_id = 'task_id'
    has_valid_artifact = True
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=incoming_pass_rate, commit_position=commit_position)
    ]
    analysis.Save()

    flake_swarming_task_output = RunFlakeSwarmingTaskOutput(
        completed_time=completed_time,
        error=SwarmingTaskError(code=1, message='error'),
        has_valid_artifact=has_valid_artifact,
        pass_count=incoming_pass_count,
        iterations=iterations,
        started_time=started_time,
        task_id=task_id)

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        previous_swarming_task_output=flake_swarming_task_output,
        revision=revision)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    mocked_error_reporting.assert_called()

  @mock.patch.object(
      data_point_util,
      'MaximumIterationsPerDataPointReached',
      return_value=True)
  def testDetermineApproximatePassRateMaximumIterationsPerDataPointReached(
      self, _):
    commit_position = 1000
    incoming_pass_count = 15
    iterations = 30
    incoming_pass_rate = float(incoming_pass_count / iterations)
    isolate_sha = 'sha1'
    revision = 'r1000'
    task_id = 'task_id'
    has_valid_artifact = True
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=incoming_pass_rate, commit_position=commit_position)
    ]
    analysis.Save()

    flake_swarming_task_output = RunFlakeSwarmingTaskOutput(
        error=None,
        pass_count=incoming_pass_count,
        iterations=iterations,
        started_time=started_time,
        completed_time=completed_time,
        has_valid_artifact=has_valid_artifact,
        task_id=task_id)

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        previous_swarming_task_output=flake_swarming_task_output,
        revision=revision)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

  @mock.patch.object(
      data_point_util,
      'MaximumIterationsPerDataPointReached',
      return_value=False)
  @mock.patch.object(pass_rate_util, 'TestDoesNotExist', return_value=True)
  def testDetermineApproximatePassRateTestDoesNotExist(self, *_):
    commit_position = 1000
    incoming_pass_count = 0
    iterations = 0
    incoming_pass_rate = flake_constants.PASS_RATE_TEST_NOT_FOUND
    isolate_sha = 'sha1'
    revision = 'r1000'
    task_id = 'task_id'
    has_valid_artifact = True
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=incoming_pass_rate, commit_position=commit_position)
    ]
    analysis.Save()

    flake_swarming_task_output = RunFlakeSwarmingTaskOutput(
        error=None,
        pass_count=incoming_pass_count,
        iterations=iterations,
        task_id=task_id,
        started_time=started_time,
        completed_time=completed_time,
        has_valid_artifact=has_valid_artifact)

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        previous_swarming_task_output=flake_swarming_task_output,
        revision=revision)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

  @mock.patch.object(
      data_point_util,
      'MaximumIterationsPerDataPointReached',
      return_value=False)
  @mock.patch.object(pass_rate_util, 'TestDoesNotExist', return_value=False)
  @mock.patch.object(
      pass_rate_util,
      'HasSufficientInformationForConvergence',
      return_value=True)
  def testDetermineApproximatePassRateConverged(self, *_):
    commit_position = 1000
    incoming_pass_count = 15
    iterations = 30
    incoming_pass_rate = 0.5
    isolate_sha = 'sha1'
    revision = 'r1000'
    started_time = datetime(2018, 1, 1, 0, 0, 0)
    completed_time = datetime(2018, 1, 1, 1, 0, 0)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=incoming_pass_rate, commit_position=commit_position)
    ]
    analysis.Save()

    flake_swarming_task_output = RunFlakeSwarmingTaskOutput(
        error=None,
        pass_count=incoming_pass_count,
        iterations=iterations,
        started_time=started_time,
        completed_time=completed_time,
        has_valid_artifact=True,
        task_id='task_id')

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        previous_swarming_task_output=flake_swarming_task_output,
        revision=revision)

    pipeline_job = DetermineApproximatePassRatePipeline(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()

  def testDetermineApproximatePassRatePipelineWrapper(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()
    commit_position = 1000
    isolate_sha = 'sha1'
    revision = 'r1000'

    determine_approximate_pass_rate_input = DetermineApproximatePassRateInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=commit_position,
        isolate_sha=isolate_sha,
        previous_swarming_task_output=None,
        revision=revision)

    self.MockGeneratorPipeline(DetermineApproximatePassRatePipeline,
                               determine_approximate_pass_rate_input, None)

    pipeline_job = DetermineApproximatePassRatePipelineWrapper(
        determine_approximate_pass_rate_input)
    pipeline_job.start()
    self.execute_queued_tasks()
