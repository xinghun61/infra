# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs import time_util
from model.wf_build import WfBuild
from waterfall import buildbot
from waterfall import lock_util
from waterfall import waterfall_config

HTTP_CLIENT_LOGGING_ERRORS = HttpClientAppengine()
HTTP_CLIENT_NO_404_ERROR = HttpClientAppengine(no_error_logging_statuses=[404])
CHROME_BUILD_EXTRACT = 'CBE'
BUILDBOT_MASTER = 'BM'


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
    use_cbe = waterfall_config.GetDownloadBuildDataSettings().get(
        'use_chrome_build_extract')

    if use_cbe:
      # Retrieve build data from build archive first.
      build.data = buildbot.GetBuildDataFromArchive(
          master_name, builder_name, build_number, HTTP_CLIENT_NO_404_ERROR)

      if build.data:
        build.data_source = CHROME_BUILD_EXTRACT
      elif not lock_util.WaitUntilDownloadAllowed(
          master_name):  # pragma: no cover
        return None

    if not build.data or not use_cbe:
      # Retrieve build data from build master.
      build.data = buildbot.GetBuildDataFromBuildMaster(
          master_name, builder_name, build_number, HTTP_CLIENT_LOGGING_ERRORS)
      build.data_source = BUILDBOT_MASTER

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
