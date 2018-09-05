# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to assist in determining swarming parameters for flake analysis."""

from common import monitoring
from dto import swarming_task_error
from libs import analysis_status
from libs import time_util
from services.flake_failure import flake_constants
from waterfall import waterfall_config


def _CalculateNumberOfIterationsToRunWithinTimeout(estimated_timeout_per_test):
  """Calculates the number of iterations that will run in one swarming task.

  Uses the total iterations, target timeout, and the timeout per test to
  calculate the appropriate amount of test iterations to run.

  Args:
    estimated_timeout_per_test (int): Time, in seconds, that each test will
    is estimated to take. Can be 0 if unknown, and a default used instead.

  Returns:
    (int) Number of iterations to perform in one swarming task.
  """
  timeout_per_test = (
      estimated_timeout_per_test or
      flake_constants.DEFAULT_TIMEOUT_PER_TEST_SECONDS)
  timeout_per_swarming_task = waterfall_config.GetCheckFlakeSettings().get(
      'timeout_per_swarming_task_seconds',
      flake_constants.DEFAULT_TIMEOUT_PER_SWARMING_TASK_SECONDS)

  iterations = timeout_per_swarming_task / timeout_per_test

  # Always run at least 1 iteration.
  return max(1, iterations)


def _EstimateSwarmingIterationTimeout(flakiness):
  """Estimates a timeout per iteration based on previous data points.

  Uses the amount of time previous data points at this build number took to
  estimate a timeout for an iteration.

  Args:
    flakiness (Flakiness): Information representing the flakiness and other
        metadata at a commit position.

  Return:
    (int) Timeout for one iteration in seconds.
  """
  check_flake_settings = waterfall_config.GetCheckFlakeSettings()

  if not flakiness.total_test_run_seconds or not flakiness.iterations:
    # There is insufficient data to calculate a timeout, possibly due to error.
    # Fallback to safe values.
    return check_flake_settings.get(
        'timeout_per_test_seconds',
        flake_constants.DEFAULT_TIMEOUT_PER_TEST_SECONDS)

  # Set lower threshold for timeout per iteration.
  time_per_iteration = (
      float(flakiness.total_test_run_seconds) / float(flakiness.iterations))

  # Add padding to for a more pessimistic per-test estimated time. For example,
  # if 60 iterations were measured to have ran in 60 seconds, theoretically 1
  # should take 1 second. However there can be some variance in the run time, so
  # to be safe, we multiply that theoretical time by a constant factor (e.g. 2)
  # to give an adjusted time of 2 seconds per test to trigger tasks with more a
  # conservative number of iterations.
  cushion_multiplier = check_flake_settings.get(
      'swarming_task_cushion', flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER)

  return int(round(cushion_multiplier * time_per_iteration))


def _EstimateTimeoutForTask(estimated_timeout_per_test,
                            estimated_iterations_for_task):
  """Returns the timeout for a swarming task.

  Returns either timeout_per_test * iterations_for_task or the default timeout
  for a swarming task (whichever is greater).

  Args:
    estimated_timeout_per_test (int): timeout per test derived from existing
        data points.
    estimated_iterations_for_task (int): total number of iterations for the
        task derived from existing data points.
  Returns:
    (int): The estimated timeout for a swarming task.
  """
  minimum_timeout = waterfall_config.GetCheckFlakeSettings().get(
      'timeout_per_swarming_task_seconds',
      flake_constants.DEFAULT_TIMEOUT_PER_SWARMING_TASK_SECONDS)

  return max(estimated_timeout_per_test * estimated_iterations_for_task,
             minimum_timeout)


def _GetMaximumIterationsPerSwarmingTask(requested_iterations_for_task):
  """Returns the maximum iterations not to exceed per swarming task."""
  max_iterations_per_task = waterfall_config.GetCheckFlakeSettings().get(
      'max_iterations_per_task', flake_constants.MAX_ITERATIONS_PER_TASK)

  return min(max_iterations_per_task, requested_iterations_for_task)


def CalculateRunParametersForSwarmingTask(flakiness, error):
  """Calculates and returns the iterations and timeout for swarming tasks

  Args:
    flakiness (Flakiness): A structure representing flakiness thus far.
    error (SwarmingError): The error of the previously-run swarming
        task at commit_position. Should be None if no error was encountered.

  Returns:
      ((int) iterations, (int) timeout) Tuple containing the iterations to run
          for this swarming task, and the timeout for that task.
  """
  assert flakiness, 'Cannot calculate parameters for nonexistent Flakiness'

  timeout_per_test = _EstimateSwarmingIterationTimeout(flakiness)
  iterations_for_task = _CalculateNumberOfIterationsToRunWithinTimeout(
      timeout_per_test)
  time_for_task_seconds = _EstimateTimeoutForTask(timeout_per_test,
                                                  iterations_for_task)

  if error and error.code == swarming_task_error.TIMED_OUT:
    # If the previous run timed out, run a smaller, fixed number of
    # iterations so the next attempt is more likely to finish.
    iterations_for_task = waterfall_config.GetCheckFlakeSettings().get(
        'iterations_to_run_after_timeout',
        flake_constants.DEFAULT_ITERATIONS_TO_RUN_AFTER_TIMEOUT)
  else:
    # If the calculated number of iterations is too many, reduce it rather than
    # increase the timeout to minimize the load on swarming.
    iterations_for_task = (
        _GetMaximumIterationsPerSwarmingTask(iterations_for_task))

  return iterations_for_task, time_for_task_seconds


def ReportSwarmingTaskError(analysis, error):
  """Reports an error in a swarming task affecting a MasterFlakeAnalysis.

  Args:
    analysis (MasterFlakeAnalysis): The analysis that had the error.
    error (SwarmingTaskError): The error to report.
  """
  if not error:
    return

  analysis.Update(
      status=analysis_status.ERROR,
      error=error.ToSerializable(),
      end_time=time_util.GetUTCNow())
  duration = analysis.end_time - analysis.start_time

  # Report error to ts_mon.
  monitoring.analysis_durations.add(duration.total_seconds(), {
      'type': 'flake',
      'result': 'error',
  })
