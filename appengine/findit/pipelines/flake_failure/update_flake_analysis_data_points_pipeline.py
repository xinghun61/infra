# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Updates a flake analysis' data points with incoming pass rate information."""

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from dto.flakiness import Flakiness
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import pipeline
from libs.structured_object import StructuredObject
from services import constants
from services.flake_failure import data_point_util
from services.flake_failure import flakiness_util
from services.flake_failure import run_swarming_util


class UpdateFlakeAnalysisDataPointsInput(StructuredObject):
  # The urlsafe-key to the analysis to update.
  analysis_urlsafe_key = basestring

  # The flakiness rate with which to create a data point with.
  flakiness = Flakiness


class UpdateFlakeAnalysisDataPointsPipeline(GeneratorPipeline):
  """Updates a MasterFlakeAnalysis' data points with swarming task results."""

  input_type = UpdateFlakeAnalysisDataPointsInput

  def RunImpl(self, parameters):
    """Appends a DataPoint to a MasterFlakeAnalysis."""
    analysis_urlsafe_key = parameters.analysis_urlsafe_key
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis, 'Analysis unexpectedly missing'

    flakiness = parameters.flakiness

    if flakiness_util.MaximumSwarmingTaskRetriesReached(flakiness):
      run_swarming_util.ReportSwarmingTaskError(analysis, flakiness.error)
      analysis.LogError(
          'Swarming task ended in error after {} failed attempts. Giving '
          'up'.format(flakiness.failed_swarming_task_attempts))
      raise pipeline.Abort()

    git_repo = CachedGitilesRepository(FinditHttpClient(),
                                       constants.CHROMIUM_GIT_REPOSITORY_URL)
    change_log = git_repo.GetChangeLog(flakiness.revision)
    data_point = data_point_util.ConvertFlakinessToDataPoint(flakiness)
    data_point.commit_position_landed_time = change_log.committer.time
    analysis.data_points.append(data_point)
    analysis.put()
