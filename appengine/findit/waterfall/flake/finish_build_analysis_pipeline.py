# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.pipelines import pipeline
from gae_libs.pipeline_wrapper import BasePipeline

from libs import analysis_status
from libs import time_util

from common import monitoring

from model import result_status

from services.flake_failure import heuristic_analysis

from waterfall import extractor_util
from waterfall.flake import confidence
from waterfall.flake import flake_analysis_util
from waterfall.flake import flake_constants
from waterfall.flake import lookback_algorithm
from waterfall.flake.initialize_flake_try_job_pipeline import (
    InitializeFlakeTryJobPipeline)
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline


def _UpdateAnalysisResults(analysis,
                           suspected_build,
                           status,
                           error,
                           build_confidence_score=None):
  """Sets an analysis' fields upon cessation of an analysis.

  Args:
    analysis (MasterFlakeAnalysis): The analysis to update.
    suspected_build (int): The build number that the flakiness is suspected to
        have begun in. None if not found.
    status (int): The analysis status to set to.
    error (dict): Any detected errors during the analysis, or None.
    build_confidence_score (float): The confidence score associated with the
        suspected build. Can be None if no suspected build was identified.
    user_specified_range (bool): Whether the user supplied a rerun of a specific
        range, which will force try jobs to start regardless of confidence.
  """
  analysis.status = status

  if (suspected_build is not None and
      suspected_build != analysis.suspected_flake_build_number):
    # In case the user specified a region to analyze, only update the suspected
    # build if one was found within the user's range and it is different from
    # what Findit had originally found.
    analysis.confidence_in_suspected_build = build_confidence_score
    analysis.suspected_flake_build_number = suspected_build

  analysis.try_job_status = analysis.try_job_status or analysis_status.SKIPPED

  analysis.result_status = (result_status.NOT_FOUND_UNTRIAGED
                            if suspected_build is None else
                            result_status.FOUND_UNTRIAGED)

  if error:
    analysis.end_time = time_util.GetUTCNow()
    analysis.error = error
    duration = analysis.end_time - analysis.start_time
    monitoring.analysis_durations.add(duration.total_seconds(), {
        'type': 'flake',
        'result': 'error',
    })
  else:
    # Clear info about the last attempted swarming task since it will be stored
    # in the data point.
    analysis.last_attempted_swarming_task_id = None
    analysis.last_attempted_build_number = None

  analysis.put()


def _GetBuildConfidenceScore(analysis, suspected_build, data_points):
  """Gets a confidence score for a suspected build.

  Args:
    analysis (MasterFlakeAnalysis): The analysis itself.
    suspected_build (int): The suspected build number that flakiness started in.
        Can be None if not identified.
    data_points (list): A list of DataPoint() entities to calculate stepinness
        and determine a confidence score.

  Returns:
    Float between 0 and 1 representing confidence in the suspected build number
        or None if not found.
  """
  if suspected_build is None:
    return None

  # If this build introduced a new flaky test, confidence should be 100%.
  previous_point = analysis.FindMatchingDataPointWithBuildNumber(
      suspected_build - 1)
  if (previous_point and
      previous_point.pass_rate == flake_constants.PASS_RATE_TEST_NOT_FOUND):
    return 1.0

  return confidence.SteppinessForBuild(data_points, suspected_build)


def _UserSpecifiedRange(lower_bound_build_number, upper_bound_build_number):
  """Determines whether or not try jobs should be run based on user input.

  Args:
    lower_bound_build_number (int): The lower-bound build number corresponding
        to a user-specified commit position, or None if part of an automatic
        analysis.
    upper_bound_build_number (int): The upper-bound build number corresponding
        to a user-specified commit position, or None if part of an automatic
        analysis.

  Returns:
    Bool whether or not a user specified a range. Used to force try jobs to run
        regardless of confidence.
  """
  return (lower_bound_build_number is not None and
          upper_bound_build_number is not None)


def _IdentifySuspectedRevisions(analysis, http_client):
  suspected_data_point = analysis.GetDataPointOfSuspectedBuild()
  assert suspected_data_point

  test_location = heuristic_analysis.GetTestLocation(
      suspected_data_point.GetSwarmingTaskId(), analysis.test_name, http_client)

  normalized_file_path = extractor_util.NormalizeFilePath(test_location.file)

  git_repo = CachedGitilesRepository(
      http_client, flake_constants.CHROMIUM_GIT_REPOSITORY_URL)

  git_blame = git_repo.GetBlame(normalized_file_path,
                                suspected_data_point.git_hash)

  return heuristic_analysis.GetSuspectedRevisions(
      git_blame, suspected_data_point.blame_list)


class FinishBuildAnalysisPipeline(BasePipeline):
  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, analysis_urlsafe_key, lower_bound_build_number,
          upper_bound_build_number, user_specified_iterations, force):
    """Finish the build-level analysis.

      Calculate the confidence, update the information and start
      the try job pipeline.

      Args:
        analysis_urlsafe_key (MasterFlakeAnalysis): Key to look up the current
            analysis.
        lower_bound_build_number (int): The earliest build number to check. Pass
            None to allow the look back algorithm to determine how far back to
            look.
        upper_bound_build_number (int): The latest build number to include
            in the analysis. Pass None to allow the algorithm to determine
            where to start the backward search from.
        user_specified_iterations (int): The number of iterations to rerun the
            test as specified by the user. If None, Findit will fallback to what
            is in the analysis' algorithm parameters.
        force (bool): Force this build to run from scratch,
          a rerun by an admin will trigger this.
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    analysis.LogInfo('Regression range analysis completed')
    data_points_within_range = analysis.GetDataPointsWithinBuildNumberRange(
        lower_bound_build_number, upper_bound_build_number)
    data_points = flake_analysis_util.NormalizeDataPointsByBuildNumber(
        data_points_within_range)

    _, suspected_build = lookback_algorithm.GetNextRunPointNumber(
        data_points, analysis.algorithm_parameters.get('swarming_rerun'))
    build_confidence_score = _GetBuildConfidenceScore(analysis, suspected_build,
                                                      data_points_within_range)

    user_specified_range = _UserSpecifiedRange(lower_bound_build_number,
                                               upper_bound_build_number)
    _UpdateAnalysisResults(
        analysis,
        suspected_build,
        analysis_status.COMPLETED,
        None,
        build_confidence_score=build_confidence_score)

    suspected_data_point = analysis.GetDataPointOfSuspectedBuild()
    assert suspected_data_point

    # Run heuristic analysis before triggering try jobs.
    http_client = FinditHttpClient()
    suspected_revisions = _IdentifySuspectedRevisions(analysis, http_client)

    heuristic_analysis.SaveFlakeCulpritsForSuspectedRevisions(
        http_client, analysis_urlsafe_key, suspected_revisions)

    suspected_ranges = heuristic_analysis.GenerateSuspectedRanges(
        suspected_revisions, analysis.GetDataPointOfSuspectedBuild().blame_list)

    analysis.LogInfo('Identified suspected ranges %s from revisions %r' %
                     (suspected_ranges, suspected_revisions))

    with pipeline.InOrder():
      yield InitializeFlakeTryJobPipeline(
          analysis.key.urlsafe(), suspected_ranges, user_specified_iterations,
          user_specified_range, force)

      # Update the bug associated with the analysis with results of findings.
      yield UpdateFlakeBugPipeline(analysis.key.urlsafe())
