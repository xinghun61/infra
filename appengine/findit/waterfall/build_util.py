# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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
from waterfall import buildbot


def DownloadBuildData(master_name, builder_name, build_number):
  """Downloads build data and returns a WfBuild instance."""
  build = WfBuild.Get(master_name, builder_name, build_number)
  if not build:
    build = WfBuild.Create(master_name, builder_name, build_number)

  if build.build_id:
    return build

  luci_project, luci_bucket = buildbot.GetLuciProjectAndBucketForMaster(
      master_name)
  bb_build = buildbucket_client.GetV2BuildByBuilderAndBuildNumber(
      luci_project, luci_bucket, builder_name, build_number)
  build.last_crawled_time = time_util.GetUTCNow()
  build.build_id = str(bb_build.id)
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
  if not build.build_id:
    return None

  bb_build = buildbucket_client.GetV2Build(
      build.build_id, fields=FieldMask(paths=['*']))
  build_info = buildbot.ExtractBuildInfoFromV2Build(master_name, builder_name,
                                                    build_number, bb_build)

  if not build.completed:
    build.start_time = build_info.build_start_time
    build.completed = build_info.completed
    build.result = build_info.result
    build.put()

  return build_info


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
        page_size=2,
        fields=FieldMask(paths=['builds.*.*']))

    if not search_builds_response.builds:
      # No more previous build.
      return

    previous_build = None
    # TODO(crbug.com/969124): remove the loop when SearchBuilds RPC works as
    # expected.
    for search_build in search_builds_response.builds:
      if search_build.id != end_build_id:
        previous_build = search_build
        break

    if not previous_build:
      logging.warning('No previous build found for build %d.', end_build_id)
      return

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
