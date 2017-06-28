# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common import constants
from gae_libs import appengine_util
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from libs import time_util
from model import result_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.wf_swarming_task import WfSwarmingTask
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.flake import confidence
from waterfall.flake import lookback_algorithm
from waterfall.flake.initialize_flake_try_job_pipeline import (
    InitializeFlakeTryJobPipeline)
from waterfall.flake.lookback_algorithm import NormalizedDataPoint
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)

_DEFAULT_MINIMUM_CONFIDENCE_SCORE = 0.6
_DEFAULT_MAX_BUILD_NUMBERS = 500
_DEFAULT_ITERATIONS_TO_RERUN = 100

_BASE_COUNT_DOWN_SECONDS = 2 * 60
# Tries to start the RecursiveFlakePipeline on peak hours at most 5 times.
_MAX_RETRY_TIMES = 5

_MINIMUM_NUMBER_BOT = 5
_MINIMUM_PERCENT_BOT = 0.1

# In order not to hog resources on the swarming server, set the timeout to a
# non-configurable 3 hours.
_ONE_HOUR_IN_SECONDS = 60 * 60
_MAX_TIMEOUT_SECONDS = 3 * _ONE_HOUR_IN_SECONDS


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
  else:
    # Clear info about the last attempted swarming task since it will be stored
    # in the data point.
    analysis.last_attempted_swarming_task_id = None
    analysis.last_attempted_build_number = None

  analysis.put()


def _IsSwarmingTaskSufficientForCacheHit(flake_swarming_task,
                                         number_of_iterations):
  """Determines whether or not a swarming task is sufficient for a cache hit.

  Args:
    flake_swarming_task (FlakeSwarmingTask): The task to be examined.
    number_of_iterations (int): The minimum number of iterations
      flake_swarming_task needs to have run in order to count as a cache hit.

  Returns:
    A bool whether or not flake_swarming_task is sufficient to be a cache hit.
  """
  # Swarming task must exist.
  if not flake_swarming_task:
    return False

  # Cached swarming task's numbers must be thorough enough.
  if flake_swarming_task.tries < number_of_iterations:
    return False

  # Cached swarming task must either be scheduled, in progress, or completed.
  return flake_swarming_task.status in [
      analysis_status.PENDING, analysis_status.RUNNING,
      analysis_status.COMPLETED
  ]


def _GetListOfNearbyBuildNumbers(preferred_run_build_number,
                                 lower_bound_build_number,
                                 upper_bound_build_number, maximum_threshold):
  """Gets a list of numbers within range near preferred_run_build_number.

  Args:
    preferred_run_build_number (int): Assumed to be a positive number.
    lower_bound_build_number (int): The smallest build number allowed, or None.
    upper_bound_build_number (int): The largest build number allowed, or None.
    maximum_threshold (int): A non-negative number for how far in either
    direction to look.

  Returns:
    A list of nearby numbers within maximum_threshold before and after
    preferred_run_build_number, ordered by closest to farthest. For example, if
    preferred_run_build_number is 1000 and maximum_threshold is 2, return
    [1000, 999, 1001, 998, 1002].
  """
  lower_bound = lower_bound_build_number or 0
  upper_bound = (upper_bound_build_number
                 if upper_bound_build_number is not None else
                 preferred_run_build_number + maximum_threshold)
  nearby_build_numbers = [preferred_run_build_number]

  for i in range(1, maximum_threshold + 1):
    if preferred_run_build_number - i >= lower_bound:
      nearby_build_numbers.append(preferred_run_build_number - i)

    if preferred_run_build_number + i <= upper_bound:
      nearby_build_numbers.append(preferred_run_build_number + i)

  return nearby_build_numbers


