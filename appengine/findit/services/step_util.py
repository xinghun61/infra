# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for logic about build test steps."""

import logging

from common.findit_http_client import FinditHttpClient
from services import swarming
from waterfall import build_util
from waterfall import buildbot


# TODO(crbug/804617): Modify this function to use new LUCI API when ready.
def _GetCandidateBounds(master_name, builder_name, upper_bound, lower_bound,
                        requested_commit_position):
  """ Bisects the build number range and search for the earliest build whose
      commit position >= requested_commit_position.

  This function is still based on the assumption that build numbers are
  consecutive. But because it asserts all results from GetBuildInfo, so
  the worst case is that it hits assertion error on missing builds and aborts
  analysis, and it should not happen often since the gaps between build
  numbers should be not too many.
  """
  while upper_bound - lower_bound > 1:
    candidate_build_number = (upper_bound - lower_bound) / 2 + lower_bound
    _, candidate_build = build_util.GetBuildInfo(master_name, builder_name,
                                                 candidate_build_number)
    assert candidate_build

    if candidate_build.commit_position == requested_commit_position:
      # Exact match.
      lower_bound = candidate_build_number - 1
      upper_bound = candidate_build_number
    elif candidate_build.commit_position > requested_commit_position:
      # Go left.
      upper_bound = candidate_build_number
    else:
      # Go right.
      lower_bound = candidate_build_number
  return upper_bound, lower_bound


def _GetLowerBoundBuildNumber(
    lower_bound_build_number,
    upper_bound_build_number,
    # The default window is the number of builds
    # Findit will look back for an analysis.
    default_build_number_window_size=500):
  """Determines the lowest bound build number relative to an upper bound.

  Args:
    lower_bound_build_number (int): An optional int to return directly.
    upper_bound_build)number (int): A non-optional int to use as a reference
        point.
    default_build_number_window_size (int): A fallback window to use to
        determine the lower bound.
  """
  if lower_bound_build_number is not None:
    return lower_bound_build_number

  if upper_bound_build_number > default_build_number_window_size:
    return upper_bound_build_number - default_build_number_window_size

  # For new builders, there may not be that many builds yet. This is a temporary
  # workaround and wil be replaced when the isolate index service is ready and
  # this function will no longer be necessary. 
  return upper_bound_build_number / 2


# TODO(crbug/804617): Modify this function to use new LUCI API when ready.
def GetValidBoundingBuildsForStep(
    master_name, builder_name, step_name, lower_bound_build_number,
    upper_bound_build_number, requested_commit_position):
  """Finds the two builds immediately before and after a commit position.

  TODO (lijeffrey): use case in regression_range_analysis_pipeline.py is not
  verified to be supported yet because that feature is not fully supported.

  The builds should also have useful artifacts for the step. Meaning:
  - The build completed without exception, or
  - The build completed the step without exception but exceptioned out later.

  Args:
    master_name (str): The name of the master.
    builder_name (str): The name of the builder.
    step_name (str): The name of the step.
    lower_bound_build_number (int): The earliest build number to search.
    upper_bound_build_number (int): The latest build number to search.
    requested_commit_position (int): The specified commit_position to find the
        bounding build numbers.

  Returns:
    (BuildInfo, Buildinfo): The two nearest builds that bound the requested
        commit position, with the first being earlier of the two. For example,
        if build_1 has commit position 100, build_2 has commit position 110,
        and 105 is requested, returns (build_1, build_2). Returns None for
        either or both of the builds if they cannot be determined. If the
        requested commit is before the lower bound, returns (None, BuildInfo).
        If the requested commit is after the upper bound, returns
        (BuildInfo, None). The calling code should check for the returned builds
        and decide what to do accordingly.
        If a given commit position is included in the blame list of either
        boundary build, that boundary build is returned as both the lower and
        upper bound build.
  """
  http_client = FinditHttpClient()

  logging.debug('GetBoundingBuildsForStep being called for %s/%s/%s with build '
                'number bounds (%d, %d) at commit position %d', master_name,
                builder_name, step_name, lower_bound_build_number or -1,
                upper_bound_build_number or -1, requested_commit_position)

  assert upper_bound_build_number is not None, 'upper_bound can\'t be None'

  _, latest_build_info = build_util.GetBuildInfo(master_name, builder_name,
                                                 upper_bound_build_number)
  logging.debug('latest_build_info: %r', latest_build_info)
  assert latest_build_info, 'Couldn\'t find build info for %s/%s/%s' % (
      master_name, builder_name, upper_bound_build_number)
  assert latest_build_info.commit_position is not None

  lower_bound_build_number = _GetLowerBoundBuildNumber(lower_bound_build_number,
                                                       upper_bound_build_number)
  logging.info('Found lower_bound_build_number to be %d.',
               lower_bound_build_number)

  _, earliest_build_info = build_util.GetBuildInfo(master_name, builder_name,
                                                   lower_bound_build_number)
  logging.debug('earliest_build_info: %r', earliest_build_info)
  assert earliest_build_info, 'Couldn\'t find build info for %s/%s/%s' % (
      master_name, builder_name, lower_bound_build_number)
  assert earliest_build_info.commit_position is not None
  assert (latest_build_info.commit_position >=
          earliest_build_info.commit_position)

  if requested_commit_position <= earliest_build_info.commit_position:
    if not swarming.CanFindSwarmingTaskFromBuildForAStep(
        http_client, master_name, builder_name, lower_bound_build_number,
        step_name):
      # TODO(crbug.com/831828): Support newly added test steps for this case.
      # Cannot find valid artifact in earliest_build for the step.
      return None, None
    if requested_commit_position == earliest_build_info.commit_position:
      return earliest_build_info, earliest_build_info
    else:
      return None, earliest_build_info

  if requested_commit_position >= latest_build_info.commit_position:
    if not swarming.CanFindSwarmingTaskFromBuildForAStep(
        http_client, master_name, builder_name, upper_bound_build_number,
        step_name):
      # Cannot find valid artifact in latest_build for the step.
      return None, None
    if latest_build_info.commit_position == requested_commit_position:
      return latest_build_info, latest_build_info
    else:
      return latest_build_info, None

  # Gets candidata builds.
  upper_bound, lower_bound = _GetCandidateBounds(
      master_name, builder_name, upper_bound_build_number,
      lower_bound_build_number, requested_commit_position)

  # Get valid builds.
  lower_bound_build = None
  upper_bound_build = None

  while lower_bound >= lower_bound_build_number:  # pragma: no branch
    _, lower_bound_build = build_util.GetBuildInfo(master_name, builder_name,
                                                   lower_bound)
    if lower_bound_build:
      if lower_bound_build.result != buildbot.EXCEPTION:
        break
      if swarming.CanFindSwarmingTaskFromBuildForAStep(
          http_client, master_name, builder_name, lower_bound, step_name):
        break
    lower_bound -= 1

  while upper_bound <= upper_bound_build_number:  # pragma: no branch
    _, upper_bound_build = build_util.GetBuildInfo(master_name, builder_name,
                                                   upper_bound)
    if upper_bound_build:
      if upper_bound_build.result != buildbot.EXCEPTION:
        break
      if swarming.CanFindSwarmingTaskFromBuildForAStep(
          http_client, master_name, builder_name, upper_bound, step_name):
        break
    upper_bound += 1

  assert lower_bound_build
  assert upper_bound_build

  return lower_bound_build, upper_bound_build
