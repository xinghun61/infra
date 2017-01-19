# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import time_util

from common import appengine_util
from common import constants
from common.pipeline_wrapper import BasePipeline
from common.pipeline_wrapper import pipeline
from common.waterfall import failure_type
from model import analysis_status
from model import result_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.flake_try_job import FlakeTryJob
from waterfall.flake import confidence
from waterfall.flake.process_flake_try_job_result_pipeline import (
    ProcessFlakeTryJobResultPipeline)
from waterfall.flake.schedule_flake_try_job_pipeline import (
    ScheduleFlakeTryJobPipeline)
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline


# TODO(lijeffrey): The lookback algorithms for RecursiveFlakePipeline and
# RecursiveFlakeTryJob are to be identical. Refactor both files to use a base
# algorithm.


_GIT_REPO = CachedGitilesRepository(
    HttpClientAppengine(),
    'https://chromium.googlesource.com/chromium/src.git')


def CreateCulprit(revision, commit_position, confidence_score,
                   repo_name='chromium'):
  """Sets culprit information."""
  change_log = _GIT_REPO.GetChangeLog(revision)

  if change_log:
    url = change_log.code_review_url or change_log.commit_url
    culprit = FlakeCulprit.Create(
        repo_name, revision, commit_position, url, confidence_score)
  else:
    logging.error('Unable to retrieve change logs for %s', revision)
    culprit = FlakeCulprit.Create(
        repo_name, revision, commit_position, None, confidence_score)

  return culprit


def _UpdateAnalysisTryJobStatusUponCompletion(
    flake_analysis, culprit, status, error):
  flake_analysis.end_time = time_util.GetUTCNow()
  flake_analysis.try_job_status = status

  if error:
    flake_analysis.error = error
  elif culprit:
    flake_analysis.culprit = culprit
    flake_analysis.result_status = result_status.FOUND_UNTRIAGED
  else:
    flake_analysis.result_status = result_status.NOT_FOUND_UNTRIAGED

  flake_analysis.put()


