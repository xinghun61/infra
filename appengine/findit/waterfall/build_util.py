# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from common import constants
from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from libs import time_util
from model.wf_build import WfBuild
from waterfall import buildbot
from waterfall import swarming_util

HTTP_CLIENT_LOGGING_ERRORS = FinditHttpClient()
HTTP_CLIENT_NO_404_ERROR = FinditHttpClient(no_error_logging_statuses=[404])


def _BuildDataNeedUpdating(build):
  return (not build.data or (
      not build.completed and
      (time_util.GetUTCNow() - build.last_crawled_time).total_seconds() >= 300))


def DownloadBuildData(master_name, builder_name, build_number):
  """Downloads build data and returns a WfBuild instance."""
  build = WfBuild.Get(master_name, builder_name, build_number)
  if not build:
    build = WfBuild.Create(master_name, builder_name, build_number)

  # Cache the data to avoid pulling from master again.
  if _BuildDataNeedUpdating(build):
    # Retrieve build data from milo.
    build.data = buildbot.GetBuildDataFromMilo(
        master_name, builder_name, build_number, HTTP_CLIENT_LOGGING_ERRORS)
    build.last_crawled_time = time_util.GetUTCNow()
    build.put()

  return build


def GetBuildInfo(master_name, builder_name, build_number):
  """Gets build info given a master, builder, and build number.

  Args:
    master_name (str): The name of the master.
    builder_name (str): The name of the builder.
    build_number (int): The build number.

  Returns:
    Build information as an instance of BuildInfo.
  """
  build = DownloadBuildData(master_name, builder_name, build_number)

  if not build.data:
    return None

  return buildbot.ExtractBuildInfo(master_name, builder_name, build_number,
                                   build.data)


def GetBuildEndTime(master_name, builder_name, build_number):
  build = DownloadBuildData(master_name, builder_name, build_number)
  build_info = buildbot.ExtractBuildInfo(master_name, builder_name,
                                         build_number, build.data)
  return build_info.build_end_time


def CreateBuildId(master_name, builder_name, build_number):
  return '%s/%s/%s' % (master_name, builder_name, build_number)


def GetBuildInfoFromId(build_id):
  return build_id.split('/')


def GetFailureType(build_info):
  if not build_info.failed_steps:
    return failure_type.UNKNOWN
  # TODO(robertocn): Consider also bailing out of tests with infra failures.
  if constants.COMPILE_STEP_NAME in build_info.failed_steps:
    if build_info.result == buildbot.EXCEPTION:
      return failure_type.INFRA
    return failure_type.COMPILE
  # TODO(http://crbug.com/602733): differentiate test steps from infra ones.
  return failure_type.TEST


def GetLatestBuildNumber(master_name, builder_name):
  """Attempts to get the latest build number on master_name/builder_name."""
  recent_builds = buildbot.GetRecentCompletedBuilds(master_name, builder_name,
                                                    FinditHttpClient())

  if recent_builds is None:
    # Likely a network error.
    logging.error('Failed to detect latest build number on %s, %s', master_name,
                  builder_name)
    return None

  if not recent_builds:
    # In case the builder is new or was recently reset.
    logging.warning('No recent builds found on %s %s', master_name,
                    builder_name)
    return None

  return recent_builds[0]


def GetEarliestContainingBuild(
    master_name, builder_name, lower_bound_build_number,
    upper_bound_build_number, requested_commit_position):
  """Finds the earliest build that contains the requested commit position.

    The lower/upper bounds represent a build number range to search. The upper
    bound build number must have a commit position greater than the requested
    commit in order to contain it, while the lower bound build number's commit
    position must be smaller than the requested commit position. For example,
    If the requested commit position is 200 and build numbers 1 and 3 are passed
    in as the lower/upper bounds, then build 1's commit position must be under
    200 and build 3's commit position must be at least 200.

  Args:
    master_name (str): The name of the master.
    builder_name (str): The name of the builder.
    lower_bound_build_number (int): The earliest build number to search.
    upper_bound_build_number (int): The latest build number to search.
    requested_commit_position (int): The specified commit_position to find the
        containing build number.

  Returns:
    (BuildInfo): The earliest build that contains the requested commit position,
        or None if not determined due to unexpected errors.
  """
  if lower_bound_build_number is None:
    lower_bound_build_number = 0
    earliest_build_info = GetBuildInfo(master_name, builder_name,
                                       lower_bound_build_number)
    if requested_commit_position <= earliest_build_info.commit_position:
      # The requested commit position is before the earliest available build.
      # Fallback to the earliest build. The calling code should compare the
      # requested commit position to what is returned here and raise an alert
      # accordingly.
      return earliest_build_info

  if upper_bound_build_number is None:
    upper_bound_build_number = GetLatestBuildNumber(master_name, builder_name)

    if upper_bound_build_number is None:
      logging.error('Failed to detect latest build number')
      return None

    latest_build_info = GetBuildInfo(master_name, builder_name,
                                     upper_bound_build_number)
    if requested_commit_position >= latest_build_info.commit_position:
      # If the requested commit is beyond what has actually been committed.
      # Fallback to the latest build. The calling code should compare the
      # requested commit position to what is returned here and raise an alert
      # accordingly.
      return latest_build_info

  # Bisect the build number range and search for the earliest build whose
  # commit position >= requested_commit_position.
  upper_bound = upper_bound_build_number
  lower_bound = lower_bound_build_number

  while upper_bound - lower_bound > 1:
    candidate_build_number = (upper_bound - lower_bound) / 2 + lower_bound
    candidate_build = GetBuildInfo(master_name, builder_name,
                                   candidate_build_number)

    if candidate_build.commit_position == requested_commit_position:
      # Exact match.
      return candidate_build
    if candidate_build.commit_position > requested_commit_position:
      # Go left.
      upper_bound = candidate_build_number
    else:
      # Go right.
      lower_bound = candidate_build_number

  return GetBuildInfo(master_name, builder_name, upper_bound)


def FindValidBuildNumberForStepNearby(master_name,
                                      builder_name,
                                      step_name,
                                      build_number,
                                      exclude_list=None,
                                      search_distance=3):
  """Finds a valid nearby build number for a step.

  Looks around the given build number for builds that have a reference task
  on swarming. We use this reference swarming task to create a task request,
  and it's required to run the test. If no reference swarming task can be
  found, it's likely that the build failed and the artifact doesn't exist.

  Args:
    master_name (str): Name of the master for this test.
    builder_name (str): Name of the builder for this test.
    step_name (str): Name of the builder for this test.
    build_number (int): Build number to look around.
    exclude_list (lst): Build numbers to exclude from the search.
    search_distance (int): Distance to search on either side of the build.

  Returns:
    (int) Valid nearby build if any, else None."""
  builds_to_look_at = [build_number]
  for x in range(1, search_distance + 1):
    builds_to_look_at.append(build_number + x)
    builds_to_look_at.append(build_number - x)

  http_client = FinditHttpClient()
  for build in builds_to_look_at:
    if exclude_list and build in exclude_list:
      continue
    swarming_task_items = swarming_util.ListSwarmingTasksDataByTags(
        master_name, builder_name, build, http_client, {'stepname': step_name})
    if swarming_task_items:
      return build

  return None