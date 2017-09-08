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


def UpdateIterationsToRerun(analysis, iterations_to_rerun):
  """Updates iterations to rerun in the analaysis' algorithm parameters"""
  if not iterations_to_rerun or not analysis.algorithm_parameters:
    return

  analysis.algorithm_parameters['swarming_rerun'][
      'iterations_to_rerun'] = iterations_to_rerun

  analysis.algorithm_parameters['try_job_rerun'][
      'iterations_to_rerun'] = iterations_to_rerun

  analysis.put()


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


def CalculateNumberOfIterationsToRunWithinTimeout(analysis, iterations,
                                                  timeout_per_test):
  """Calculates the number of iterations that will run in one swarming task.

  Uses the total iterations, target timeout, and the timeout per test to
  calculate the appropriate amount of test iterations to run.

  Args:
    analysis (MasterFlakeAnalysis): The analysis being run.
    iterations (int): Total number of iterations left.
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
  target_iterations = timeout_per_swarming_task / timeout_per_test

  iterations_this_task = min(iterations, target_iterations)

  # We should never be running 0 tasks.
  return max(1, iterations_this_task)


def EstimateSwarmingIterationTimeout(analysis):
  """Estimates a timeout per iteration based on previous data points.

  Uses the amount of time previous data points at this build number took to
  estimate a timeout for an iteration.
  """
  sample_size = analysis.algorithm_parameters.get('swarming_rerun', {}).get(
      'data_point_sample_size', flake_constants.DEFAULT_DATA_POINT_SAMPLE_SIZE)

  default_timeout_per_test = analysis.algorithm_parameters.get(
      'swarming_rerun',
      {}).get('timeout_per_test_seconds',
              flake_constants.DEFAULT_TIMEOUT_PER_TEST_SECONDS)

  # Trim off the points that have None for iterations.
  # TODO(https://crbug.com/761025): Investigate and fix models missing
  # fields by the time they're saved.
  points = [
      point for point in analysis.data_points if point.iterations is not None
  ]
  last_n_points = points[-sample_size:]

  if not last_n_points:
    return default_timeout_per_test

  tasks = [
      FlakeSwarmingTask.Get(analysis.master_name, analysis.builder_name,
                            point.build_number, analysis.step_name,
                            analysis.test_name) for point in last_n_points
  ]

  assert None not in tasks
  assert len(tasks) == len(last_n_points)

  total_iterations = sum([task.tries for task in tasks])
  total_time = sum([(task.completed_time - task.started_time).total_seconds()
                    for task in tasks])

  # Set lower threshold for timeout per iteration.
  time_per_iteration = max(default_timeout_per_test,
                           total_time / total_iterations)

  return int(
      flake_constants.SWARMING_TASK_CUSHION_MULTIPLIER * time_per_iteration)
