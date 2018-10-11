# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common import constants
from gae_libs import appengine_util
from libs import analysis_status
from pipelines.flake_failure.analyze_recent_flakiness_pipeline import (
    AnalyzeRecentFlakinessInput)
from pipelines.flake_failure.analyze_recent_flakiness_pipeline import (
    AnalyzeRecentFlakinessPipeline)


def AnalyzeRecentCommitPosition(analysis_urlsafe_key):
  """Schedules an analysis of a recent commit for a MasterFlakeAnalysis.

  Args:
    analysis_urlsafe_key (str): The url-safe key to the analysis for which to
      analyze a recent commit position for.
  """
  analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
  assert analysis, 'Analysis missing unexpectedly!'

  analyze_recent_flakiness_input = AnalyzeRecentFlakinessInput(
      analysis_urlsafe_key=analysis_urlsafe_key)

  if (analysis.status in [analysis_status.RUNNING, analysis_status.PENDING] or
      analysis.analyze_recent_flakiness_status == analysis_status.RUNNING):
    # Bail out if the analysis is still in progress.
    return

  pipeline_job = AnalyzeRecentFlakinessPipeline(analyze_recent_flakiness_input)
  pipeline_job.target = appengine_util.GetTargetNameForModule(
      constants.WATERFALL_BACKEND)
  pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)

  analysis.Update(
      analyze_recent_flakiness_status=analysis_status.RUNNING,
      analyze_recent_flakiness_pipeline_status_path=(
          pipeline_job.pipeline_status_path))

  analysis.LogInfo(
      'An analysis of recent flakiness was scheduled with path {}'.format(
          pipeline_job.pipeline_status_path))