def _GetBestBuildNumberToRun(master_name, builder_name,
                             preferred_run_build_number, step_name, test_name,
                             lower_bound_build_number, upper_bound_build_number,
                             step_size, number_of_iterations):
  """Finds the optimal nearby swarming task build number to use for a cache hit.

  Builds are searched back looking for something either already completed or in
  progress. Completed builds are returned immediately, whereas for those in
  progress the closer the build number is to the original, the higher priority
  it is given.

  Args:
    master_name (str): The name of the master for this flake analysis.
    builder_name (str): The name of the builder for this flake analysis.
    preferred_run_build_number (int): The originally-requested build number to
        run the swarming task on.
    lower_bound_build_number (int): The smallest build number to include.
    upper_bound_build_number (int): The largest build number to include.
    step_name (str): The name of the step to run swarming on.
    test_name (str): The name of the test to run swarming on.
    step_size (int): The distance of the last preferred build number that was
      called on this analysis. Used for determining the lookback threshold.
    number_of_iterations (int): The number of iterations being requested for
      the swarming task that is to be performed. Used to determine a sufficient
      cache hit.

  Returns:
    build_number (int): The best build number to analyze for this iteration of
      the flake analysis.
  """
  # Looks forward or backward up to half of step_size.
  possibly_cached_build_numbers = _GetListOfNearbyBuildNumbers(
      preferred_run_build_number, lower_bound_build_number,
      upper_bound_build_number, step_size / 2)
  candidate_build_number = None
  candidate_flake_swarming_task_status = None

  for build_number in possibly_cached_build_numbers:
    cached_flake_swarming_task = FlakeSwarmingTask.Get(
        master_name, builder_name, build_number, step_name, test_name)
    sufficient = _IsSwarmingTaskSufficientForCacheHit(
        cached_flake_swarming_task, number_of_iterations)

    if sufficient:
      if cached_flake_swarming_task.status == analysis_status.COMPLETED:
        # Found a nearby swarming task that's already done.
        return build_number

      # Keep searching, but keeping this candidate in mind. Pending tasks are
      # considered, but running tasks are given higher priority.
      # TODO(lijeffrey): A further optimization can be to pick the swarming
      # task with the earliest ETA.
      if (candidate_build_number is None or
          (candidate_flake_swarming_task_status == analysis_status.PENDING and
           cached_flake_swarming_task.status == analysis_status.RUNNING)):
        # Either no previous candidate or a better candidate was found.
        candidate_build_number = build_number
        candidate_flake_swarming_task_status = cached_flake_swarming_task.status

  # No cached build nearby deemed adequate could be found.
  return candidate_build_number or preferred_run_build_number


def _CanEstimateExecutionTimeFromReferenceSwarmingTask(swarming_task):
  return (swarming_task and not swarming_task.error and
          swarming_task.started_time and swarming_task.completed_time and
          swarming_task.tests_statuses and swarming_task.parameters and
          swarming_task.parameters.get('iterations_to_rerun'))


def _GetHardTimeoutSeconds(master_name, builder_name, reference_build_number,
                           step_name, iterations_to_rerun):
  flake_settings = waterfall_config.GetCheckFlakeSettings()
  flake_swarming_settings = flake_settings.get('swarming_rerun', {})
  reference_task = WfSwarmingTask.Get(master_name, builder_name,
                                      reference_build_number, step_name)

  if _CanEstimateExecutionTimeFromReferenceSwarmingTask(reference_task):
    delta = reference_task.completed_time - reference_task.started_time
    execution_time = delta.total_seconds()
    number_of_tests = len(reference_task.tests_statuses)
    number_of_iterations = reference_task.parameters['iterations_to_rerun']
    time_per_test_per_iteration = (execution_time /
                                   (number_of_iterations * number_of_tests))
    estimated_execution_time = (
        time_per_test_per_iteration * iterations_to_rerun)
  else:
    # Use default settings if the reference task is unavailable or malformed.
    estimated_execution_time = flake_swarming_settings.get(
        'default_per_iteration_timeout_seconds', 60) * iterations_to_rerun

  # To account for variance and pending time, use a factor of 2x estimated
  # execution time.
  estimated_time_needed = estimated_execution_time * 2

  return min(
      max(estimated_time_needed, _ONE_HOUR_IN_SECONDS), _MAX_TIMEOUT_SECONDS)


def _GetIterationsToRerun(user_specified_iterations, analysis):
  return user_specified_iterations or analysis.algorithm_parameters.get(
      'swarming_rerun', {}).get('iterations_to_rerun',
                                _DEFAULT_ITERATIONS_TO_RERUN)


