# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common import constants
from common.waterfall import failure_type
from gae_libs import appengine_util
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from libs import time_util
from model import result_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from waterfall.flake import confidence
from waterfall.flake import lookback_algorithm
from waterfall.flake.lookback_algorithm import NormalizedDataPoint
from waterfall.flake.process_flake_try_job_result_pipeline import (
    ProcessFlakeTryJobResultPipeline)
from waterfall.flake.schedule_flake_try_job_pipeline import (
    ScheduleFlakeTryJobPipeline)
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline


_GIT_REPO = CachedGitilesRepository(
    HttpClientAppengine(),
    'https://chromium.googlesource.com/chromium/src.git')
_DEFAULT_ITERATIONS_TO_RERUN = 100


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


def UpdateAnalysisUponCompletion(
    flake_analysis, culprit, status, error):
  flake_analysis.end_time = time_util.GetUTCNow()
  flake_analysis.try_job_status = status

  if error:
    flake_analysis.error = error
  else:
    flake_analysis.last_attempted_swarming_task_id = None
    flake_analysis.last_attempted_revision = None
    if culprit:
      flake_analysis.culprit = culprit
      flake_analysis.result_status = result_status.FOUND_UNTRIAGED
    else:
      flake_analysis.result_status = result_status.NOT_FOUND_UNTRIAGED

  flake_analysis.put()


@ndb.transactional
def _GetTryJob(
    master_name, builder_name, step_name, test_name, revision):
  """Gets or creates a FlakeTryJob for the specified configuration.

    If a try job from a previous run with this configuration was already run,
    reuse the entity. Else create a new one.

  Args:
    master_name (string): The master name of the analysis this try job is for.
    builder_name (string): The builder name of the analysis this try job is for.
    step_name (string): The step that the flaky test was found on.
    test_name (string): The name of the flaky test.
    revision (string): The chromium revision/git hash that this try job will be
        analyzing.

  Returns:
    FlakeTryJobData representing the try job.
  """
  try_job = FlakeTryJob.Get(
      master_name, builder_name, step_name, test_name, revision)
  if not try_job:
    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.put()
  return try_job


def _GetIterationsToRerun(user_specified_iterations, analysis):
  return (user_specified_iterations or
          analysis.algorithm_parameters.get(
              'try_job_rerun', {}).get('iterations_to_rerun',
                                       _DEFAULT_ITERATIONS_TO_RERUN))


def _NeedANewTryJob(analysis, try_job, required_iterations, rerun):
  """Determines whether or not a try job needs to be run.

    A try job needs to be run if:
    1. It is to generate a data point on a build configuration and revision
       for which there is no existing data.
    2. A data point exists for the revision, but it is stable and run against
       too few iterations.

  Args:
    analysis (MasterFlakeAnalysis): The flake analysis for which try jobs are
        analyzing.
    try_job (FlakeTryJob): A flake try job entity.
    rerun (bool): Whether or not to force a rerun regardless of the need to.
  """
  if rerun or not try_job.flake_results:
    # Either this is a redo from scratch or a brand new try job.
    return True

  step_name = try_job.step_name
  test_name = try_job.test_name
  revision = try_job.git_hash
  result = try_job.flake_results[-1]['report']['result'][revision][step_name]
  pass_fail_counts = result.get('pass_fail_counts', {})

  if pass_fail_counts:
    # The existing try job attempt completed successfully.
    test_results = pass_fail_counts[test_name]
    pass_count = test_results['pass_count']
    fail_count = test_results['fail_count']
    tries = pass_count + fail_count
    pass_rate = float(pass_count) / tries
    lower_flake_threshold = analysis.algorithm_parameters[
        'try_job_rerun']['lower_flake_threshold']
    upper_flake_threshold = analysis.algorithm_parameters[
        'try_job_rerun']['upper_flake_threshold']

    if (lookback_algorithm.IsStable(
        pass_rate, lower_flake_threshold, upper_flake_threshold) and
        tries < required_iterations):
      # Stable results with insufficient iterations are not reliable and should
      # be rerun.
      return True

  # Either the test does not exist at the revision, test is stable with
  # sufficient iterations, or is flaky. No need for a new try job.
  return False


def _SetAnalysisTryJobStatus(analysis, desired_status):
  # Sets an analysis' try_job_status to desired_status.
  if analysis.try_job_status != desired_status:
    analysis.try_job_status = desired_status


