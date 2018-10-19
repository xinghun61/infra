# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to assist in operations on DataPoint objects."""

from model.flake.analysis.data_point import DataPoint
from services.flake_failure import pass_rate_util


def ConvertFlakinessToDataPoint(flakiness):
  """Converts Flakiness to DataPoint."""
  return DataPoint.Create(
      build_number=flakiness.build_number,
      build_url=flakiness.build_url,
      commit_position=flakiness.commit_position,
      elapsed_seconds=flakiness.total_test_run_seconds,
      error=flakiness.error,
      failed_swarming_task_attempts=flakiness.failed_swarming_task_attempts,
      git_hash=flakiness.revision,
      iterations=flakiness.iterations,
      pass_rate=flakiness.pass_rate,
      task_ids=flakiness.task_ids.ToSerializable(),
      try_job_url=flakiness.try_job_url)


def HasSeriesOfFullyStablePointsPrecedingCommitPosition(
    data_points, commit_position, required_number_of_stable_points):
  """Checks for a minimum number of fully-stable points before a given commit.

    Fully-stable must also be the same type of stable and for existing tests
    only. Forexample, fully-passing to fully-passing and fully-failing to fully-
    failing. This function should not be used when handling newly-added tests.

  Args:
    data_points ([DataPoint]): The list of data points of a MasterFlakeAnalysis.
    commit_position (int): The commit position to find stable points preceding.
    required_number_of_stable_points (int): The minimum number of data points
        of the same fully-stable type required in order to send a notification
        to a code review.
  """
  if required_number_of_stable_points > len(data_points):
    return False

  # Ensure the data points are sorted before processing.
  ordered_data_points = sorted(data_points, key=lambda k: k.commit_position)

  fully_stable_data_points_in_a_row = 0
  previous_data_point = data_points[0]

  for data_point in ordered_data_points:
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