class RecursiveFlakeTryJobPipeline(BasePipeline):
  """Starts a series of flake try jobs to identify the exact culprit."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, urlsafe_flake_analysis_key, commit_position, revision):
    """Runs a try job at a revision to determine its flakiness.

    Args:
      urlsafe_flake_analysis_key (str): The urlsafe-key of the flake analysis
          for which the try jobs are to analyze.
      commit_position (int): The commit position corresponding to |revision| to
        analyze.
      revision (str): The revision to run the try job against corresponding to
        |commit_position|.
    """
    flake_analysis = ndb.Key(urlsafe=urlsafe_flake_analysis_key).get()
    assert flake_analysis

    if (flake_analysis.error or
        flake_analysis.status != analysis_status.COMPLETED):
      # Don't start try-jobs if analysis at the build level did not complete
      # successfully.
      return

    # TODO(lijeffrey): support force/rerun.

    try_job = FlakeTryJob.Create(
        flake_analysis.master_name, flake_analysis.builder_name,
        flake_analysis.step_name, flake_analysis.test_name, revision)
    try_job.put()

    if flake_analysis.try_job_status is None:  # pragma: no branch
      flake_analysis.try_job_status = analysis_status.RUNNING
      flake_analysis.put()

    with pipeline.InOrder():
      try_job_id = yield ScheduleFlakeTryJobPipeline(
          flake_analysis.master_name, flake_analysis.builder_name,
          flake_analysis.step_name, flake_analysis.test_name, revision)

      try_job_result = yield MonitorTryJobPipeline(
          try_job.key.urlsafe(), failure_type.FLAKY_TEST, try_job_id)

      yield ProcessFlakeTryJobResultPipeline(
          revision, commit_position, try_job_result, try_job.key.urlsafe(),
          urlsafe_flake_analysis_key)

      yield NextCommitPositionPipeline(
          urlsafe_flake_analysis_key, try_job.key.urlsafe())


def _IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):
  return (
      pass_rate < lower_flake_threshold or pass_rate > upper_flake_threshold)


def _GetNextCommitPosition(data_points, flake_settings,
                           lower_boundary_commit_position):
  """Finds the next commit_position to analyze, or gets final result.

  Args:
    data_points (list): Already-completed data points.
    flake_settings (dict): Parameters for flakiness algorithm.
    lower_boundary_commit_position (int): The commit position not to pass when
        looking back.

  Returns:
    (next_commit_position, suspected_commit_position): The commit position of
        the next revision to check and suspected commit position that that the
        flakiness was introduced in. If next_commit_position needs to be
        checked, suspected_commit_position will be None. If
        suspected_commit_position is found, next_commit_position will be
        None. If no findings eventually, both will be None.
  """
  lower_flake_threshold = flake_settings.get('lower_flake_threshold')
  upper_flake_threshold = flake_settings.get('upper_flake_threshold')
  max_stable_in_a_row = flake_settings.get('max_stable_in_a_row')
  max_flake_in_a_row = flake_settings.get('max_flake_in_a_row')

  stables_in_a_row = 0
  flakes_in_a_row = 0
  stables_happened = False
  flakes_first = 0
  flaked_out = False
  next_commit_position = None

  total_data_points = len(data_points)

  for i in xrange(total_data_points):
    pass_rate = data_points[i].pass_rate
    commit_position = data_points[i].commit_position

    if pass_rate < 0:  # Test doesn't exist at this revision.
      if flaked_out or flakes_first:
        stables_in_a_row += 1
        lower_boundary = data_points[i - stables_in_a_row + 1].commit_position
        return lower_boundary + 1, None
      else:
        return None, None
    elif _IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):
      stables_in_a_row += 1
      flakes_in_a_row = 0
      stables_happened = True

      if stables_in_a_row <= max_stable_in_a_row:  # pragma: no cover.
        # No stable region yet, keep searching.
        next_commit_position = commit_position - 1
        continue
      # Stable region found.
      if not flaked_out and not flakes_first:  # pragma: no cover.
        # Already stabled_out but no flake region yet, no findings.
        return None, None

      # Flake region is also found, ready for sequential search.
      lower_boundary_index = i - stables_in_a_row + 1
      lower_boundary = data_points[lower_boundary_index].commit_position
      previous_commit_position = data_points[
          lower_boundary_index - 1].commit_position

      if previous_commit_position == lower_boundary + 1:
        # Sequential search is Done.
        return None, previous_commit_position
      # Continue sequential search.
      return lower_boundary + 1, None

    else:  # Flaky result.
      flakes_in_a_row += 1
      stables_in_a_row = 0

      if flakes_in_a_row > max_flake_in_a_row:  # Identified a flaky region.
        flaked_out = True

      if not stables_happened:  # pragma: no branch
        # No stables yet.
        flakes_first += 1

      if commit_position == lower_boundary_commit_position:  # pragma: no branch
        # The earliest commit_position to look back is already flaky. This is
        # the culprit.
        return None, commit_position

      step_size = flakes_in_a_row
      next_commit_position = commit_position - step_size
      continue

  if next_commit_position < lower_boundary_commit_position:
    # Do not run past the bounds of the blame list.
    return lower_boundary_commit_position, None

  return next_commit_position, None


def _GetTryJobDataPoints(analysis):
  """Gets which data points should be used to determine the next revision.

  Args:
    analysis (MasterFlakeAnalysis): The analysis entity to determine what data
        points to run on.

  Returns:
    A list of data points used to analyze and determine what try job to trigger
        next.
  """
  all_data_points = analysis.data_points

  # Include the suspected build itself first, which already has a result.
  data_points = [analysis.GetDataPointOfSuspectedBuild()]

  for i in range(0, len(all_data_points)):
    if all_data_points[i].try_job_url:
      data_points.append(all_data_points[i])

  return sorted(data_points, key=lambda k: k.commit_position, reverse=True)


class NextCommitPositionPipeline(BasePipeline):
  """Returns the next index in the blame list to run a try job on."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, urlsafe_flake_analysis_key, urlsafe_try_job_key):
    """Determines the next commit position to run a try job on.

    Args:
      urlsafe_flake_analysis_key (str): The url-safe key to the corresponding
          flake analysis that triggered this pipeline.
      urlsafe_try_job_key (str): The url-safe key to the try job that was just
          run.
    """
    flake_analysis = ndb.Key(urlsafe=urlsafe_flake_analysis_key).get()
    try_job = ndb.Key(urlsafe=urlsafe_try_job_key).get()
    assert flake_analysis
    assert try_job

    # Don't call another pipeline if the previous try job failed.
    if try_job.status == analysis_status.ERROR:
      error = try_job.error or {
          'error': 'Try job %s failed' % try_job.try_job_id,
          'message': 'The last try job did not complete as expected'
      }
      _UpdateAnalysisTryJobStatusUponCompletion(
          flake_analysis, None, analysis_status.ERROR, error)
      yield UpdateFlakeBugPipeline(flake_analysis.key.urlsafe())
      return

    # TODO(lijeffrey) Move parameters to config.
    flake_settings = {
        'lower_flake_threshold': 0.02,
        'upper_flake_threshold': 0.98,
        'max_flake_in_a_row': 1,
        'max_stable_in_a_row': 0,
    }

    suspected_build_data_point = flake_analysis.GetDataPointOfSuspectedBuild()
    lower_boundary_commit_position = (
        suspected_build_data_point.previous_build_commit_position + 1)

    # Because |suspected_build_data_point| already sets hard lower and upper
    # bounds, only the data points involved in try jobs should be considered
    # when determining the next commit position to test.
    try_job_data_points = _GetTryJobDataPoints(flake_analysis)

    # Figure out what commit position to trigger the next try job on, if any.
    next_commit_position, suspected_commit_position = _GetNextCommitPosition(
        try_job_data_points, flake_settings, lower_boundary_commit_position)

    if (next_commit_position is None or
        next_commit_position == suspected_build_data_point.commit_position):
      # Finished.
      if next_commit_position == suspected_build_data_point.commit_position:
        suspected_commit_position = next_commit_position

      confidence_score = confidence.SteppinessForCommitPosition(
         flake_analysis.data_points, suspected_commit_position)
      culprit_revision = suspected_build_data_point.GetRevisionAtCommitPosition(
          suspected_commit_position)
      culprit = CreateCulprit(
          culprit_revision, suspected_commit_position, confidence_score)
      _UpdateAnalysisTryJobStatusUponCompletion(
          flake_analysis, culprit, analysis_status.COMPLETED, None)
      yield UpdateFlakeBugPipeline(flake_analysis.key.urlsafe())
      return

    next_revision = suspected_build_data_point.GetRevisionAtCommitPosition(
        next_commit_position)

    pipeline_job = RecursiveFlakeTryJobPipeline(
        urlsafe_flake_analysis_key, next_commit_position, next_revision)
    # Disable attribute 'target' defined outside __init__ pylint warning,
    # because pipeline generates its own __init__ based on run function.
    pipeline_job.target = (  # pylint: disable=W0201
        appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND))
    pipeline_job.start()
