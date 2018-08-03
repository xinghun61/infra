# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import pipeline
from libs.structured_object import StructuredObject
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaOutput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskInput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskPipeline)
from pipelines.flake_failure.update_flake_analysis_data_points_pipeline import (
    UpdateFlakeAnalysisDataPointsInput)
from pipelines.flake_failure.update_flake_analysis_data_points_pipeline import (
    UpdateFlakeAnalysisDataPointsPipeline)
from services.flake_failure import data_point_util
from services.flake_failure import pass_rate_util
from services.flake_failure import run_swarming_util


class DetermineApproximatePassRateInput(StructuredObject):
  # The urlsafe key to the analysis in progress.
  analysis_urlsafe_key = basestring

  # The commit position being analyzed.
  commit_position = int

  # The isolate sha and other fields corresponding to the commit_position.
  get_isolate_sha_output = GetIsolateShaOutput

  # The output of the last swarming task that was run.
  previous_swarming_task_output = FlakeSwarmingTaskOutput

  # The revision corresponding to the commit position.
  revision = basestring


class DetermineApproximatePassRatePipeline(GeneratorPipeline):
  """Determines the true pass rate of a test at a commit position."""

  input_type = DetermineApproximatePassRateInput

  def RunImpl(self, parameters):
    """Pipeline to find the true pass rate of a test at a commit position."""
    analysis_urlsafe_key = parameters.analysis_urlsafe_key
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    commit_position = parameters.commit_position
    get_isolate_sha_output = parameters.get_isolate_sha_output
    previous_swarming_task_output = parameters.previous_swarming_task_output

    # Extract pass rate and iterations already-completed up to this point.
    data_point = (
        analysis.FindMatchingDataPointWithCommitPosition(commit_position))

    if data_point:
      # previous_swarming_task_output should be None if and only if this is the
      # first time analyzing this data point. If at any point a data point
      # already exists and this pipeline is called with
      # previous_swarming_task_output as None could be a sign of an infinite
      # loop or otherwise duplicating work.
      assert previous_swarming_task_output, (
          'Attempt to re-analyze existing data point')

    if previous_swarming_task_output:
      assert data_point
      error = previous_swarming_task_output.error
      iterations_already_completed = data_point.iterations
      pass_rate_at_commit_position = data_point.pass_rate
      previous_pass_count = previous_swarming_task_output.pass_count
      previous_iterations = previous_swarming_task_output.iterations
      previous_pass_rate = (
          float(previous_pass_count / previous_iterations)
          if previous_iterations else None)
    else:
      data_point = None
      error = None
      iterations_already_completed = 0
      pass_rate_at_commit_position = None
      previous_iterations = 0
      previous_pass_count = 0
      previous_pass_rate = None

    # Abandon the analysis if there were too many errors generating a single
    # data point.
    if error and data_point_util.MaximumSwarmingTaskRetriesReached(data_point):
      run_swarming_util.ReportSwarmingTaskError(analysis, error)
      analysis.LogError(
          'Swarming task ended in error after {} failed attempts. Giving '
          'up'.format(data_point.failed_swarming_task_attempts))
      raise pipeline.Abort()

    # Move on if the maximum number of iterations has been reached or exceeded.
    if data_point_util.MaximumIterationsPerDataPointReached(
        iterations_already_completed):
      analysis.LogInfo('Max iterations reached for commit_position {}'.format(
          commit_position))
      return

    # Move on if the test doesn't exist.
    if pass_rate_util.TestDoesNotExist(pass_rate_at_commit_position):
      analysis.LogInfo(
          'No test found at commit position {}'.format(commit_position))
      return

    # Move on if there is sufficient information about the pass rate.
    if pass_rate_util.HasSufficientInformation(
        pass_rate_at_commit_position, iterations_already_completed,
        previous_pass_rate, previous_iterations):
      analysis.LogInfo(
          'There is sufficient information for commit position {} with pass '
          'rate {} after {} iterations'.format(commit_position,
                                               pass_rate_at_commit_position,
                                               iterations_already_completed))
      return

    # Another swarming task is needed. Determine parameters for it to run.
    iterations_for_task, time_for_task_seconds = (
        run_swarming_util.CalculateRunParametersForSwarmingTask(
            analysis, commit_position, error))

    analysis.LogInfo('Running {} iterations with a {} second timeout'.format(
        iterations_for_task, time_for_task_seconds))

    # Run swarming task, update data points with results, and recurse.
    with pipeline.InOrder():
      swarming_task_input = self.CreateInputObjectInstance(
          RunFlakeSwarmingTaskInput,
          analysis_urlsafe_key=analysis_urlsafe_key,
          commit_position=commit_position,
          isolate_sha=get_isolate_sha_output.isolate_sha,
          iterations=iterations_for_task,
          timeout_seconds=time_for_task_seconds)

      swarming_task_output = yield RunFlakeSwarmingTaskPipeline(
          swarming_task_input)

      update_flake_data_points_input = self.CreateInputObjectInstance(
          UpdateFlakeAnalysisDataPointsInput,
          analysis_urlsafe_key=analysis_urlsafe_key,
          commit_position=commit_position,
          revision=parameters.revision,
          build_url=get_isolate_sha_output.build_url,
          try_job_url=get_isolate_sha_output.try_job_url,
          swarming_task_output=swarming_task_output)

      yield UpdateFlakeAnalysisDataPointsPipeline(
          update_flake_data_points_input)

      determine_approximate_pass_rate_input = self.CreateInputObjectInstance(
          DetermineApproximatePassRateInput,
          analysis_urlsafe_key=analysis_urlsafe_key,
          commit_position=commit_position,
          get_isolate_sha_output=get_isolate_sha_output,
          previous_swarming_task_output=swarming_task_output,
          revision=parameters.revision)

      yield DetermineApproximatePassRatePipelineWrapper(
          determine_approximate_pass_rate_input)


class DetermineApproximatePassRatePipelineWrapper(GeneratorPipeline):
  """A wrapper for DetermineApproximatePassRatePipeline for testability only.

    Because DetermineApproximatePassRatePipeline is recursive, in unit tests it
    is not possible to mock only the recursive call to validate its input
    independently of the original call.
  """

  input_type = DetermineApproximatePassRateInput

  def RunImpl(self, parameters):
    yield DetermineApproximatePassRatePipeline(parameters)
