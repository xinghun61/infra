# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Logic for all confidence score-related operations."""

from services.flake_failure import confidence
from services.flake_failure import flake_constants
from services.flake_failure import pass_rate_util


def CalculateCulpritConfidenceScore(analysis, culprit_commit_position):
  """Gets a confidence score for a suspected commit position.

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
  current_point = analysis.FindMatchingDataPointWithCommitPosition(
      culprit_commit_position)

  # Heuristics to avoid using stepiness for commit position.
  if previous_point:
    # Test doesn't exist means that the CL that added the test is the culprit.
    if pass_rate_util.TestDoesNotExist(previous_point.pass_rate):
      return 1.0
    # If the test goes from stable to flaky, the reuslt is likely to be correct
    # set the confidence high enough to send a notification.
    elif (
        pass_rate_util.IsStableDefaultThresholds(previous_point.pass_rate) and
        not pass_rate_util.IsStableDefaultThresholds(current_point.pass_rate)):
      return flake_constants.DEFAULT_MINIMUM_CONFIDENCE_SCORE_TO_UPDATE_CR

  # TODO(crbug.com/807947): Smarter confidence score besides steppiness.
  return confidence.SteppinessForCommitPosition(analysis.data_points,
                                                culprit_commit_position)
