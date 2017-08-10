# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from waterfall.flake import flake_constants


class NormalizedDataPoint(object):

  def __init__(self, run_point_number, pass_rate, has_valid_artifact=True):
    self.run_point_number = run_point_number
    self.pass_rate = pass_rate
    self.has_valid_artifact = has_valid_artifact


def UpdateIterationsToRerun(analysis, iterations_to_rerun):
  if not iterations_to_rerun or not analysis.algorithm_parameters:
    return

  analysis.algorithm_parameters['swarming_rerun'][
      'iterations_to_rerun'] = iterations_to_rerun

  analysis.algorithm_parameters['try_job_rerun'][
      'iterations_to_rerun'] = iterations_to_rerun


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
