# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for logic about build test steps."""

import logging

from common.constants import SUPPORTED_ISOLATED_SCRIPT_TESTS
from common.findit_http_client import FinditHttpClient
from libs.test_results.webkit_layout_test_results import WebkitLayoutTestResults
from model.isolated_target import IsolatedTarget
from services import constants
from services import swarming
from waterfall import build_util
from waterfall import buildbot
from waterfall import waterfall_config

_HTTP_CLIENT = FinditHttpClient()


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


def _GetLowerBoundBuild(master_name, builder_name, lower_bound_build_number,
                        upper_bound_build_number, step_name):
  """Gets a valid lower build near build_number."""
  # Search 10 below then 10 above for a valid build.
  return (GetValidBuild(
      master_name, builder_name, lower_bound_build_number, step_name, False,
      min(10, lower_bound_build_number)) or GetValidBuild(
          master_name, builder_name, lower_bound_build_number, step_name, True,
          min(10, upper_bound_build_number - lower_bound_build_number)))


def GetValidBuild(master_name, builder_name, requested_build_number, step_name,
                  search_ascending, maximum_search_distance):
  """Gets a valid bound at or near the requested build number.

    A build is considered valid if it exists, has a commit position, and has a
    swarming task available.

  Args:
    master_name (str): The name of the master to check.
    builder_name (str): The name of the builder to check.
    requested_build_number (int): The build number to get a valid build at or
        near.
    step_name (str): The name of the step.
    search_ascending (bool): Whether to return a build at least as high as the
        requested build number.
    maximum_search_distance (int): The maximum number of builds to check.

  Returns:
    (BuildInfo): A valid BuildInfo at or near requested_build_number, or None if
        not found.
  """
  candidate_build_number = requested_build_number
  increment = 0
  direction = 1 if search_ascending else -1

  while increment <= maximum_search_distance:
    candidate_build_number = requested_build_number + increment * direction

    _, candidate_build = build_util.GetBuildInfo(master_name, builder_name,
                                                 candidate_build_number)
    if (candidate_build and candidate_build.commit_position is not None and
        (candidate_build.result != buildbot.EXCEPTION or
         swarming.CanFindSwarmingTaskFromBuildForAStep(
             _HTTP_CLIENT, master_name, builder_name, candidate_build_number,
             step_name))):
      return candidate_build

    increment += 1

  logging.warning('Failed to find valid build for %s/%s/%s within %s builds',
                  master_name, builder_name, requested_build_number,
                  maximum_search_distance)
  return None


def GetBoundingIsolatedTargets(master_name, builder_name, target_name,
                               commit_position):
  """Determines the IsolatedTarget instances surrounding a commit position.

  Args:
    master_name (str): The name of the master to search by.
    builder_name (str): The name of the builder to search by.
    target_name (str): The name of the target to search by, e.g.
        'browser_tests'.
    commit_position (int): The desired commit position to find neighboring
        IsolatedTargets.

  Returns:
    (IsolatedTarget, IsolatedTarget): The lower and upper bound IsolatedTargets.
  """
  upper_bound_targets = (
      IsolatedTarget.FindIsolateAtOrAfterCommitPositionByMaster(
          master_name, builder_name, constants.GITILES_HOST,
          constants.GITILES_PROJECT, constants.GITILES_REF, target_name,
          commit_position))
  lower_bound_targets = (
      IsolatedTarget.FindIsolateBeforeCommitPositionByMaster(
          master_name, builder_name, constants.GITILES_HOST,
          constants.GITILES_PROJECT, constants.GITILES_REF, target_name,
          commit_position))

  assert upper_bound_targets, ((
      'Unable to detect isolated targets at for {}/{} with minimum commit '
      'position {}').format(master_name, builder_name, commit_position))

  assert lower_bound_targets, ((
      'Unable to detect isolated targets at for {}/{} below commit position'
      ' {}').format(master_name, builder_name, commit_position))

  return lower_bound_targets[0], upper_bound_targets[0]


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
  logging.debug(
      'GetBoundingBuildsForStep being called for %s/%s/%s with build '
      'number bounds (%d, %d) at commit position %d', master_name, builder_name,
      step_name, lower_bound_build_number or -1, upper_bound_build_number or -1,
      requested_commit_position)

  assert upper_bound_build_number is not None, 'upper_bound can\'t be None'

  _, latest_build_info = build_util.GetBuildInfo(master_name, builder_name,
                                                 upper_bound_build_number)
  logging.debug('latest_build_info: %r', latest_build_info)

  assert latest_build_info, 'Couldn\'t find build info for %s/%s/%s' % (
      master_name, builder_name, upper_bound_build_number)
  assert latest_build_info.commit_position is not None

  lower_bound_build_number = _GetLowerBoundBuildNumber(
      lower_bound_build_number, upper_bound_build_number)
  logging.info('Found lower_bound_build_number to be %d.',
               lower_bound_build_number)

  earliest_build_info = _GetLowerBoundBuild(master_name, builder_name,
                                            lower_bound_build_number,
                                            upper_bound_build_number, step_name)

  logging.debug('earliest_build_info: %r', earliest_build_info)
  assert earliest_build_info, 'Couldn\'t find build info for %s/%s/%s' % (
      master_name, builder_name, lower_bound_build_number)
  assert earliest_build_info.commit_position is not None
  assert (latest_build_info.commit_position >=
          earliest_build_info.commit_position)

  if requested_commit_position <= earliest_build_info.commit_position:
    if not swarming.CanFindSwarmingTaskFromBuildForAStep(
        _HTTP_CLIENT, master_name, builder_name, lower_bound_build_number,
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
        _HTTP_CLIENT, master_name, builder_name, upper_bound_build_number,
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

  # Get valid builds at or near the candidate build bounds.
  lower_bound_build = GetValidBuild(master_name, builder_name, lower_bound,
                                    step_name, False,
                                    lower_bound - lower_bound_build_number)

  upper_bound_build = GetValidBuild(master_name, builder_name, upper_bound,
                                    step_name, True,
                                    upper_bound_build_number - upper_bound)

  return lower_bound_build, upper_bound_build


def IsStepSupportedByFindit(test_result_object, step_name, master_name):
  """Checks if a test step is currently supported by Findit.

  Currently Findit supports all gtest test steps;
  for isolated-script-tests, Findit only supports webkit_layout_tests.

  * If there isn't a parser for the test_result of the step, it's not supported;
  * If the step is an isolated-script-test step but not webkit_layout_tests,
    it's not supported.
  * If the step is set to unsupported in config, it's not supported.
  """
  if not test_result_object:
    return False

  if not waterfall_config.StepIsSupportedForMaster(step_name, master_name):
    return False

  # TODO(crbug/836317): remove the special check for step_name when Findit
  # supports all isolated_script_tests.
  if (isinstance(test_result_object, WebkitLayoutTestResults) and
      step_name not in SUPPORTED_ISOLATED_SCRIPT_TESTS):
    return False
  return True
