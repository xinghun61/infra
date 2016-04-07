# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from base_handler import BaseHandler
from base_handler import Permission
from common import constants
from common.http_client_appengine import HttpClientAppengine
from waterfall import buildbot
from waterfall import build_failure_analysis_pipelines
from waterfall import build_util


def _TriggerNewAnalysesOnDemand(builds):
  for build in builds:
    master_name = build['master_name']
    builder_name = build['builder_name']
    build_number = build['build_number']
    failed_steps = build.get('failed_steps')

    # TODO(stgao): make builder_alerts send information of whether a build
    # is completed.
    build = build_util.DownloadBuildData(
        master_name, builder_name, build_number)
    if not build or not build.data:
      continue  # Skip the build, wait for next request to recheck.

    build_info = buildbot.ExtractBuildInfo(
        master_name, builder_name, build_number, build.data)

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, failed_steps=failed_steps,
        build_completed=build_info.completed,
        force=False, queue_name=constants.WATERFALL_ANALYSIS_QUEUE)


class TriggerAnalyses(BaseHandler):
  """Triggers new analyses on demand.

  This handler checks the build failures in the request, and triggers new
  analyes for a build in two situations:
  1. A new step failed.
  2. The build became completed after last analysis. This will potentially
     trigger a try-job run.
  """

  PERMISSION_LEVEL = Permission.ADMIN

  def HandlePost(self):
    builds = json.loads(self.request.body).get('builds', [])
    _TriggerNewAnalysesOnDemand(builds)
