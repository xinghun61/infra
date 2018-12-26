# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Logic for all confidence score-related operations."""

from libs.math import statistics
from services import math_util
from services.flake_failure import confidence
from services.flake_failure import flake_constants
from services.flake_failure import data_point_util
from services.flake_failure import pass_rate_util


def CalculateCulpritConfidenceScore(analysis, culprit_commit_position):
  """Gets a confidence score for a suspected commit position.

    Heuristics for confidence score:
    1. Newly-added tests always should return 1.0.
    2. Multiple (2+) 100% stable points --> flaky should be the max of
       steppiness or 0.7, whichever is greater.
    3. Fallback to steppiness in all other cases.

  Args:
    analysis (MasterFlakeAnalysis): The analysis to determine confidence for.
    culprit_commit_position (int): The suspected commit position that flakiness
      was determined to have started in. Can be None if not identified.

  Returns:
    Float between 0 and 1 representing confidence in the culprit commit
        position, or None if not found.
  """
  if culprit_commit_position is None:
    return None

  # If this build introduced a new flaky test, confidence should be 100%.
  previous_point = analysis.FindMatchingDataPointWithCommitPosition(
      culprit_commit_position - 1)

  assert previous_point, 'Data point preceding culprit unexpectedly missing!'

  culprit_data_point = analysis.FindMatchingDataPointWithCommitPosition(
      culprit_commit_position)

  assert culprit_data_point, (
      'Data point containing culprit unexpectedly missing!')

  steppiness_confidence_score = confidence.SteppinessForCommitPosition(
      analysis.data_points, culprit_commit_position)

  # Heuristics for obvious cases.

  # Test doesn't exist means that the CL that added the test is the culprit.
  if pass_rate_util.TestDoesNotExist(previous_point.pass_rate):
    return 1.0

  # For low-flakiness cases, calculate the pass rate confidence interval of the
  # stable point given the flaky point's estimated pass rate and compare it to
  # The flaky point's distribution range. If there is significant overlap,
  # The culprit is likely a false positive.
  stable_point_distribution_range = statistics.WilsonScoreConfidenceInterval(
      previous_point.pass_rate,
      previous_point.iterations,
      alpha=flake_constants.ALPHA)
  culprit_distribution_range = statistics.WilsonScoreConfidenceInterval(
      culprit_data_point.pass_rate,
      culprit_data_point.iterations,
      alpha=flake_constants.ALPHA)
  overlap = math_util.CalculateOverlapInIntervals(
      culprit_distribution_range, stable_point_distribution_range)

  if overlap > 0.0:
    # If there is any overlap at all in the confidence intervals of pass rates
    # the result is statistically likely to be a false positive. Assign a very
    # low confidence score. Note the value of |overlap| does not have any actual
    # statistical meaning, but is only used to assign a low value.
    analysis.LogInfo(
        ('Theoretical pass rates of stable and flaky points overlap. '
         'Steppiness score is %s') % steppiness_confidence_score)
    return min(1.0 - overlap, steppiness_confidence_score)

  # If there is no overlap in the likely true pass rates of the stable and flaky
  # points and the test goes from fully-stable for multiple data points to
  # flaky, the reuslt is likely to be correct. Set the confidence high enough to
  # perform an auto-action.
  if (data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition(
      analysis.data_points, culprit_commit_position,
      flake_constants.REQUIRED_NUMBER_OF_STABLE_POINTS_BEFORE_CULPRIT) and
      not pass_rate_util.IsStableDefaultThresholds(
          culprit_data_point.pass_rate)):
    return max(
        steppiness_confidence_score,
        flake_constants.DEFAULT_MINIMUM_CONFIDENCE_SCORE_TO_UPDATE_ENDPOINTS)

  # TODO(crbug.com/807947): Implement more heuristics for smarter confidence
  # score before falling back to steppiness.
  return steppiness_confidence_score
