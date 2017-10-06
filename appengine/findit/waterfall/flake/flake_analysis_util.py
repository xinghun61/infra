# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.flake.flake_swarming_task import FlakeSwarmingTask

from waterfall.flake import flake_constants


class NormalizedDataPoint(object):
  """Class to encapsulate a generalized data-point.

  This data point contains information used in both commit position/build number
  so it can be used with functions that require either.
  """

  def __init__(self, run_point_number, pass_rate, has_valid_artifact=True):
    self.run_point_number = run_point_number
    self.pass_rate = pass_rate
    self.has_valid_artifact = has_valid_artifact


def GetIterationsToRerun(user_specified_iterations,
                         analysis,
                         source='swarming_rerun'):
  """Retrieves the iterations to rerun from the analysis' settings.

  Uses the analysis, and given source to determine the iterations to rerun
  for this specific task.

  Args:
    user_specified_iterations (int): The user specified iterations, will use
        this instead of analysis info if given.
    analysis (MasterFlakeAnalysis): Analysis to get the settings from.
    source (string): Source within the algorithm_parameters of the analysis
      to get the iterations_to_rerun. These values can only be 'swarming_rerun'
      or 'try_job_rerun'.

  Returns:
    (int) Iterations to rerun.
  """
  return user_specified_iterations or analysis.algorithm_parameters.get(
      source, {}).get('iterations_to_rerun',
                      flake_constants.DEFAULT_SWARMING_TASK_ITERATIONS_TO_RERUN)


def NormalizeDataPointsByBuildNumber(data_points):
  """Converts a list of data points into a list of normalized data points.

    Data points need to be normalized before passing into lookback_algorithm.py,
    which is agnostic to build numbers and commit positions.

  Args:
    data_points (list): A list of DataPoint objects.

  Returns:
    A list of NormalizedDataPoint objects based on data_points, sorted by
    run point number in ascending order.
  """
  normalized_data_points = [(NormalizedDataPoint(data_point.build_number,
                                                 data_point.pass_rate,
                                                 data_point.has_valid_artifact))
                            for data_point in data_points]
  return sorted(
      normalized_data_points, key=lambda k: k.run_point_number, reverse=True)


def CalculateNumberOfIterationsToRunWithinTimeout(analysis, timeout_per_test):
  """Calculates the number of iterations that will run in one swarming task.

  Uses the total iterations, target timeout, and the timeout per test to
  calculate the appropriate amount of test iterations to run.

  Args:
    analysis (MasterFlakeAnalysis): The analysis being run.
    timeout_per_test (int): Time, in seconds, that each test will take.

  Returns:
    (int) Number of iterations to perform in one swarming task.
  """
  timeout_per_test = (timeout_per_test if timeout_per_test else
                      flake_constants.DEFAULT_TIMEOUT_PER_TEST_SECONDS)
  timeout_per_swarming_task = analysis.algorithm_parameters.get(
      'swarming_rerun',
      {}).get('timeout_per_swarming_task_seconds',
              flake_constants.DEFAULT_TIMEOUT_PER_SWARMING_TASK_SECONDS)
  iterations = timeout_per_swarming_task / timeout_per_test

  # We should never be running 0 iterations.
  return max(1, iterations)


def EstimateSwarmingIterationTimeout(analysis, build_number):
  """Estimates a timeout per iteration based on previous data points.

  Uses the amount of time previous data points at this build number took to
  estimate a timeout for an iteration.

  Args:
    analysis (MasterFlakeAnalysis): The analysis being run.
    build_number (int): The current build number.

  Return:
    (int) Timeout for one iteration in seconds.
  """

  point = analysis.FindMatchingDataPointWithBuildNumber(build_number)

  if not point:
    return analysis.algorithm_parameters.get('swarming_rerun', {}).get(
        'timeout_per_test_seconds',
        flake_constants.DEFAULT_TIMEOUT_PER_TEST_SECONDS)

  assert point.elapsed_seconds > 0
  assert point.iterations > 0
  assert point.pass_rate >= 0

  # Set lower threshold for timeout per iteration.
  time_per_iteration = float(point.elapsed_seconds) / float(point.iterations)

  analysis.LogInfo(('Estimated %d seconds timeout per iterations based on '
                    '%d elapsed seconds and %d iterations.' %
                    (int(time_per_iteration), point.elapsed_seconds,
                     point.iterations)))

  return int(
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER * time_per_iteration)
