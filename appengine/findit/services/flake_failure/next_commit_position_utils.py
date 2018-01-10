# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from waterfall import waterfall_config
from waterfall.flake import flake_constants


def GetEarliestCommitPosition(lower_bound, upper_bound):
  """Determines the earliest commit position to analyze.

  Args:
    lower_bound (int): The lowest commit position to analyze, or None if no
        pre-determined lower bound is specified.
    upper_bound (int): The highest commit position to analyze.

  Returns:
    (int): The lowest commit position to analyze.
  """
  assert upper_bound > lower_bound

  if lower_bound is not None:
    return lower_bound

  config_settings = waterfall_config.GetCheckFlakeSettings()
  max_commit_positions_to_look_back = config_settings.get(
      'max_commit_positions_to_look_back',
      flake_constants.DEFAULT_MAX_COMMIT_POSITIONS_TO_LOOK_BACK)

  return max(0, upper_bound - max_commit_positions_to_look_back)


def GetNextCommitPositionFromBuildRange(analysis, build_range,
                                        requested_commit_position):
  """Rounds a commit position to that of the nearest un-analyzed build's.

  Args:
    analysis (MasterFlakeAnalysis): The analysis whose data points to check.
    commit_position_range (IntRange): The commit positions of the later and
        earlier builds representing the range.
    requested_commit_position (int): The requested commit position to fall
        back to when rounding is not possible.

  Returns:
    (int): The commit position of either the upper bound build, lower bound
        build, or the originally-requested commit position itself.
  """
  assert (build_range.lower < requested_commit_position and
          requested_commit_position <= build_range.upper)

  if not analysis.FindMatchingDataPointWithCommitPosition(build_range.upper):
    # Try the later build first.
    return build_range.upper

  if not analysis.FindMatchingDataPointWithCommitPosition(build_range.lower):
    # Try the earlier build.
    return build_range.lower

  # Both the earlier and later builds have already been analyzed.
  # Use the requested commit position directly.
  return requested_commit_position
