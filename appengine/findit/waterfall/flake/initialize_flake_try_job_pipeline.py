# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs.pipeline_wrapper import BasePipeline
from libs import analysis_status
from libs import time_util

from common import monitoring
from waterfall import build_util
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.flake import confidence
from waterfall.flake import flake_constants
from waterfall.flake import heuristic_analysis_util
from waterfall.flake import lookback_algorithm
from waterfall.flake import recursive_flake_try_job_pipeline
from waterfall.flake.recursive_flake_try_job_pipeline import (
    RecursiveFlakeTryJobPipeline)
from waterfall.flake.send_notification_for_flake_culprit_pipeline import (
    SendNotificationForFlakeCulpritPipeline)


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
      flake_constants.DEFAULT_MINIMUM_CONFIDENCE_SCORE)
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


def _DataPointBeforeSuspectIsFullyStable(analysis):
  assert analysis.suspected_flake_build_number is not None
  # Note when migrating to LUCI there is no concept of build number, but a
  # build ID (str). TODO(crbug.com/769374): Use commit position only instead of
  # build number,
  previous_data_point = analysis.FindMatchingDataPointWithBuildNumber(
      analysis.suspected_flake_build_number - 1)
  assert previous_data_point

  return lookback_algorithm.IsFullyStable(previous_data_point.pass_rate)


def _HasHeuristicResults(analysis):
  """Determines whether an analysis has heuristic results."""
  return bool(analysis.suspect_urlsafe_keys)


def _ShouldRunTryJobs(analysis, user_specified_range):
  """Determines whether try jobs should be run.

  Rules should be followed in order of precedence:
  1. Never run try jobs if there is no suspected flake build.
  2. Always run try jobs if the user requested a specific range to run that
     leads to a suspected build.
  3. Never run try jobs if the stable build before the suspect isn't a full 100%
     passing or failing.
  4. Always run try jobs if heuristic analysis suggests a culprit.
  5. Never run try jobs if there is insufficient confidence in the suspected
     build.

  Args:
    analysis (MasterFlakeAnalysis): The main analysis being run.
    user_specified_range (boolean): whetehr this analysis is in progress due to
        a user specifying a range to rerun.

  Returns:
    Boolean whether try jobs should be run after identifying a suspected build
        cycle.
  """
  if analysis.suspected_flake_build_number is None:
    analysis.LogInfo(
        'Skipping try jobs due to no suspected flake build being identified')
    return False

  if user_specified_range:
    # Always run try jobs if the user specified a range to analyze that led to
    # a suspected flake build number being identified.
    analysis.LogInfo('Running try jobs on user-specified range')
    return True

  if not _DataPointBeforeSuspectIsFullyStable(analysis):
    # The previous data point is only slightly flaky. Running try jobs may yield
    # false positives so bail out.
    analysis.LogInfo('Skipping try jobs due to previous data point being '
                     'slightly flaky')
    return False

  if _HasHeuristicResults(analysis):
    # Analyses with heuristic results are highly-suspect. Run try jobs to check.
    analysis.LogInfo('Running try jobs with heuristic-guidance')
    return True

  if not _HasSufficientConfidenceToRunTryJobs(analysis):
    analysis.LogInfo(
        'Skipping try jobs due to insufficient confidence in suspected build')
    return False

  analysis.LogInfo('All checks for running try jobs passed')
  return True


def _RevisionToCommitPositions(commits_to_revisions_dict):
  """Inverts commit_position:revision mappings to revision:commit_position.

      Assumes all keys and values in commtis_to_revisions_dict are unique.

  Args:
    commits_to_revisions_dict (dict): A dict mapping commit positions to
        revisions. For example:
        {
            101: 'r101',
            102: 'r102',
        }

  Returns:
    (dict): A dict mapping revisions to commit positions that is the inverse of
        the input dict. For example,
        {
            'r101': 101,
            'r102': 102,
        }
  """
  # Enforce all commits and revisions are unique.
  commits = commits_to_revisions_dict.keys()
  revisions = commits_to_revisions_dict.values()
  assert len(commits) == len(list(set(commits)))
  assert len(revisions) == len(list(set(revisions)))

  return dict(reversed(item) for item in commits_to_revisions_dict.items())


