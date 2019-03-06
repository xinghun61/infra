# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math

from dto.commit_id_range import CommitID
from dto.commit_id_range import CommitIDRange
from dto.int_range import IntRange
from services import git
from services.flake_failure import pass_rate_util


def _Bisect(regression_range):
  """Bisects a regression range or returns a culprit.

  Args:
    reression_range (IntRange): The latest regression range to perform the
        bisection on.

  Returns:
    (int, int): The next commit position to run and suspected commit position.
        If the next commit position is identified, there will be no suspected
        commit position and vice versa.
  """
  lower_bound = regression_range.lower
  upper_bound = regression_range.upper

  assert lower_bound is not None, 'Cannot bisect without lower bound'
  assert upper_bound is not None, 'Cannot bisect without upper bound'

  next_commit_position = BisectPoint(lower_bound.commit_position,
                                     upper_bound.commit_position)

  if next_commit_position == lower_bound.commit_position:
    return None, upper_bound

  return CommitID(
      commit_position=next_commit_position,
      revision=git.GetRevisionForCommitPositionByAnotherCommit(
          upper_bound.revision, upper_bound.commit_position,
          next_commit_position)), None


def _DetermineNextCommitPosition(data_points):
  """Determines the next numerical point to check flakiness on.

    1. When no lower bound is known yet, use a quadratically-increasing step
       size based on the distance in commit position of the previous data point,
       starting from 1.
    2. When both a lower and upper bound are known, which occurs when a stable
       and a flaky point are identified, restart exponential search backward
       from the later point (biased from the right side to avoid identifying an
       obsolete culprit).
    3. When two data points shows a flaky test is newly-added, bisect to find
       when it was added.

  Args:
    data_points (list): A list of DataPoints that have already fully been
        analyzed, sorted in descending order by commit position.

  Returns:
    (int, int): A tuple representing the next calculated commit position
        to analyze based on the flakiness trend in data_points, and a
        culprit commit position that flakiness was introduced in. Returns
        (None, culprit_commit_position) if a culprit has been identified,
        (next_commit_position, None) if further analysis is needed, or
        (None, None) if no findings or unreproducible. At no point should
        (next_commit_position, culprit_culprit_commit_position) be returned.
  """
  flakes_in_a_row = 0

  earliest_data_point = None
  for i, current_data_point in enumerate(data_points):
    pass_rate = current_data_point.pass_rate
    commit_position = current_data_point.commit_position
    earliest_data_point = current_data_point

    if pass_rate_util.TestDoesNotExist(pass_rate):
      if flakes_in_a_row > 0:
        # The test doesn't exist. It is likely the newly-added test is flaky
        # to begin with. Bisect the range between the nonexistent point and
        # when the earliest known flaky point to find when the test was
        # introduced.

        # _Bisect requires the data points to be sorted in descending order
        # by commit_position.
        previous_data_point = data_points[i - 1]

        return _Bisect(
            CommitIDRange(
                lower=CommitID(
                    commit_position=current_data_point.commit_position,
                    revision=current_data_point.git_hash),
                upper=CommitID(
                    commit_position=previous_data_point.commit_position,
                    revision=previous_data_point.git_hash)))
      else:
        # No flaky region has been identified, no findings.
        return None, None

    if pass_rate_util.IsStableDefaultThresholds(pass_rate):
      if flakes_in_a_row > 0:
        # A regression range (stable data point --> flaky data point) has been
        # identified. Perform the exponential search on that smaller range only.
        previous_data_point = data_points[i - 1]

        # Ensure the data points are sorted in descending order.
        assert (previous_data_point.commit_position >
                current_data_point.commit_position)

        # If the previous point and this one have adjacent commit positions,
        # the culprit is found.
        if previous_data_point.commit_position - commit_position == 1:
          return None, CommitID(
              commit_position=previous_data_point.commit_position,
              revision=previous_data_point.git_hash)

        if flakes_in_a_row == 1:
          # Begin the search 1 commit back from the flaky point.
          next_step_size = 1
        else:
          # Exponential search using a quadraticially-increasing step size
          # based on the distance between the previous two data points.
          second_previous_data_point = data_points[i - 2]
          step_size = (
              second_previous_data_point.commit_position -
              previous_data_point.commit_position)
          next_step_size = _NextHighestSquare(step_size)

          if (previous_data_point.commit_position - next_step_size <=
              commit_position):
            # Also restart the exponential lookback step size from 1 in case the
            # quadratic step size is too large and runs to or beyond the lower
            # bound of the regression range.
            next_step_size = 1

        next_commit_position = (
            previous_data_point.commit_position - next_step_size)
        return CommitID(
            commit_position=next_commit_position,
            revision=git.GetRevisionForCommitPositionByAnotherCommit(
                previous_data_point.git_hash,
                previous_data_point.commit_position,
                next_commit_position)), None
      else:
        # Stable/not reproducible.
        return None, None

    # Test is flaky at the current data point.
    flakes_in_a_row += 1

  # Further analysis is neeed.
  if flakes_in_a_row == 1:
    next_step_size = 1
  else:
    previous_data_point = data_points[-2]

    # Data points are assumed to be sorted in reverse order.
    assert (previous_data_point.commit_position >
            earliest_data_point.commit_position)

    # Exponential search using a quadraticially increasing step size.
    step_size = (
        previous_data_point.commit_position -
        earliest_data_point.commit_position)
    next_step_size = _NextHighestSquare(step_size)

  next_commit_position = earliest_data_point.commit_position - next_step_size

  return CommitID(
      commit_position=next_commit_position,
      revision=git.GetRevisionForCommitPositionByAnotherCommit(
          earliest_data_point.git_hash, earliest_data_point.commit_position,
          next_commit_position)), None


def _NextHighestSquare(n):
  """Takes an integer and returns the next highest square number.

  Args:
    n (int): Any integer.

  Returns:
    (int): The nearest square number larger than n. For example, input 1 returns
        4, input 4 returns 9, input 10 returns 16.
  """
  return int(math.pow(math.floor(math.sqrt(n) + 1), 2))


def BisectPoint(lower_bound, upper_bound):
  """Returns a bisection of two positive input numbers.

  Args:
    lower_bound (int): The lower of the two numbers.
    upper_bound (int): The higher of the two numbers.

  Returns:
    (int): The number half way in between lower_bound and upper_bound, with
        preference for the lower of the two as the result of treating the
        result of division as an int.
  """
  assert upper_bound >= 0
  assert lower_bound >= 0
  assert upper_bound >= lower_bound
  return lower_bound + (upper_bound - lower_bound) / 2


def GetNextCommitId(data_points, use_bisect, regression_range):
  """Determines the next point to analyze to be handled by the caller.

  Args:
    data_points ([DataPoint]): The list of data points to process and determine
        what the next commit position to run is and culprit if found.
    use_bisect (bool): Whether bisect should be attempted. Usually even if a
        regression range is available bisect may not be preferred in case the
        range is too wide to produce meaningful results. This flag allows the
        caller to determine whether it wants bisect to be performed or not.
    regression_range (CommitIDRange): The most up-to-date regression range
      available within the analysis.
  """
  if use_bisect:
    return _Bisect(regression_range)

  # Allow the algorithm to decide what to do.
  return _DetermineNextCommitPosition(data_points)
