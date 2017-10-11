# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import constants
from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from libs import time_util
from model.wf_build import WfBuild
from waterfall import buildbot

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
