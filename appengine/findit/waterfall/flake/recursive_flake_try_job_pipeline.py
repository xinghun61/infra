# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common import constants
from common.findit_http_client import FinditHttpClient
from common import monitoring
from common.waterfall import failure_type
from gae_libs import appengine_util
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from libs import time_util
from model.flake.flake_culprit import FlakeCulprit
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.flake import confidence
from waterfall.flake import flake_analysis_util
from waterfall.flake import flake_constants
from waterfall.flake import lookback_algorithm
from waterfall.flake.flake_analysis_util import NormalizedDataPoint
from waterfall.flake.process_flake_try_job_result_pipeline import (
    ProcessFlakeTryJobResultPipeline)
from waterfall.flake.schedule_flake_try_job_pipeline import (
    ScheduleFlakeTryJobPipeline)
from waterfall.flake.send_notification_for_flake_culprit_pipeline import (
    SendNotificationForFlakeCulpritPipeline)
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline

_GIT_REPO = CachedGitilesRepository(
    FinditHttpClient(), 'https://chromium.googlesource.com/chromium/src.git')

_MAX_RETRY_TIMES = 5
_BASE_COUNT_DOWN_SECONDS = 2 * 60


@ndb.transactional
def UpdateCulprit(analysis_urlsafe_key,
                  revision,
                  commit_position,
                  repo_name='chromium'):
  """Sets culprit information."""
  culprit = (FlakeCulprit.Get(repo_name, revision) or
             FlakeCulprit.Create(repo_name, revision, commit_position))

  needs_updating = False

  if culprit.url is None:
    change_log = _GIT_REPO.GetChangeLog(revision)

    if change_log:
      culprit.url = change_log.code_review_url or change_log.commit_url
      needs_updating = True
    else:
      logging.error('Unable to retrieve change logs for %s', revision)

  if analysis_urlsafe_key not in culprit.flake_analysis_urlsafe_keys:
    culprit.flake_analysis_urlsafe_keys.append(analysis_urlsafe_key)
    needs_updating = True

  if needs_updating:
    culprit.put()

  return culprit


