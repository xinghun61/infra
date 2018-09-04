# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to assist in estimating flakiness of a test."""

from services.flake_failure import flake_analysis_util
from services.flake_failure import flake_constants
from services.flake_failure import pass_rate_util
from waterfall import waterfall_config


def _GetMaximumIterationsToRun():
  return waterfall_config.GetCheckFlakeSettings().get(
      'max_iterations_to_rerun',
      flake_constants.DEFAULT_MAX_ITERATIONS_TO_RERUN)


def _GetMaximumSwarmingTaskRetries():
  return waterfall_config.GetCheckFlakeSettings().get(
      'maximum_swarming_task_retries_per_flakiness',
      flake_constants.DEFAULT_MAX_SWARMING_TASK_RETRIES_PER_DATA_POINT)


def MaximumIterationsReached(flakiness):
  """Determines whether a Flakiness has achieved the required iterations."""
  max_iterations_to_run = _GetMaximumIterationsToRun()
  return flakiness.iterations >= max_iterations_to_run


def MaximumSwarmingTaskRetriesReached(flakiness):
  """Determines whether a data point has too many failed swarming task attempts.

  Args:
    flakiness (Flakiness): The Flakiness to check.

  Returns:
    True if the data point has had too many failed attempts at a swarming task.
  """
  max_swarming_retries = _GetMaximumSwarmingTaskRetries()
  return flakiness.failed_swarming_task_attempts > max_swarming_retries


def UpdateFlakiness(flakiness, incoming_swarming_task_output):
  """Updates flakiness with swarming task output.

  Args:
    flakiness (Flakiness): The flakiness thus far to update.
    incoming_swarming_task_output (RunFlakeSwarmingTaskOutput): The results of
        a flake swarming task to update flakiness with.

  Returns:
    flakiness (Flakiness): The updated flakiness entity.
  """
  assert flakiness, 'No Flakiness object to update'

  if not incoming_swarming_task_output:
    # Nothing to update with.
    return flakiness

  error = incoming_swarming_task_output.error
  task_id = incoming_swarming_task_output.task_id

  if task_id:  # pragma: no branch
    # Always track all swarming tasks triggered for generating Flakiness,
    # regardless of error for diagnostic information.
    flakiness.task_ids.append(task_id)

  # Integrate incoming swarming task output into already aggregated Flakiness.
  if error and not flake_analysis_util.CanFailedSwarmingTaskBeSalvaged(
      incoming_swarming_task_output):
    # The latest swarming task ran into an error.
    # TODO(crbug.com/808947): A failed swarming task's partial data can
    # sometimes still be salvaged.
    flakiness.failed_swarming_task_attempts += 1
    return flakiness

  # An undetected error occurred. Assert to prevent writing faulty data.
  assert incoming_swarming_task_output.iterations is not None, (
      'Expected swarming task output to have iterations, but got None')
  assert incoming_swarming_task_output.pass_count is not None, (
      'Expected swarming task output to have pass count, but got None')

  # Aggregate swarming task output into Flakiness.
  if (flakiness.pass_rate is None and
      flakiness.failed_swarming_task_attempts == 0):
    # First ever pass at aggregating flakiness.
    flakiness.total_test_run_seconds = (
        incoming_swarming_task_output.GetElapsedSeconds())
    flakiness.iterations = incoming_swarming_task_output.iterations
    flakiness.pass_rate = pass_rate_util.GetPassRate(
        incoming_swarming_task_output)
    return flakiness

  # The latest swarming task completed successfully. Incorporate the incoming
  # data with the existing data point.
  old_pass_rate = flakiness.pass_rate or 0
  old_iterations = flakiness.iterations
  incoming_iterations = incoming_swarming_task_output.iterations
  incoming_pass_rate = pass_rate_util.GetPassRate(incoming_swarming_task_output)

  # Ensure the are no discrepancies between old and new pass rates about the
  # test existing or not at the same commit position. If this assert occurs it
  # may indicate something wrong with nonexistent-test detection.
  assert not (pass_rate_util.TestDoesNotExist(incoming_pass_rate) and
              not pass_rate_util.TestDoesNotExist(old_pass_rate)), (
                  'Discrepancy about test existance')

  incoming_total_test_run_seconds = (
      incoming_swarming_task_output.GetElapsedSeconds())
  assert incoming_total_test_run_seconds is not None, (
      'Incoming swarming task elapsed seconds is None')

  flakiness.pass_rate = pass_rate_util.CalculateNewPassRate(
      old_pass_rate, old_iterations, incoming_pass_rate, incoming_iterations)
  flakiness.iterations += incoming_iterations
  flakiness.total_test_run_seconds += incoming_total_test_run_seconds

  return flakiness
