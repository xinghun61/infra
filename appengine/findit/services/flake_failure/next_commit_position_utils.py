# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from services.flake_failure import flake_constants
from services.flake_failure import pass_rate_util
from waterfall import waterfall_config


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
  upper = build_range.upper
  lower = build_range.lower

  assert (lower <= requested_commit_position and
          requested_commit_position <= upper), (
              '{} is not within range of {} and {}'.format(
                  requested_commit_position, lower, upper))

  # If the upper commit position has already been analyzed but not the lower,
  # return lower. This case occurs when exponential search is early on and a
  # requested commit is still close by.
  if (analysis.FindMatchingDataPointWithCommitPosition(upper) and
      not analysis.FindMatchingDataPointWithCommitPosition(lower)):
    return lower

  # If the lower commit position has already been analyzed but not the upper,
  # return upper. This case occurs when the analysis has already identified a
  # stable point.
  if (analysis.FindMatchingDataPointWithCommitPosition(lower) and
      not analysis.FindMatchingDataPointWithCommitPosition(upper)):
    return upper

  # Neither data point has been analyzed, so use whichever is closer. This case
  # occurs during exponential search back when no stable point has been found
  # yet.
  if ((upper - requested_commit_position) <=
      (requested_commit_position - lower) and
      not analysis.FindMatchingDataPointWithCommitPosition(upper)):
    # The upper bound commit position is closer and unanalyzed.
    return upper

  if not analysis.FindMatchingDataPointWithCommitPosition(lower):
    # The lower bound commit position is closer and unanalyzed.
    return lower

  # Both the upper and lower bound commits have already been analyzed.
  # Use the requested commit position directly.
  return requested_commit_position


def GetNextCommitPositionFromHeuristicResults(analysis_urlsafe_key):
  """Returns a commit position based on heuristic results.

    Checks an analysis for suspect_urlsafe_keys, which each correspond to a
    commit position. This function will consider both these commit positions
    and their 1-previous positions, depending on what has already been run and
    whether or not they are already flaky. Each suspect_urlsafe_key is expected
    to be in chronological order.

  Args:
    analysis_urlsafe_key (str): The url-safe key to a MasterFlakeAnalsyis.

  Returns:
    (int): A suggested commit position based on heuristic results, or None if
        not applicable.
  """
  analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
  assert analysis

  suspect_urlsafe_keys = analysis.suspect_urlsafe_keys

  if not suspect_urlsafe_keys:
    # No heuristic results.
    return None

  # Suspects are expected to be in chronological order.
  for suspect_urlsafe_key in suspect_urlsafe_keys:
    # Go through each suspect to see if they have already been analyzed.
    # For each suspect, check the previous commit position prior to it to verify
    # it is stable, and the suspect itself to verify it is flaky.
    suspect = ndb.Key(urlsafe=suspect_urlsafe_key).get()
    assert suspect
    assert suspect.commit_position is not None

    previous_commit_position_data_point = (
        analysis.FindMatchingDataPointWithCommitPosition(
            suspect.commit_position - 1))

    if not previous_commit_position_data_point:
      # Return the commit position right before the suspect, for the caller to
      # verify is stable.
      return suspect.commit_position - 1

    if not pass_rate_util.IsStableDefaultThresholds(
        previous_commit_position_data_point.pass_rate):
      # The test is already confirmed to be flaky before any of the heuristic
      # results.
      return None

    suspected_data_point = analysis.FindMatchingDataPointWithCommitPosition(
        suspect.commit_position)

    # Suspect is not yet run. Return it next.
    if suspected_data_point is None:
      return suspect.commit_position

  # Heuristic results and their 1-previous commit positions have all been run.
  return None
