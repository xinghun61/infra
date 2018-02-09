# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to assist in operations on DataPoint objects."""

from services.flake_failure import pass_rate_util
from waterfall import waterfall_config
from waterfall.flake import flake_constants


def GetMaximumIterationsToRunPerDataPoint():
  return waterfall_config.GetCheckFlakeSettings().get(
      'max_iterations_to_rerun',
      flake_constants.DEFAULT_MAX_ITERATIONS_TO_RERUN)


def GetMaximumSwarmingTaskRetriesPerDataPoint():
  return waterfall_config.GetCheckFlakeSettings().get(
      'maximum_swarming_task_retries_per_data_point',
      flake_constants.DEFAULT_MAX_SWARMING_TASK_RETRIES_PER_DATA_POINT)


def HasSeriesOfFullyStablePointsPrecedingCommitPosition(
    data_points, commit_position, required_number_of_stable_points):
  """Checks for a minimum number of fully-stable points before a given commit.

    Fully-stable must also be the same type of stable and for existing tests
    only. Forexample, fully-passing to fully-passing and fully-failing to fully-
    failing. This function should not be used when handling newly-added tests.

  Args:
    data_points ([DataPoint]): The list of data points of a MasterFlakeAnalysis.
        data_points is expected to be pre-sorted in ascending order by commit
        position.
    commit_position (int): The commit position to find stable points preceding.
    required_number_of_stable_points (int): The minimum number of data points
        of the same fully-stable type required in order to send a notification
        to a code review.
  """
  if required_number_of_stable_points > len(data_points):
    return False

  fully_stable_data_points_in_a_row = 0
  previous_data_point = data_points[0]

  for data_point in data_points:
    if data_point.commit_position == commit_position:
      break

    if pass_rate_util.IsFullyStable(data_point.pass_rate):
      # Only 100% passing or 100% failing can count towards fully-stable.
      if pass_rate_util.ArePassRatesEqual(data_point.pass_rate,
                                          previous_data_point.pass_rate):
        # Must be the same type of fully-stable in order to count towards the
        # series.
        fully_stable_data_points_in_a_row += 1
      else:
        # A new series of stable passing/failing began. For example, if a series
        # of passes is followed by a failure, begin counting at the failure.
        fully_stable_data_points_in_a_row = 1
    else:
      # A slightly-flaky data point was encuntered. Reset the count.
      fully_stable_data_points_in_a_row = 0

    previous_data_point = data_point

  return fully_stable_data_points_in_a_row >= required_number_of_stable_points


def MaximumSwarmingTaskRetriesReached(data_point):
  """Determines whether a data point has too many failed swarming task attempts.

  Args:
    data_point (DataPoint): The data point to check.

  Returns:
    True if the data point has had too many failed attempts at a swarming task.
  """
  max_swarming_retries = GetMaximumSwarmingTaskRetriesPerDataPoint()
  return data_point.failed_swarming_task_attempts > max_swarming_retries


def MaximumIterationsPerDataPointReached(iterations):
  max_iterations_to_run = GetMaximumIterationsToRunPerDataPoint()
  return iterations >= max_iterations_to_run


def UpdateFailedSwarmingTaskAttempts(data_point):
  assert data_point
  data_point.failed_swarming_task_attempts += 1
  data_point.put()
