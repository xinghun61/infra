# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from gae_libs.pipeline_wrapper import BasePipeline
from libs import analysis_status
from libs import time_util
from waterfall import build_util
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.flake import confidence
from waterfall.flake import lookback_algorithm
from waterfall.flake import recursive_flake_try_job_pipeline
from waterfall.flake.recursive_flake_try_job_pipeline import (
    RecursiveFlakeTryJobPipeline)
from waterfall.flake.send_notification_for_flake_culprit_pipeline import (
    SendNotificationForFlakeCulpritPipeline)

_DEFAULT_MINIMUM_CONFIDENCE_SCORE = 0.6


def _HasSufficientConfidenceToRunTryJobs(analysis):
  """Determines whether there is sufficient confidence to run try jobs.

      Based on analysis of historical data, 60 percent confidence could filter
      out almost all false positives.

  Args:
    analysis (MasterFlakeAnalysis): A flake analysis with a suspected build
        identified.

  Returns:
    Whether or not the suspected build's confidence score is high enough to
        trigger try jobs against its revision range.
  """
  minimum_confidence_score = analysis.algorithm_parameters.get(
      'minimum_confidence_score_to_run_tryjobs',
      _DEFAULT_MINIMUM_CONFIDENCE_SCORE)
  return analysis.confidence_in_suspected_build >= minimum_confidence_score


def _GetFullBlamedCLsAndLowerBound(suspected_build_point, data_points):
  """Gets Full blame list and lower bound to bisect.

      For cases like B1(Stable) - B2(Exception) - B3(Flaky), the blame list
      should be revisions in B2 and B3, and lower bound should be
      B1.commit_position. Note the previous build's commit position is included
      for bisection as the known stable point.

  Args:
    suspected_build_point (int): The suspected build number flakiness was
        introduced in.
    data_points (list): A list of DataPoints to determine the regression range
        to run try jobs against.

  Returns:
    (dict, int): A dict mapping commit positions to revisions and the earlist
        commit position to analyze.
  """
  blamed_cls = suspected_build_point.GetDictOfCommitPositionAndRevision()
  _, invalid_points = lookback_algorithm.GetCategorizedDataPoints(data_points)
  if not invalid_points:
    return blamed_cls, suspected_build_point.previous_build_commit_position

  build_lower_bound = suspected_build_point.build_number
  point_lower_bound = suspected_build_point
  invalid_points.sort(key=lambda k: k.build_number, reverse=True)
  for data_point in invalid_points:
    if data_point.build_number != build_lower_bound - 1:
      break
    build_lower_bound = data_point.build_number
    blamed_cls.update(data_point.GetDictOfCommitPositionAndRevision())
    point_lower_bound = data_point

  return blamed_cls, point_lower_bound.previous_build_commit_position


class InitializeFlakeTryJobPipeline(BasePipeline):
  """Determines whether try jobs need to be run and where to start."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, analysis_urlsafe_key, user_specified_iterations,
          user_specified_range, force):
    """Pipeline to trigger try jobs on a suspected build range.

    Args:
      analysis_urlsafe_key (str): The url-safe key to the MasterFlakeAnalysis
          being analyzed.
      user_specified_iterations (int): The number of iterations to rerun as
          specified by the user. If None is passed, Findit will determine the
          number of iterations to rerun.
      user_specified_range (bool): Whether or not the user had specified a
          range to run analysis on, used for overriding confidence score when
          triggering try jobs.
      force (bool): Force this build to run from scratch,
          a rerun by an admin will trigger this.
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis
    master_name = analysis.master_name
    builder_name = analysis.builder_name
    triggering_build_number = analysis.build_number

    if analysis.confidence_in_suspected_build is None:
      logging.info(('Skipping try jobs due to no suspected flake build being '
                    'identified'))
      analysis.Update(
          end_time=time_util.GetUTCNow(),
          try_job_status=analysis_status.SKIPPED)
    elif not (_HasSufficientConfidenceToRunTryJobs(analysis) or
              user_specified_range):
      logging.info('Bailing out from automatic try job analysis due to '
                   'insufficiene confidence in suspected build')
      analysis.Update(
          end_time=time_util.GetUTCNow(),
          try_job_status=analysis_status.SKIPPED)
    else:
      suspected_build_point = analysis.GetDataPointOfSuspectedBuild()
      assert suspected_build_point
      blamed_cls, lower_bound_commit_position = _GetFullBlamedCLsAndLowerBound(
          suspected_build_point, analysis.data_points)

      if blamed_cls:
        upper_bound_commit_position = suspected_build_point.commit_position

        if len(blamed_cls) > 1:
          start_commit_position = lookback_algorithm.BisectPoint(
              lower_bound_commit_position, upper_bound_commit_position)
          start_revision = blamed_cls[start_commit_position]
          build_info = build_util.GetBuildInfo(master_name, builder_name,
                                               triggering_build_number)
          parent_mastername = build_info.parent_mastername or master_name
          parent_buildername = build_info.parent_buildername or builder_name
          cache_name = swarming_util.GetCacheName(parent_mastername,
                                                  parent_buildername)
          dimensions = waterfall_config.GetTrybotDimensions(
              parent_mastername, parent_buildername)
          logging.info(
              'Running try-jobs against commits in regression range [%d:%d]',
              lower_bound_commit_position, upper_bound_commit_position)
          analysis.Update(try_job_status=analysis_status.RUNNING)

          yield RecursiveFlakeTryJobPipeline(
              analysis.key.urlsafe(),
              start_commit_position,
              start_revision,
              lower_bound_commit_position,
              upper_bound_commit_position,
              user_specified_iterations,
              cache_name,
              dimensions,
              rerun=force)
        else:
          logging.info('Single commit in the blame list of suspected build')
          culprit_confidence_score = confidence.SteppinessForCommitPosition(
              analysis.data_points, upper_bound_commit_position)
          culprit = recursive_flake_try_job_pipeline.UpdateCulprit(
              analysis_urlsafe_key, suspected_build_point.git_hash,
              upper_bound_commit_position)
          analysis.Update(
              culprit_urlsafe_key=culprit.key.urlsafe(),
              confidence_in_culprit=culprit_confidence_score,
              try_job_status=analysis_status.COMPLETED)

          yield SendNotificationForFlakeCulpritPipeline(analysis_urlsafe_key)
      else:
        logging.error('Cannot run flake try jobs against empty blame list')
        error = {
            'error': 'Could not start try jobs',
            'message': 'Empty blame list'
        }
        analysis.Update(
            try_job_status=analysis_status.ERROR,
            error=error,
            end_time=time_util.GetUTCNow())
