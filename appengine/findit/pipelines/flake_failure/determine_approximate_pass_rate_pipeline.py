# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from dto.flakiness import Flakiness
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import pipeline
from gae_libs.pipelines import SynchronousPipeline
from libs.list_of_basestring import ListOfBasestring
from libs.structured_object import StructuredObject
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaOutput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskInput)
from pipelines.flake_failure.run_flake_swarming_task_pipeline import (
    RunFlakeSwarmingTaskPipeline)
from services.flake_failure import flakiness_util
from services.flake_failure import pass_rate_util
from services.flake_failure import run_swarming_util


class AggregateFlakinessInput(StructuredObject):
  # The Flakiness object to update.
  flakiness_thus_far = Flakiness

  # The flake swarming task output with which to update flakiness with.
  incoming_swarming_task_output = FlakeSwarmingTaskOutput


class AggregateFlakinessPipeline(SynchronousPipeline):
  """Aggregates new swarming task results into Flakiness."""
  input_type = AggregateFlakinessInput
  output_type = Flakiness

  def RunImpl(self, parameters):
    """Aggregates new swarming task results into Flakines."""
    return flakiness_util.UpdateFlakiness(
        parameters.flakiness_thus_far, parameters.incoming_swarming_task_output)


class DetermineApproximatePassRateInput(StructuredObject):
  # The name of the master used to trigger swarming tasks.
  master_name = basestring

  # The name of the builder used to trigger swarming tasks.
  builder_name = basestring

  # A reference build number to trigger swarming tasks.
  reference_build_number = int

  # The name of the step containing the test to analyze.
  step_name = basestring

  # The name of the test to analyze.
  test_name = basestring

  # The commit position being analyzed.
  commit_position = int

  # The current pass rate information about the test being examined thus far.
  flakiness_thus_far = Flakiness

  # The isolate sha and other fields corresponding to the commit_position.
  get_isolate_sha_output = GetIsolateShaOutput

  # The output of the last swarming task that was run to update the current
  # flakiness thus far.
  previous_swarming_task_output = FlakeSwarmingTaskOutput

  # The revision corresponding to the commit position.
  revision = basestring