class RecursiveFlakeTryJobPipeline(BasePipeline):
  """Starts a series of flake try jobs to identify the exact culprit."""

  def __init__(
      self, urlsafe_flake_analysis_key, commit_position, revision,
      lower_bound_commit_position, upper_bound_commit_position,
      user_specified_iterations, cache_name, dimensions):
    super(RecursiveFlakeTryJobPipeline, self).__init__(
        urlsafe_flake_analysis_key, commit_position, revision,
        lower_bound_commit_position, upper_bound_commit_position,
        user_specified_iterations, cache_name, dimensions)
    self.urlsafe_flake_analysis_key = urlsafe_flake_analysis_key
    self.commit_position = commit_position
    self.revision = revision
    self.lower_bound_commit_position = lower_bound_commit_position
    self.upper_bound_commit_position = upper_bound_commit_position
    self.user_specified_iterations = user_specified_iterations

  def _LogUnexpectedAbort(self):
    if not self.was_aborted:
      return

    flake_analysis = ndb.Key(urlsafe=self.urlsafe_flake_analysis_key).get()

    assert flake_analysis

    flake_analysis.try_job_status = analysis_status.ERROR
    flake_analysis.error = flake_analysis.error or {
        'error': 'RecursiveFlakeTryJobPipeline was aborted unexpectedly',
        'message': 'RecursiveFlakeTryJobPipeline was aborted unexpectedly'
    }
    flake_analysis.end_time = time_util.GetUTCNow()
    flake_analysis.put()

    try_job = FlakeTryJob.Get(
        flake_analysis.master_name, flake_analysis.builder_name,
        flake_analysis.step_name, flake_analysis.test_name, self.revision)

    if try_job and not try_job.completed:
      try_job.status = analysis_status.ERROR
      try_job.put()

    if not try_job or not try_job.try_job_ids:
      return

    try_job_data = FlakeTryJobData.Get(try_job.try_job_ids[-1])
    if try_job_data:  # pragma: no branch
      try_job_data.error = try_job_data.error or {
          'error': 'RecursiveFlakeTryJobPipeline was aborted unexpectedly',
          'message': 'RecursiveFlakeTryJobPipeline was aborted unexpectedly'
      }
      try_job_data.put()

  def finalized(self):
    self._LogUnexpectedAbort()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, urlsafe_flake_analysis_key, commit_position, revision,
          lower_bound_commit_position, upper_bound_commit_position,
          user_specified_iterations, cache_name, dimensions, rerun=False):
    """Runs a try job at a revision to determine its flakiness.

    Args:
      urlsafe_flake_analysis_key (str): The urlsafe-key of the flake analysis
          for which the try jobs are to analyze.
      commit_position (int): The commit position corresponding to |revision| to
          analyze.
      revision (str): The revision to run the try job against corresponding to
          |commit_position|.
      lower_bound_commit_position (int): The lower bound of commit position
          that can run a try job.
      user_specified_iterations (int): The number of iterations the test
          should be run as specified by the user. If None, Findit will use
          what's specified in the analysis' algorithm parameters.
      cache_name (str): A string to identify separate directories for different
          waterfall bots on the trybots.
      dimensions (list): A list of strings in the format
          ["key1:value1", "key2:value2"].
      rerun (bool): Whether or not a full rerun of this analysis is being
          requested.
    """
    analysis = ndb.Key(urlsafe=urlsafe_flake_analysis_key).get()
    assert analysis

    if analysis.error or analysis.status != analysis_status.COMPLETED:
      # Don't start try-jobs if analysis at the build level did not complete
      # successfully.
      return

    try_job = _GetTryJob(
        analysis.master_name, analysis.builder_name,
        analysis.canonical_step_name, analysis.test_name, revision)

    if _NeedANewTryJob(analysis, try_job, user_specified_iterations, rerun):
      _SetAnalysisTryJobStatus(analysis, analysis_status.RUNNING)
      analysis.last_attempted_revision = revision
      analysis.put()

      iterations = _GetIterationsToRerun(user_specified_iterations, analysis)

      with pipeline.InOrder():
        try_job_id = yield ScheduleFlakeTryJobPipeline(
            analysis.master_name, analysis.builder_name,
            analysis.canonical_step_name, analysis.test_name, revision,
            analysis.key.urlsafe(), cache_name, dimensions, iterations)

        try_job_result = yield MonitorTryJobPipeline(
            try_job.key.urlsafe(), failure_type.FLAKY_TEST, try_job_id)

        yield ProcessFlakeTryJobResultPipeline(
            revision, commit_position, try_job_result, try_job.key.urlsafe(),
            urlsafe_flake_analysis_key)

        yield NextCommitPositionPipeline(
            urlsafe_flake_analysis_key, try_job.key.urlsafe(),
            lower_bound_commit_position, upper_bound_commit_position,
            user_specified_iterations, cache_name, dimensions)
    else:
      yield NextCommitPositionPipeline(
          urlsafe_flake_analysis_key, try_job.key.urlsafe(),
          lower_bound_commit_position, upper_bound_commit_position,
          user_specified_iterations, cache_name, dimensions)


