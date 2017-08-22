# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pickle

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from waterfall.flake import flake_analysis_service
from waterfall.flake import triggering_sources


class ProcessFlakeAnalysisRequest(BaseHandler):
  """Processes request of flake analysis and triggers the analysis on demand."""

  PERMISSION_LEVEL = Permission.APP_SELF

  def HandlePost(self):
    flake_analysis_request, user_email, is_admin = pickle.loads(
        self.request.body)

    flake_analysis_service.ScheduleAnalysisForFlake(
        flake_analysis_request, user_email, is_admin,
        triggering_sources.FINDIT_API)
