# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import timedelta
import random

from common.findit_http_client import FinditHttpClient
from infra_api_clients.swarming import swarming_util
from libs import time_util
from services import swarming
from waterfall import waterfall_config
from waterfall.flake import flake_constants

DEFAULT_MINIMUM_NUMBER_AVAILABLE_BOTS = 5
DEFAULT_MINIMUM_PERCENTAGE_AVAILABLE_BOTS = 0.1

# TODO(crbug.com/809885): Merge with
# services/flake_failure/flake_analysis_util.py.


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
  timeout_per_test = (
      timeout_per_test
      if timeout_per_test else flake_constants.DEFAULT_TIMEOUT_PER_TEST_SECONDS)
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
      analysis.algorithm_parameters.get(
          'swarming_task_cushion', flake_constants.
          SWARMING_TASK_CUSHION_MULTIPLIER) * time_per_iteration)


def GetETAToStartAnalysis(manually_triggered):
  """Returns an ETA as of a UTC datetime.datetime to start the analysis.

  If not urgent, Swarming tasks should be run off PST peak hours from 11am to
  6pm on workdays.

  Args:
    manually_triggered (bool): True if the analysis is from manual request, like
        by a Chromium sheriff.

  Returns:
    The ETA as of a UTC datetime.datetime to start the analysis.
  """
  if manually_triggered:
    # If the analysis is manually triggered, run it right away.
    return time_util.GetUTCNow()

  now_at_pst = time_util.GetPSTNow()
  if now_at_pst.weekday() >= 5:  # PST Saturday or Sunday.
    return time_util.GetUTCNow()

  if now_at_pst.hour < 11 or now_at_pst.hour >= 18:  # Before 11am or after 6pm.
    return time_util.GetUTCNow()

  # Set ETA time to 6pm, and also with a random latency within 30 minutes to
  # avoid sudden burst traffic to Swarming.
  diff = timedelta(
      hours=18 - now_at_pst.hour,
      minutes=-now_at_pst.minute,
      seconds=-now_at_pst.second + random.randint(0, 30 * 60),
      microseconds=-now_at_pst.microsecond)
  eta = now_at_pst + diff

  # Convert back to UTC.
  return time_util.ConvertPSTToUTC(eta)


def BotsAvailableForTask(step_metadata):
  """Check if there are available bots for a swarming task's dimensions."""
  if not step_metadata:
    return False

  minimum_number_of_available_bots = (
      waterfall_config.GetSwarmingSettings().get(
          'minimum_number_of_available_bots',
          DEFAULT_MINIMUM_NUMBER_AVAILABLE_BOTS))
  minimum_percentage_of_available_bots = (
      waterfall_config.GetSwarmingSettings().get(
          'minimum_percentage_of_available_bots',
          DEFAULT_MINIMUM_PERCENTAGE_AVAILABLE_BOTS))
  dimensions = step_metadata.get('dimensions')
  bot_counts = swarming_util.GetBotCounts(swarming.SwarmingHost(), dimensions,
                                          FinditHttpClient)
  total_count = bot_counts.count or -1
  available_count = bot_counts.available or 0
  available_rate = float(available_count) / total_count

  return (available_count > minimum_number_of_available_bots and
          available_rate > minimum_percentage_of_available_bots)