@ndb.transactional
def _GetTryJob(master_name, builder_name, step_name, test_name, revision):
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
  try_job = FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                            revision)
  if not try_job:
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()
  return try_job


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
    lower_flake_threshold = analysis.algorithm_parameters['try_job_rerun'][
        'lower_flake_threshold']
    upper_flake_threshold = analysis.algorithm_parameters['try_job_rerun'][
        'upper_flake_threshold']

    if (lookback_algorithm.IsStable(pass_rate, lower_flake_threshold,
                                    upper_flake_threshold) and
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


def _CanStartTryJob(try_job, rerun, retries):
  try_master, try_builder = waterfall_config.GetWaterfallTrybot(
      try_job.master_name, try_job.builder_name)
  if (try_master.startswith('luci.') and not rerun and
      retries < _MAX_RETRY_TIMES):
    dimensions = waterfall_config.GetTrybotDimensions(try_master, try_builder)
    bot_counts = swarming_util.GetSwarmingBotCounts(dimensions,
                                                    FinditHttpClient())
    waterfall_reserved_rate = waterfall_config.GetTryJobSettings().get(
        'waterfall_reserved_rate', .5)
    total_count = bot_counts.get('count') or -1
    available_count = bot_counts.get('available', 0)
    available_rate = float(available_count) / total_count
    return available_rate >= waterfall_reserved_rate
  return True


class RecursiveFlakeTryJobPipeline(BasePipeline):
  """Starts a series of flake try jobs to identify the exact culprit."""

  def __init__(self,
               urlsafe_flake_analysis_key,
               remaining_suspected_commit_positions,
               commit_position,
               revision,
               lower_bound_commit_position,
               upper_bound_commit_position,
               user_specified_iterations,
               cache_name,
               dimensions,
               rerun,
               retries=0):
    super(RecursiveFlakeTryJobPipeline, self).__init__(
        urlsafe_flake_analysis_key,
        remaining_suspected_commit_positions,
        commit_position,
        revision,
        lower_bound_commit_position,
        upper_bound_commit_position,
        user_specified_iterations,
        cache_name,
        dimensions,
        rerun,
        retries=retries)
    self.urlsafe_flake_analysis_key = urlsafe_flake_analysis_key
    self.commit_position = commit_position
    self.revision = revision
    self.lower_bound_commit_position = lower_bound_commit_position
    self.upper_bound_commit_position = upper_bound_commit_position
    self.user_specified_iterations = user_specified_iterations
    self.rerun = rerun
    self.retries = retries

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
    duration = flake_analysis.end_time - flake_analysis.start_time
    monitoring.analysis_durations.add(duration.total_seconds(), {
        'type': 'flake',
        'result': 'error',
    })

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
  def run(self,
          urlsafe_flake_analysis_key,
          remaining_suspected_commit_positions,
          commit_position,
          revision,
          lower_bound_commit_position,
          upper_bound_commit_position,
          user_specified_iterations,
          cache_name,
          dimensions,
          rerun,
          retries=0):
    """Runs a try job at a revision to determine its flakiness.

    Args:
      urlsafe_flake_analysis_key (str): The urlsafe-key of the flake analysis
          for which the try jobs are to analyze.
      remaining_suspected_commit_positions (list): A list of commit positions
          not yet analyzed but may aid in finding the culprit faster than
          bisecting.
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

    try_job = _GetTryJob(analysis.master_name, analysis.builder_name,
                         analysis.canonical_step_name, analysis.test_name,
                         revision)

    if _NeedANewTryJob(analysis, try_job, user_specified_iterations, rerun):
      if _CanStartTryJob(try_job, rerun, retries):
        _SetAnalysisTryJobStatus(analysis, analysis_status.RUNNING)
        analysis.last_attempted_revision = revision
        analysis.put()

        iterations = flake_analysis_util.GetIterationsToRerun(
            user_specified_iterations, analysis, 'try_job_rerun')

        with pipeline.InOrder():
          try_job_id = yield ScheduleFlakeTryJobPipeline(
              analysis.master_name, analysis.builder_name,
              analysis.canonical_step_name, analysis.test_name, revision,
              analysis.key.urlsafe(), cache_name, dimensions, iterations)

          try_job_result = yield MonitorTryJobPipeline(
              try_job.key.urlsafe(), failure_type.FLAKY_TEST, try_job_id)

          yield ProcessFlakeTryJobResultPipeline(
              revision, commit_position, try_job_result,
              try_job.key.urlsafe(), urlsafe_flake_analysis_key)

          yield NextCommitPositionPipeline(
              urlsafe_flake_analysis_key,
              try_job.key.urlsafe(), remaining_suspected_commit_positions,
              commit_position, lower_bound_commit_position,
              upper_bound_commit_position, user_specified_iterations,
              cache_name, dimensions, rerun)
      else:
        retries += 1

        pipeline_job = RecursiveFlakeTryJobPipeline(
            urlsafe_flake_analysis_key,
            remaining_suspected_commit_positions,
            commit_position,
            revision,
            lower_bound_commit_position,
            upper_bound_commit_position,
            user_specified_iterations,
            cache_name,
            dimensions,
            rerun,
            retries=retries)

        # Disable attribute 'target' defined outside __init__ pylint warning,
        # because pipeline generates its own __init__ based on run function.
        pipeline_job.target = (  # pylint: disable=W0201
            appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND))

        # Delay or start off peak.
        if retries > _MAX_RETRY_TIMES:
          pipeline_job._StartOffPSTPeakHours(queue_name=self.queue_name or
                                             constants.DEFAULT_QUEUE)
          logging.info('Retries exceed max count, RecursiveFlakeTryJobPipeline '
                       'on MasterFlakeAnalysis %s/%s/%s/%s/%s will start off '
                       'peak hours', analysis.master_name,
                       analysis.builder_name, analysis.build_number,
                       analysis.step_name, analysis.test_name)
        else:
          pipeline_job._RetryWithDelay(queue_name=self.queue_name or
                                       constants.DEFAULT_QUEUE)
          countdown = retries * _BASE_COUNT_DOWN_SECONDS
          logging.info('No available swarming bots, '
                       'RecursiveFlakeTryJobPipeline on MasterFlakeAnalysis '
                       '%s/%s/%s/%s/%s will be tried after %d seconds',
                       analysis.master_name, analysis.builder_name,
                       analysis.build_number, analysis.step_name,
                       analysis.test_name, countdown)

    else:
      yield NextCommitPositionPipeline(
          urlsafe_flake_analysis_key,
          try_job.key.urlsafe(), remaining_suspected_commit_positions,
          commit_position, lower_bound_commit_position,
          upper_bound_commit_position, user_specified_iterations, cache_name,
          dimensions, rerun)

  def _StartOffPSTPeakHours(self, *args, **kwargs):
    """Starts the pipeline off PST peak hours if not triggered manually."""
    kwargs['eta'] = swarming_util.GetETAToStartAnalysis(False)
    self.start(*args, **kwargs)

  def _RetryWithDelay(self, *args, **kwargs):
    """Trys to start the pipeline later."""
    kwargs['countdown'] = kwargs.get('retries', 1) * _BASE_COUNT_DOWN_SECONDS
    self.start(*args, **kwargs)


def _NormalizeDataPoints(data_points):
  normalized_data_points = [(NormalizedDataPoint(data_point.commit_position,
                                                 data_point.pass_rate))
                            for data_point in data_points]

  return sorted(normalized_data_points, key=lambda k: k.run_point_number)


def _GetNormalizedTryJobDataPoints(analysis, lower_bound_commit_position,
                                   upper_bound_commit_position):
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


def _GetSuspectedCommitConfidenceScore(analysis, suspected_commit_position,
                                       data_points_within_range):
  """Gets a confidence score for a suspected commit position.

  Args:
    analysis (MasterFlakeAnalysis): The analysis itself.
    suspected_build (int): The suspected build number that flakiness started in.
        Can be None if not identified.
    data_points_within_range (list): A list of DataPoint() entities to calculate
        stepinness and determine a confidence score.

  Returns:
    Float between 0 and 1 representing confidence in the suspected build number
        or None if not found.
  """
  if suspected_commit_position is None:
    return None

  # If this build introduced a new flaky test, confidence should be 100%.
  previous_point = analysis.FindMatchingDataPointWithCommitPosition(
      suspected_commit_position - 1)
  if (previous_point and
      previous_point.pass_rate == flake_constants.PASS_RATE_TEST_NOT_FOUND):
    return 1.0

  return confidence.SteppinessForCommitPosition(data_points_within_range,
                                                suspected_commit_position)


def _GetNextCommitPositionAndRemainingSuspects(
    analysis, remaining_suspected_commit_positions,
    previously_run_commit_position, next_bisect_commit_position):
  """Gets the next commit to run and remaining suspects to try.

  Args:
    analysis (MasterFlakeAnalysis): The analysis being run.
    remaining_suspected_commit_positions (list): An list of commit positions in
        ascending order determined by heuristic analysis that have not yet been
        analyzed.
    previously_run_commit_position (int): The most previously-run commit
        position to determine it's pass rate.
    next_bisect_commit_position (int): The commit position bisect suggests to
        run against already-ran data points.

  Returns:
    (int): The next commit position (int) to run, either from heuristic results
        or bisect.
    ([int]): The remainining list of suspected commit positions to try.
  """
  if remaining_suspected_commit_positions:
    # Try the suggested commit position first.
    next_suspected_commit_position = remaining_suspected_commit_positions[0]
    previously_run_data_point = (
        analysis.FindMatchingDataPointWithCommitPosition(
            previously_run_commit_position))
    assert previously_run_data_point

    lower_flake_threshold = (analysis.algorithm_parameters.get(
        'try_job_rerun', {}).get('lower_flake_threshold',
                                 flake_constants.DEFAULT_LOWER_FLAKE_THRESHOLD))
    upper_flake_threshold = (analysis.algorithm_parameters.get(
        'try_job_rerun', {}).get('upper_flake_threshold',
                                 flake_constants.DEFAULT_UPPER_FLAKE_THRESHOLD))

    if not lookback_algorithm.IsStable(previously_run_data_point.pass_rate,
                                       lower_flake_threshold,
                                       upper_flake_threshold):
      # The suggested results are in ascending order and run before bisect. Thus
      # the previously-ran data point will always have a smaller commit
      # position than those in remaining_suspected_ommit_positions. If it was
      # identified already to be flaky, all subsequent suggested commit
      # positions will be flaky too and need not be tried. Fallback to
      # next_bisect_commit_position, which has already been computed to be the
      # bisection of the lowest flaky commit position
      # (previously_run_commit_position) and latest preceding stable commit
      # position. remaining_suspected_commit_positions can safely be discarded.
      return next_bisect_commit_position, []

    return (next_suspected_commit_position,
            remaining_suspected_commit_positions[1:])

  # Fallback to the bisect/exponential lookback point.
  return next_bisect_commit_position, []


class NextCommitPositionPipeline(BasePipeline):
  """Returns the next index in the blame list to run a try job on."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, urlsafe_flake_analysis_key, urlsafe_try_job_key,
          remaining_suspected_commit_positions, previously_run_commit_position,
          lower_bound_commit_position, upper_bound_commit_position,
          user_specified_iterations, cache_name, dimensions, rerun):
    """Determines the next commit position to run a try job on.

    Args:
      urlsafe_flake_analysis_key (str): The url-safe key to the corresponding
          flake analysis that triggered this pipeline.
      urlsafe_try_job_key (str): The url-safe key to the try job that was just
          run.
      remaining_suspected_commit_positions ([int]): A list of commit positions
          not yet analyzed but may aid in finding the culprit faster than
          bisecting.
      lower_bound_commit_position (int): The lower bound commit position to
          consider when deciding the next run point number.
      upper_bound_commit_position (int): The upper bound commit position to
          consider when deciding the next run point number.
      rerun (bool): Whether or not a full rerun of this analysis is being
          requested.
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
      flake_analysis.Update(
          try_job_status=analysis_status.ERROR,
          error=try_job_data.error,
          end_time=time_util.GetUTCNow())
      duration = flake_analysis.end_time - flake_analysis.start_time
      monitoring.analysis_durations.add(duration.total_seconds(),
                                        {'type': 'flake',
                                         'result': 'error'})
      return

    algorithm_settings = flake_analysis.algorithm_parameters.get(
        'try_job_rerun', {})

    # Figure out what commit position to trigger the next try job on, if any.
    suspected_build_data_point = flake_analysis.GetDataPointOfSuspectedBuild()
    data_points = _GetNormalizedTryJobDataPoints(flake_analysis,
                                                 lower_bound_commit_position,
                                                 upper_bound_commit_position)

    next_bisect_commit_position, suspected_commit_position = (
        lookback_algorithm.GetNextRunPointNumber(
            data_points,
            algorithm_settings,
            lower_bound_run_point_number=lower_bound_commit_position,
            upper_bound_run_point_number=upper_bound_commit_position))

    if suspected_commit_position is not None:  # Finished.
      data_points_within_range = (
          flake_analysis.GetDataPointsWithinCommitPositionRange(
              lower_bound_commit_position, upper_bound_commit_position))
      confidence_score = _GetSuspectedCommitConfidenceScore(
          flake_analysis, suspected_commit_position, data_points_within_range)
      culprit_revision = suspected_build_data_point.GetRevisionAtCommitPosition(
          suspected_commit_position)
      culprit = UpdateCulprit(flake_analysis.key.urlsafe(), culprit_revision,
                              suspected_commit_position)
      flake_analysis.Update(
          culprit_urlsafe_key=culprit.key.urlsafe(),
          confidence_in_culprit=confidence_score,
          try_job_status=analysis_status.COMPLETED,
          end_time=time_util.GetUTCNow())
      duration = flake_analysis.end_time - flake_analysis.start_time
      monitoring.analysis_durations.add(duration.total_seconds(), {
          'type': 'flake',
          'result': 'completed',
      })

      yield SendNotificationForFlakeCulpritPipeline(urlsafe_flake_analysis_key)
      return

    flake_analysis.LogInfo('Remaining suspected commit positions: %r' %
                           remaining_suspected_commit_positions)
    (next_commit_position,
     remaining_suspects) = _GetNextCommitPositionAndRemainingSuspects(
         flake_analysis, remaining_suspected_commit_positions,
         previously_run_commit_position, next_bisect_commit_position)

    next_revision = suspected_build_data_point.GetRevisionAtCommitPosition(
        next_commit_position)

    assert next_revision is not None

    pipeline_job = RecursiveFlakeTryJobPipeline(
        urlsafe_flake_analysis_key, remaining_suspects, next_commit_position,
        next_revision, lower_bound_commit_position, upper_bound_commit_position,
        user_specified_iterations, cache_name, dimensions, rerun)
    # Disable attribute 'target' defined outside __init__ pylint warning,
    # because pipeline generates its own __init__ based on run function.
    pipeline_job.target = (  # pylint: disable=W0201
        appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND))
    pipeline_job.start()