class RecursiveFlakePipeline(BasePipeline):

  def __init__(self,
               analysis_urlsafe_key,
               preferred_run_build_number,
               lower_bound_build_number,
               upper_bound_build_number,
               user_specified_iterations,
               step_metadata=None,
               manually_triggered=False,
               use_nearby_neighbor=False,
               step_size=0,
               retries=0,
               force=False):
    """Pipeline to determine and analyze the regression range of a flaky test.

    Args:
      analysis_urlsafe_key (str): A url-safe key corresponding to a
          MasterFlakeAnalysis for which this analysis represents.
      preferred_run_build_number (int): The build number the check flake
          algorithm should perform a swarming rerun on, but may be overridden to
          use the results of a nearby neighbor if use_nearby_neighbor is True.
      lower_bound_build_number (int): The earliest build number to check. Pass
          None to allow the look back algorithm to determine how far back to
          look.
      upper_bound_build_number (int): The latest build number to include in the
          analysis. Pass None to allow the algorithm to determine where to start
          the backward search from.
      user_specified_iterations (int): The number of iterations to rerun the
          test as specified by the user. If None, Findit will fallback to what
          is in the analysis' algorithm parameters.
      step_metadata (dict): Step_metadata for the test.
      manually_triggered (bool): True if the analysis is from manual request,
          like by a Chromium sheriff.
      use_nearby_neighbor (bool): Whether the optimization for using the
          swarming results of a nearby build number, if available, should be
          used in place of triggering a new swarming task on
          preferred_run_build_number.
      step_size (int): The difference in build numbers since the last call to
          RecursiveFlakePipeline to determine the bounds for how far a nearby
          build's swarming task results should be used. Only relevant if
          use_nearby_neighbor is True.
      retries (int): Number of retries of this pipeline. If reties exceeds the
          _MAX_RETRY_TIMES, start this pipeline off peak hours.

    Returns:
      A dict of lists for reliable/flaky tests.
    """
    super(RecursiveFlakePipeline, self).__init__(
        analysis_urlsafe_key, preferred_run_build_number,
        lower_bound_build_number, upper_bound_build_number,
        user_specified_iterations, step_metadata, manually_triggered,
        use_nearby_neighbor, step_size, retries, force)
    self.analysis_urlsafe_key = ndb.Key(urlsafe=analysis_urlsafe_key)
    analysis = self.analysis_urlsafe_key.get()
    assert analysis
    self.master_name = analysis.master_name
    self.builder_name = analysis.builder_name
    self.preferred_run_build_number = preferred_run_build_number
    self.lower_bound_build_number = lower_bound_build_number
    self.upper_bound_build_number = upper_bound_build_number
    self.user_specified_iterations = user_specified_iterations
    self.triggering_build_number = analysis.build_number
    self.step_name = analysis.step_name
    self.test_name = analysis.test_name
    self.version_number = analysis.version_number
    self.step_metadata = step_metadata
    self.manually_triggered = manually_triggered
    self.use_nearby_neighbor = use_nearby_neighbor
    self.step_size = step_size
    self.retries = retries
    self.force = force

  def _StartOffPSTPeakHours(self, *args, **kwargs):
    """Starts the pipeline off PST peak hours if not triggered manually."""
    kwargs['eta'] = swarming_util.GetETAToStartAnalysis(self.manually_triggered)
    self.start(*args, **kwargs)

  def _RetryWithDelay(self, *args, **kwargs):
    """Trys to start the pipeline later."""
    kwargs['countdown'] = kwargs.get('retries', 1) * _BASE_COUNT_DOWN_SECONDS
    self.start(*args, **kwargs)

  def _BotsAvailableForTask(self, step_metadata):
    """Check if there are available bots for this task's dimensions."""
    if not step_metadata:
      return False

    minimum_number_of_available_bots = (
        waterfall_config.GetSwarmingSettings().get(
            'minimum_number_of_available_bots', _MINIMUM_NUMBER_BOT))
    minimum_percentage_of_available_bots = (
        waterfall_config.GetSwarmingSettings().get(
            'minimum_percentage_of_available_bots', _MINIMUM_PERCENT_BOT))
    dimensions = step_metadata.get('dimensions')
    bot_counts = swarming_util.GetSwarmingBotCounts(dimensions,
                                                    HttpClientAppengine())

    total_count = bot_counts.get('count') or -1
    available_count = bot_counts.get('available', 0)
    available_rate = float(available_count) / total_count

    return (available_count > minimum_number_of_available_bots and
            available_rate > minimum_percentage_of_available_bots)

  def _LogUnexpectedAbort(self):
    if not self.was_aborted:
      return

    analysis = self.analysis_urlsafe_key.get()
    if analysis and not analysis.completed:
      analysis.status = analysis_status.ERROR
      analysis.result_status = None
      analysis.error = analysis.error or {
          'error': 'RecursiveFlakePipeline was aborted unexpectedly',
          'message': 'RecursiveFlakePipeline was aborted unexpectedly'
      }
      analysis.put()

  def finalized(self):
    self._LogUnexpectedAbort()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self,
          analysis_urlsafe_key,
          preferred_run_build_number,
          lower_bound_build_number,
          upper_bound_build_number,
          user_specified_iterations,
          step_metadata=None,
          manually_triggered=False,
          use_nearby_neighbor=False,
          step_size=0,
          retries=0,
          force=False):
    """Pipeline to determine and analyze the regression range of a flaky test.

    Args:
      analysis_urlsafe_key (str): A url-safe key corresponding to a
          MasterFlakeAnalysis for which this analysis represents.
      preferred_run_build_number (int): The build number the check flake
          algorithm should perform a swarming rerun on, but may be overridden to
          use the results of a nearby neighbor if use_nearby_neighbor is True.
      lower_bound_build_number (int): The earliest build number to check. Pass
          None to allow the look back algorithm to determine how far back to
          look.
      upper_bound_build_number (int): The latest build number to include in the
          analysis. Pass None to allow the algorithm to determine where to start
          the backward search from.
      user_specified_iterations (int): The number of iterations each swarming
          task should run, as supplied by the user. If None is specified,
          Findit will decide how many iterations to rerun.
      step_metadata (dict): Step_metadata for the test.
      manually_triggered (bool): True if the analysis is from manual request,
          like by a Chromium sheriff.
      use_nearby_neighbor (bool): Whether the optimization for using the
          swarming results of a nearby build number, if available, should be
          used in place of triggering a new swarming task on
          preferred_run_build_number.
      step_size (int): The difference in build numbers since the last call to
          RecursiveFlakePipeline to determine the bounds for how far a nearby
          build's swarming task results should be used. Only relevant if
          use_nearby_neighbor is True.
      retries (int): Number of retries of this pipeline. If reties exceeds the
          _MAX_RETRY_TIMES, start this pipeline off peak hours.
      force (bool): Force this build to run from scratch,
          a rerun by an admin will trigger this.

    Returns:
      A dict of lists for reliable/flaky tests.
    """
    # If retries has not exceeded max count and there are available bots,
    # we can start the analysis.
    can_start_analysis = (self._BotsAvailableForTask(step_metadata)
                          if retries <= _MAX_RETRY_TIMES else True)

    if can_start_analysis:
      # Bots are available or pipeline starts off peak hours, trigger the task.
      analysis = self.analysis_urlsafe_key.get()
      analysis.Update(
          start_time=time_util.GetUTCNow(), status=analysis_status.RUNNING)

      iterations = _GetIterationsToRerun(user_specified_iterations, analysis)
      hard_timeout_seconds = _GetHardTimeoutSeconds(
          self.master_name, self.builder_name, self.triggering_build_number,
          self.step_name, iterations)
      actual_run_build_number = _GetBestBuildNumberToRun(
          self.master_name, self.builder_name, preferred_run_build_number,
          self.step_name, self.test_name, lower_bound_build_number,
          upper_bound_build_number, step_size,
          iterations) if use_nearby_neighbor else preferred_run_build_number

      task_id = yield TriggerFlakeSwarmingTaskPipeline(
          self.master_name,
          self.builder_name,
          actual_run_build_number,
          self.step_name, [self.test_name],
          iterations,
          hard_timeout_seconds,
          force=force)

      with pipeline.InOrder():
        yield ProcessFlakeSwarmingTaskResultPipeline(
            self.master_name, self.builder_name, actual_run_build_number,
            self.step_name, task_id, self.triggering_build_number,
            self.test_name, analysis.version_number)
        yield NextBuildNumberPipeline(
            analysis.key.urlsafe(),
            actual_run_build_number,
            lower_bound_build_number,
            upper_bound_build_number,
            user_specified_iterations,
            step_metadata=step_metadata,
            use_nearby_neighbor=use_nearby_neighbor,
            manually_triggered=manually_triggered)
    else:
      retries += 1

      pipeline_job = RecursiveFlakePipeline(
          analysis_urlsafe_key,
          preferred_run_build_number,
          lower_bound_build_number,
          upper_bound_build_number,
          user_specified_iterations,
          step_metadata=step_metadata,
          manually_triggered=manually_triggered,
          use_nearby_neighbor=use_nearby_neighbor,
          step_size=step_size,
          retries=retries)

      # Disable attribute 'target' defined outside __init__ pylint warning,
      # because pipeline generates its own __init__ based on run function.
      pipeline_job.target = (  # pylint: disable=W0201
          appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND))

      if retries > _MAX_RETRY_TIMES:
        pipeline_job._StartOffPSTPeakHours(queue_name=self.queue_name or
                                           constants.DEFAULT_QUEUE)
        logging.info('Retrys exceed max count, RecursiveFlakePipeline on '
                     'MasterFlakeAnalysis %s/%s/%s/%s/%s will start off peak '
                     'hour', self.master_name, self.builder_name,
                     self.triggering_build_number, self.step_name,
                     self.test_name)
      else:
        pipeline_job._RetryWithDelay(queue_name=self.queue_name or
                                     constants.DEFAULT_QUEUE)
        countdown = retries * _BASE_COUNT_DOWN_SECONDS
        logging.info('No available swarming bots, RecursiveFlakePipeline on '
                     'MasterFlakeAnalysis %s/%s/%s/%s/%s will be tried after'
                     '%d seconds', self.master_name, self.builder_name,
                     self.triggering_build_number, self.step_name,
                     self.test_name, countdown)


