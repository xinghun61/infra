# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Logic for all confidence score-related operations."""

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
  culprit_data_point = analysis.FindMatchingDataPointWithCommitPosition(
      culprit_commit_position)

  steppiness_confidence_score = confidence.SteppinessForCommitPosition(
      analysis.data_points, culprit_commit_position)

  # Heuristics for obvious cases.
  if previous_point:
    # Test doesn't exist means that the CL that added the test is the culprit.
    if pass_rate_util.TestDoesNotExist(previous_point.pass_rate):
      return 1.0

    # If the test goes from fully-stable for multiple data points to flaky, the
    # reuslt is likely to be correct. Set the confidence high enough to perform
    # an auto-action.
    elif (data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition(
        analysis.data_points, culprit_commit_position,
        flake_constants.REQUIRED_NUMBER_OF_STABLE_POINTS_BEFORE_CULPRIT) and
          not pass_rate_util.IsStableDefaultThresholds(
              culprit_data_point.pass_rate)):
      return max(steppiness_confidence_score,
                 flake_constants.DEFAULT_MINIMUM_CONFIDENCE_SCORE_TO_UPDATE_CR)

  # TODO(crbug.com/807947): Implement more heuristics for smarter confidence
  # score before falling back to steppiness.
  return steppiness_confidence_score