class DetermineApproximatePassRatePipeline(GeneratorPipeline):
  """Determines the true pass rate of a test at a commit position."""

  input_type = DetermineApproximatePassRateInput

  def RunImpl(self, parameters):
    """Pipeline to find the true pass rate of a test at a commit position."""
    master_name = parameters.master_name
    builder_name = parameters.builder_name
    reference_build_number = parameters.reference_build_number
    step_name = parameters.step_name
    test_name = parameters.test_name
    commit_position = parameters.commit_position
    get_isolate_sha_output = parameters.get_isolate_sha_output
    build_url = get_isolate_sha_output.build_url
    try_job_url = get_isolate_sha_output.try_job_url
    flakiness_thus_far = parameters.flakiness_thus_far
    previous_swarming_task_output = parameters.previous_swarming_task_output

    # Extract pass rate and iterations already-completed up to this point.
    if previous_swarming_task_output:
      assert flakiness_thus_far, (
          'Previous swarming task output not captured properly')
      error = previous_swarming_task_output.error
      pass_rate_at_commit_position = flakiness_thus_far.pass_rate
      previous_pass_count = previous_swarming_task_output.pass_count
      previous_iterations = previous_swarming_task_output.iterations
      previous_pass_rate = (
          float(previous_pass_count / previous_iterations)
          if previous_iterations else None)
    else:
      error = None
      pass_rate_at_commit_position = None
      previous_iterations = 0
      previous_pass_count = 0
      previous_pass_rate = None

      # Create a fresh Flakiness instance to aggregate swarming rerun data.
      flakiness_thus_far = Flakiness(
          build_number=get_isolate_sha_output.build_number,
          build_url=build_url,
          commit_position=commit_position,
          total_test_run_seconds=0,
          error=None,
          failed_swarming_task_attempts=0,
          iterations=0,
          pass_rate=None,
          revision=parameters.revision,
          task_ids=ListOfBasestring.FromSerializable([]),
          try_job_url=try_job_url)

    # Bail out if there were too many errors.
    if (error and
        flakiness_util.MaximumSwarmingTaskRetriesReached(flakiness_thus_far)):
      logging.error(
          'Swarming task ended in error after %d failed attempts. Giving '
          'up' % flakiness_thus_far.failed_swarming_task_attempts)
      flakiness_thus_far.error = error
      yield AggregateFlakinessPipeline(
          self.CreateInputObjectInstance(
              AggregateFlakinessInput,
              flakiness_thus_far=flakiness_thus_far,
              incoming_swarming_task_output=None))
      return

    # Move on if the maximum number of iterations has been reached or exceeded.
    if flakiness_util.MaximumIterationsReached(flakiness_thus_far):
      logging.info(
          'Max iterations reached for commit_position %d' % commit_position)
      yield AggregateFlakinessPipeline(
          self.CreateInputObjectInstance(
              AggregateFlakinessInput,
              flakiness_thus_far=flakiness_thus_far,
              incoming_swarming_task_output=None))
      return

    # Move on if the test doesn't exist.
    if pass_rate_util.TestDoesNotExist(pass_rate_at_commit_position):
      logging.info('No test found at commit position %d' % commit_position)
      yield AggregateFlakinessPipeline(
          self.CreateInputObjectInstance(
              AggregateFlakinessInput,
              flakiness_thus_far=flakiness_thus_far,
              incoming_swarming_task_output=None))
      return

    # Move on if there is sufficient information about the pass rate.
    if pass_rate_util.HasSufficientInformation(
        pass_rate_at_commit_position, flakiness_thus_far.iterations,
        previous_pass_rate, previous_iterations):
      logging.info(
          'There is sufficient information for commit position %d with pass '
          'rate %s after %d iterations' % (commit_position,
                                           pass_rate_at_commit_position,
                                           flakiness_thus_far.iterations))
      yield AggregateFlakinessPipeline(
          self.CreateInputObjectInstance(
              AggregateFlakinessInput,
              flakiness_thus_far=flakiness_thus_far,
              incoming_swarming_task_output=None))
      return

    # Another swarming task is needed. Determine parameters for it to run.
    iterations_for_task, time_for_task_seconds = (
        run_swarming_util.CalculateRunParametersForSwarmingTask(
            flakiness_thus_far, error))

    # Run swarming task, update data points with results, and recurse.
    with pipeline.InOrder():
      swarming_task_output = yield RunFlakeSwarmingTaskPipeline(
          self.CreateInputObjectInstance(
              RunFlakeSwarmingTaskInput,
              master_name=master_name,
              builder_name=builder_name,
              reference_build_number=reference_build_number,
              step_name=step_name,
              test_name=test_name,
              commit_position=commit_position,
              isolate_sha=get_isolate_sha_output.isolate_sha,
              iterations=iterations_for_task,
              timeout_seconds=time_for_task_seconds))

      aggregated_flakiness = yield AggregateFlakinessPipeline(
          self.CreateInputObjectInstance(
              AggregateFlakinessInput,
              flakiness_thus_far=flakiness_thus_far,
              incoming_swarming_task_output=swarming_task_output))

      yield DetermineApproximatePassRatePipelineWrapper(
          self.CreateInputObjectInstance(
              DetermineApproximatePassRateInput,
              builder_name=parameters.builder_name,
              commit_position=commit_position,
              flakiness_thus_far=aggregated_flakiness,
              get_isolate_sha_output=get_isolate_sha_output,
              master_name=parameters.master_name,
              previous_swarming_task_output=swarming_task_output,
              reference_build_number=parameters.reference_build_number,
              revision=parameters.revision,
              step_name=parameters.step_name,
              test_name=parameters.test_name))


class DetermineApproximatePassRatePipelineWrapper(GeneratorPipeline):
  """A wrapper for DetermineApproximatePassRatePipeline for testability only.

    Because DetermineApproximatePassRatePipeline is recursive, in unit tests it
    is not possible to mock only the recursive call to validate its input
    independently of the original call.
  """

  input_type = DetermineApproximatePassRateInput

  def RunImpl(self, parameters):
    yield DetermineApproximatePassRatePipeline(parameters)
