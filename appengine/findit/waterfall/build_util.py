# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import BuilderID
from google.protobuf.field_mask_pb2 import FieldMask

from common import constants
from common.findit_http_client import FinditHttpClient
from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from infra_api_clients import crrev
from libs import time_util
from model.isolated_target import IsolatedTarget
from model.wf_build import WfBuild
from services import constants as services_constants
from services import git
from services import swarming
from waterfall import buildbot

HTTP_CLIENT_NO_404_ERROR = FinditHttpClient(no_error_logging_statuses=[404])


def _BuildDataNeedUpdating(build):
  return (not build.build_id or (
      not build.completed and
      (time_util.GetUTCNow() - build.last_crawled_time).total_seconds() >= 300))


def _GetBuildIDForLUCIBuild(build_data):
  """Gets build_id for a LUCI build.

  For a LUCI build, we can get buildbucket_id of the build from buildbucket
  property.

  Each property would look like a list like:
    [property_name, property_content, annotation]
  """
  if not build_data:
    return None

  data_json = json.loads(build_data)
  properties = data_json.get('properties') or []
  for property_item in properties:
    if property_item[0] == 'buildbucket':  #pragma: no branch.
      buildbucket = property_item[1]
      return buildbucket.get('build', {}).get('id')

  return None


# TODO (crbug/902137): remove this logic after all builders are migrated to
# LUCI.
def _GetLogLocationForBuildbotBuild(build_data):
  """Gets log location for a buildbot build.

  For a buildbot build, we can get log location directly from log_location
  property.

  Each property would look like a list like:
    [property_name, property_content, annotation]
  """
  if not build_data:
    return None

  data_json = json.loads(build_data)
  properties = data_json.get('properties') or []
  for property_item in properties:
    if property_item[0] == 'log_location':
      return property_item[1]

  return None


def DownloadBuildData(master_name, builder_name, build_number):
  """Downloads build data and returns a WfBuild instance."""
  build = WfBuild.Get(master_name, builder_name, build_number)
  if not build:
    build = WfBuild.Create(master_name, builder_name, build_number)

  status_code = None
  build_updated = False
  # Cache the data to avoid pulling from master again.
  if _BuildDataNeedUpdating(build):
    # Retrieve build data from milo.
    status_code, build.data = buildbot.GetBuildDataFromMilo(
        master_name, builder_name, build_number, HTTP_CLIENT_NO_404_ERROR)
    build.last_crawled_time = time_util.GetUTCNow()
    build_updated = True

  if build.data:
    original_build_id = build.build_id
    original_log_location = build.log_location
    build.build_id = build.build_id or _GetBuildIDForLUCIBuild(build.data)
    if not build.build_id:
      build.log_location = (
          build.log_location or _GetLogLocationForBuildbotBuild(build.data))
    build_updated = (
        original_build_id != build.build_id or
        original_log_location != build.log_location)

  if build_updated:
    build.put()

  return status_code, build


def GetBuildInfo(master_name, builder_name, build_number):
  """Gets build info given a master, builder, and build number.

  Args:
    master_name (str): The name of the master.
    builder_name (str): The name of the builder.
    build_number (int): The build number.

  Returns:
    Build information as an instance of BuildInfo.
  """
  status_code, build = DownloadBuildData(master_name, builder_name,
                                         build_number)
  if not build.build_id:
    return status_code, None

  bb_build = buildbucket_client.GetV2Build(build.build_id)
  build_info = buildbot.ExtractBuildInfoFromV2Build(master_name, builder_name,
                                                    build_number, bb_build)

  if not build.completed:
    build.start_time = build_info.build_start_time
    build.completed = build_info.completed
    build.result = build_info.result
    build.put()

  return status_code, build_info


def GetFailureType(build_info):
  if not build_info.failed_steps:
    return failure_type.UNKNOWN
  # TODO(robertocn): Consider also bailing out of tests with infra failures.
  if constants.COMPILE_STEP_NAME in build_info.failed_steps:
    if build_info.result == common_pb2.INFRA_FAILURE:
      return failure_type.INFRA
    return failure_type.COMPILE
  # TODO(http://crbug.com/602733): differentiate test steps from infra ones.
  return failure_type.TEST