def _NormalizeDataPoints(data_points):
  """Converts a list of data points into a list of normalized data points.

    Data points need to be normalized before passing into lookback_algorithm.py,
    which is agnostic to build numbers and commit positions.

  Args:
    data_points (list): A list of DataPoint objects.

  Returns:
    A list of NormalizedDataPoint objects based on data_points.
  """
  normalized_data_points = [(NormalizedDataPoint(data_point.build_number,
                                                 data_point.pass_rate,
                                                 data_point.has_valid_artifact))
                            for data_point in data_points]
  return sorted(
      normalized_data_points, key=lambda k: k.run_point_number, reverse=True)


def _UpdateIterationsToRerun(analysis, iterations_to_rerun):
  if not iterations_to_rerun or not analysis.algorithm_parameters:
    return

  analysis.algorithm_parameters['swarming_rerun'][
      'iterations_to_rerun'] = iterations_to_rerun

  analysis.algorithm_parameters['try_job_rerun'][
      'iterations_to_rerun'] = iterations_to_rerun


def _UpdateAnalysisWithSwarmingTaskError(flake_swarming_task, analysis):
  # Report the last flake swarming task's error that it encountered.
  logging.error('Error in Swarming task')

  error = flake_swarming_task.error or {
      'error': 'Swarming task failed',
      'message': 'The last swarming task did not complete as expected'
  }
  analysis.Update(status=analysis_status.ERROR, error=error,
                  end_time=time_util.GetUTCNow())