class InitializeFlakeTryJobPipeline(BasePipeline):
  """Determines whether try jobs need to be run and where to start."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, analysis_urlsafe_key, suspected_ranges,
          user_specified_iterations, user_specified_range, force):
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

    if _ShouldRunTryJobs(analysis, user_specified_range):
      analysis.LogInfo('Preparing to perform revision-level analysis')
      analysis.LogInfo('Suspected ranges: %r' % suspected_ranges)

      suspected_build_point = analysis.GetDataPointOfSuspectedBuild()
      assert suspected_build_point
      blamed_cls, lower_bound_commit_position = _GetFullBlamedCLsAndLowerBound(
          suspected_build_point, analysis.data_points)

      if blamed_cls:
        upper_bound_commit_position = suspected_build_point.commit_position

        if len(blamed_cls) > 1:
          revisions_to_commits = _RevisionToCommitPositions(blamed_cls)
          suspected_commit_positions = (
              heuristic_analysis_util.ListCommitPositionsFromSuspectedRanges(
                  revisions_to_commits, suspected_ranges))
          analysis.LogInfo('Commit positions to analyze first from heuristic '
                           'analysis %r --> %r' % (suspected_ranges,
                                                   suspected_commit_positions))

          if suspected_commit_positions:
            # Run commit positions suggested by heuristic analysis first.
            start_commit_position = suspected_commit_positions[0]
            assert start_commit_position >= lower_bound_commit_position
            assert start_commit_position <= upper_bound_commit_position
          else:
            # Fallback to bisect if no heuristic results.
            start_commit_position = lookback_algorithm.BisectPoint(
                lower_bound_commit_position, upper_bound_commit_position)

          start_revision = blamed_cls[start_commit_position]
          remaining_suspected_commit_positions = suspected_commit_positions[1:]
          build_info = build_util.GetBuildInfo(master_name, builder_name,
                                               triggering_build_number)
          parent_mastername = build_info.parent_mastername or master_name
          parent_buildername = build_info.parent_buildername or builder_name
          cache_name = swarming_util.GetCacheName(parent_mastername,
                                                  parent_buildername)
          dimensions = waterfall_config.GetTrybotDimensions(
              parent_mastername, parent_buildername)
          analysis.LogInfo(
              'Running try-jobs against commits in regression range [%d:%d]' %
              (lower_bound_commit_position, upper_bound_commit_position))
          analysis.Update(try_job_status=analysis_status.RUNNING)

          yield RecursiveFlakeTryJobPipeline(
              analysis.key.urlsafe(), remaining_suspected_commit_positions,
              start_commit_position, start_revision,
              lower_bound_commit_position, upper_bound_commit_position,
              user_specified_iterations, cache_name, dimensions, force)
        else:
          analysis.LogInfo('Single commit in the blame list of suspected build')
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
        analysis.LogError('Cannot run flake try jobs against empty blame list')
        error = {
            'error': 'Could not start try jobs',
            'message': 'Empty blame list'
        }
        analysis.Update(
            try_job_status=analysis_status.ERROR,
            error=error,
            end_time=time_util.GetUTCNow())
        duration = analysis.end_time - analysis.start_time
        monitoring.analysis_durations.add(duration.total_seconds(), {
            'type': 'flake',
            'result': 'error',
        })
    else:
      analysis.Update(
          end_time=time_util.GetUTCNow(),
          try_job_status=analysis_status.SKIPPED)
      duration = analysis.end_time - analysis.start_time
      monitoring.analysis_durations.add(duration.total_seconds(), {
          'type': 'flake',
          'result': 'skipped',
      })