def GetLatestBuildNumber(master_name, builder_name):
  """Attempts to get the latest build number on master_name/builder_name."""
  recent_builds = buildbot.GetRecentCompletedBuilds(
      master_name, builder_name, page_size=1)

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


def GetLatestCommitPositionAndRevision(master_name, builder_name, target_name):
  """Gets the latest commit position and revision for a configuration.

  Args:
    master_name (str): The name of the master to query.
    builder_name (str): The name of the builder to query.
    target_name (str): The desired target name.

  Returns:
    (int, str): The latest commit position known and its corresponding revision.
  
  """
  latest_targets = (
      IsolatedTarget.FindLatestIsolateByMaster(
          master_name, builder_name, services_constants.GITILES_HOST,
          services_constants.GITILES_PROJECT, services_constants.GITILES_REF,
          target_name))

  if latest_targets:
    commit_position = latest_targets[0].commit_position
    revision = latest_targets[0].revision
    if not revision:
      # Historical data doesn't have revision.
      commit_info = crrev.RedirectByCommitPosition(FinditHttpClient(),
                                                   commit_position)
      assert commit_info is not None, 'No info: r%d' % commit_position
      revision = commit_info['git_sha']

    return commit_position, revision

  # Fallback to buildbot for builds not yet migrated to LUCI.
  # TODO (crbug.com/804617): Remove fallback logic after migration is complete.
  luci_project, luci_bucket = buildbot.GetLuciProjectAndBucketForMaster(
      master_name)
  search_builds_response = buildbucket_client.SearchV2BuildsOnBuilder(
      BuilderID(project=luci_project, bucket=luci_bucket, builder=builder_name),
      page_size=1)

  if not search_builds_response:
    # Something is wrong. Calling code should be responsible for checking for
    # the return value.
    return None, None

  latest_build = search_builds_response.builds[0]
  revision = latest_build.input.gitiles_commit.id
  repo_url = git.GetRepoUrlFromV2Build(latest_build)
  return git.GetCommitPositionFromRevision(
      latest_build.input.gitiles_commit.id, repo_url=repo_url), revision


# TODO(crbug/821865): Remove this after new flake pipelines are stable.
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
    (int) Valid nearby build if any, else None.
  """
  builds_to_look_at = [build_number]
  for x in range(1, search_distance + 1):
    builds_to_look_at.append(build_number + x)
    builds_to_look_at.append(build_number - x)

  logging.info('Examining build numbers %r for a valid build',
               builds_to_look_at)

  http_client = FinditHttpClient()
  for build in builds_to_look_at:
    if exclude_list and build in exclude_list:
      continue
    if swarming.CanFindSwarmingTaskFromBuildForAStep(
        http_client, master_name, builder_name, build, step_name):
      return build

  return None


def IteratePreviousBuildsFrom(master_name, builder_name, build_id, entry_limit):
  luci_project, luci_bucket = buildbot.GetLuciProjectAndBucketForMaster(
      master_name)
  builder = BuilderID(
      project=luci_project, bucket=luci_bucket, builder=builder_name)

  entry_number = 0
  # End_build_id in build_range when query the previous build.
  end_build_id = build_id
  while entry_number <= entry_limit:  # pragma: no branch.
    search_builds_response = buildbucket_client.SearchV2BuildsOnBuilder(
        builder,
        build_range=(None, end_build_id),
        page_size=1,
        fields=FieldMask(paths=['builds.*.*']))

    if not search_builds_response.builds:
      # No more previous build.
      return

    previous_build = search_builds_response.builds[0]
    end_build_id = previous_build.id
    entry_number += 1
    yield previous_build


def GetBuilderInfoForLUCIBuild(build_id):
  """Gets a build's project and bucket info.

  Args:
    build_id(str): Buildbucket id of a LUCI build.
  """
  build_proto = buildbucket_client.GetV2Build(
      build_id, fields=FieldMask(paths=['builder']))
  if not build_proto:
    logging.exception('Error retrieving buildbucket build id: %s', build_id)
    return None, None

  return build_proto.builder.project, build_proto.builder.bucket