def _NormalizeDataPoints(data_points):
  normalized_data_points = [
      (lambda data_point: NormalizedDataPoint(
          data_point.commit_position,
          data_point.pass_rate))(d) for d in data_points]

  return sorted(normalized_data_points, key=lambda k: k.run_point_number,
                reverse=True)


def _GetNormalizedTryJobDataPoints(
    analysis, lower_bound_commit_position, upper_bound_commit_position):
  """Gets which data points should be used to determine the next revision.

  Args:
    analysis (MasterFlakeAnalysis): The analysis entity to determine what data
        points to run on.
    lower_bound_commit_position (int): The earliest commit position to include
        in the list of data points to consider the next run point.
    upper_bound_commit_position (int): The latest commit position to include
        in the list of data points to consider the next run point.

  Returns:
    A list of normalized data points used to analyze and determine what try job
        to trigger next. A normalized data point has only pass_rate and
        run_point_number.
  """
  data_points = []
  all_data_points = analysis.data_points
  for i in range(0, len(all_data_points)):
    if (all_data_points[i].commit_position >= lower_bound_commit_position and
        all_data_points[i].commit_position <= upper_bound_commit_position):
      data_points.append(all_data_points[i])

  return _NormalizeDataPoints(data_points)


class NextCommitPositionPipeline(BasePipeline):
  """Returns the next index in the blame list to run a try job on."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, urlsafe_flake_analysis_key, urlsafe_try_job_key,
          lower_bound_commit_position, upper_bound_commit_position,
          user_specified_iterations, cache_name, dimensions):
    """Determines the next commit position to run a try job on.

    Args:
      urlsafe_flake_analysis_key (str): The url-safe key to the corresponding
          flake analysis that triggered this pipeline.
      urlsafe_try_job_key (str): The url-safe key to the try job that was just
          run.
      lower_bound_commit_position (int): The lower bound commit position to
          consider when deciding the next run point number.
      upper_bound_commit_position (int): The upper bound commit position to
          consider when deciding the next run point number.
    """
    flake_analysis = ndb.Key(urlsafe=urlsafe_flake_analysis_key).get()
    try_job = ndb.Key(urlsafe=urlsafe_try_job_key).get()
    assert flake_analysis
    assert try_job
    assert try_job.try_job_ids

    try_job_id = try_job.try_job_ids[-1]
    try_job_data = FlakeTryJobData.Get(try_job_id)

    # Don't call another pipeline if the previous try job failed.
    if try_job_data.error:
      UpdateAnalysisUponCompletion(
          flake_analysis, None, analysis_status.ERROR, try_job_data.error)
      yield UpdateFlakeBugPipeline(flake_analysis.key.urlsafe())
      return

    algorithm_settings = flake_analysis.algorithm_parameters.get(
        'try_job_rerun', {})

    # Figure out what commit position to trigger the next try job on, if any.
    suspected_build_data_point = flake_analysis.GetDataPointOfSuspectedBuild()
    data_points = _GetNormalizedTryJobDataPoints(
        flake_analysis, lower_bound_commit_position,
        upper_bound_commit_position)
    next_commit_position, suspected_commit_position, _ = (
        lookback_algorithm.GetNextRunPointNumber(
            data_points, algorithm_settings, lower_bound_commit_position))

    if suspected_commit_position is not None:  # Finished.
      confidence_score = confidence.SteppinessForCommitPosition(
          flake_analysis.data_points, suspected_commit_position)
      culprit_revision = suspected_build_data_point.GetRevisionAtCommitPosition(
          suspected_commit_position)
      culprit = CreateCulprit(
          culprit_revision, suspected_commit_position, confidence_score)
      UpdateAnalysisUponCompletion(
          flake_analysis, culprit, analysis_status.COMPLETED, None)

      yield UpdateFlakeBugPipeline(flake_analysis.key.urlsafe())
      return

    next_revision = suspected_build_data_point.GetRevisionAtCommitPosition(
        next_commit_position)

    pipeline_job = RecursiveFlakeTryJobPipeline(
        urlsafe_flake_analysis_key, next_commit_position, next_revision,
        lower_bound_commit_position, upper_bound_commit_position,
        user_specified_iterations, cache_name, dimensions)
    # Disable attribute 'target' defined outside __init__ pylint warning,
    # because pipeline generates its own __init__ based on run function.
    pipeline_job.target = (  # pylint: disable=W0201
        appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND))
    pipeline_job.start()