def _GetEarliestBuildNumber(lower_bound_build_number, triggering_build_number,
                            algorithm_settings):
  if lower_bound_build_number is not None:
    return lower_bound_build_number

  max_build_numbers_to_look_back = algorithm_settings.get(
      'max_build_numbers_to_look_back', _DEFAULT_MAX_BUILD_NUMBERS)

  return max(0, triggering_build_number - max_build_numbers_to_look_back)


def _GetLatestBuildNumber(upper_bound_build_number, triggering_build_number):
  return upper_bound_build_number or triggering_build_number


def _IsFinished(next_build_number, earliest_build_number, latest_build_number,
                iterations_to_rerun):
  """Determines whether or not to stop checking more build numbers.

    An analysis at the build number level is complete if the next suggested
    build number has already been run, is beyond the lower bound, or determined
    to be stable as indicated by iterations_to_rerun returned by
    lookback_algorithm.

  Args:
    next_build_number (int): The proposed next build number to run.
    earliest_build_number (int): The lower bound build number to compare.
    latest_build_number (int): The upper bound build number to compare.
    iterations_to_rerun (int): The number of iterations the lookback algorithm
        proposes to run, or None indicating it should bail out.
  """
  return ((next_build_number < earliest_build_number or
           next_build_number >= latest_build_number) and
          not iterations_to_rerun)


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


