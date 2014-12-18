# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from base_handler import BaseHandler
from base_handler import Permission
from waterfall import buildbot
from waterfall import build_failure_analysis_pipelines


BUILD_FAILURE_ANALYSIS_TASKQUEUE = 'build-failure-analysis-queue'


class BuildFailure(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Trigger analysis of a build failure on demand and return current result.

    If the final analysis result is available, set cache-control to 1 day to
    avoid overload by unnecessary and frequent query from clients; otherwise
    set cache-control to 5 seconds to allow repeated query.

    Serve HTML page or JSON result as requested.
    """
    url = self.request.get('url', '').strip()
    build_info = buildbot.ParseBuildUrl(url)
    if not build_info:
      return BaseHandler.CreateError(
          'Url "%s" is not pointing to a build.' % url, 501)
    master_name, builder_name, build_number = build_info

    force = self.request.get('force') == '1'
    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, force,
        BUILD_FAILURE_ANALYSIS_TASKQUEUE)

    # TODO: return info of the build analysis.
    return None

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
