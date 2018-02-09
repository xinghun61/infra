# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Logic for all confidence score-related operations."""

from services.flake_failure import pass_rate_util
from waterfall.flake import confidence


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

  if (previous_point and
      pass_rate_util.TestDoesNotExist(previous_point.pass_rate)):
    return 1.0

  # TODO(crbug.com/807947): Smarter confidence score besides steppiness.
  return confidence.SteppinessForCommitPosition(analysis.data_points,
                                                culprit_commit_position)