def _GetBuildConfidenceScore(suspected_build, data_points):
  """Gets a confidence score for a suspected build.

  Args:
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

  return confidence.SteppinessForBuild(data_points, suspected_build)


class NextBuildNumberPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  # Unused argument - pylint: disable=W0613
  def run(self,
          analysis_urlsafe_key,
          current_build_number,
          lower_bound_build_number,
          upper_bound_build_number,
          user_specified_iterations,
          step_metadata=None,
          use_nearby_neighbor=False,
          manually_triggered=False):
    """Pipeline for determining the build number to analyze.

    Args:
      analysis_urlsafe_key (str): The url-safe key to the MasterFlakeAnalysis
          being analyzed.
      current_build_number (int): The build number that has just been analyzed.
      lower_bound_build_number (int): The earliest build number to check, or
          None if not specified.
      upper_bound_build_number (int): The latest build number to check, or None
          if not specified.
      user_specified_iterations (int): The number of iterations to rerun as
          specified by the user. If None is passed, Findit will determine the
          number of iterations to rerun.
      step_metadata (dict): Step metadata for the test.
      use_nearby_neighbor (bool): Whether or not use existing swarming reruns
          for builds near the requested build number to analyze.
      manually_triggered (bool): Whether or not this analysis was triggered by
          a human user.
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis
    master_name = analysis.master_name
    builder_name = analysis.builder_name
    triggering_build_number = analysis.build_number
    step_name = analysis.step_name
    test_name = analysis.test_name

    flake_swarming_task = FlakeSwarmingTask.Get(
        master_name, builder_name, current_build_number, step_name, test_name)

    # Don't call another pipeline if we fail.
    if flake_swarming_task.status == analysis_status.ERROR:
      # TODO(lijeffrey): Another neighboring swarming task may be needed in this
      # one's place instead of failing altogether.
      _UpdateAnalysisWithSwarmingTaskError(flake_swarming_task, analysis)
      yield UpdateFlakeBugPipeline(analysis.key.urlsafe())
      return

    analysis.Update(
        algorithm_parameters=waterfall_config.GetCheckFlakeSettings())
    algorithm_settings = analysis.algorithm_parameters.get('swarming_rerun')

    # Figure out what build_number to trigger a swarming rerun on next, if any.
    data_points_within_range = analysis.GetDataPointsWithinBuildNumberRange(
        lower_bound_build_number, upper_bound_build_number)
    data_points = _NormalizeDataPoints(data_points_within_range)
    next_build_number, suspected_build, updated_iterations_to_rerun = (
        lookback_algorithm.GetNextRunPointNumber(data_points,
                                                 algorithm_settings))

    if updated_iterations_to_rerun and user_specified_iterations is None:
      # The lookback algorithm determined the build needs to be rerun with more
      # iterations.
      _UpdateIterationsToRerun(analysis, updated_iterations_to_rerun)
      analysis.RemoveDataPointWithBuildNumber(next_build_number)
      analysis.put()

    earliest_build_number = _GetEarliestBuildNumber(
        lower_bound_build_number, triggering_build_number, algorithm_settings)
    latest_build_number = _GetLatestBuildNumber(upper_bound_build_number,
                                                triggering_build_number)

    if _IsFinished(next_build_number, earliest_build_number,
                   latest_build_number, updated_iterations_to_rerun):
      build_confidence_score = _GetBuildConfidenceScore(
          suspected_build, data_points_within_range)

      user_specified_range = _UserSpecifiedRange(lower_bound_build_number,
                                                 upper_bound_build_number)

      _UpdateAnalysisResults(
          analysis,
          suspected_build,
          analysis_status.COMPLETED,
          None,
          build_confidence_score=build_confidence_score)

      with pipeline.InOrder():
        yield InitializeFlakeTryJobPipeline(analysis_urlsafe_key,
                                            user_specified_iterations,
                                            user_specified_range)
        yield UpdateFlakeBugPipeline(analysis_urlsafe_key)
