# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common import constants
from gae_libs import appengine_util
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from libs import time_util
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.wf_swarming_task import WfSwarmingTask
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.flake import flake_analysis_util
from waterfall.flake import flake_constants
from waterfall.flake.next_build_number_pipeline import NextBuildNumberPipeline
from waterfall.flake.save_last_attempted_swarming_task_id_pipeline import (
    SaveLastAttemptedSwarmingTaskIdPipeline)
from waterfall.flake.update_flake_analysis_data_points_pipeline import (
    UpdateFlakeAnalysisDataPointsPipeline)
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)
from waterfall.flake.finish_build_analysis_pipeline import (
    FinishBuildAnalysisPipeline)


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
    estimated_execution_time = int(
        (time_per_test_per_iteration * iterations_to_rerun))
  else:
    # Use default settings if the reference task is unavailable or malformed.
    estimated_execution_time = flake_swarming_settings.get(
        'per_iteration_timeout_seconds', 60) * iterations_to_rerun

  # To account for variance and pending time, use a factor of 2x estimated
  # execution time.
  estimated_time_needed = estimated_execution_time * 2

  return min(
      max(estimated_time_needed, flake_constants.ONE_HOUR_IN_SECONDS),
      flake_constants.MAX_TIMEOUT_SECONDS)


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
               previous_build_number=None,
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
      previous_build_number (int): The number of the build that was previously
          analyzed. This is used to determine the step size.
      retries (int): Number of retries of this pipeline. If reties exceeds the
          MAX_RETRY_TIMES, start this pipeline off peak hours.

    Returns:
      A dict of lists for reliable/flaky tests.
    """
    super(RecursiveFlakePipeline, self).__init__(
        analysis_urlsafe_key, preferred_run_build_number,
        lower_bound_build_number, upper_bound_build_number,
        user_specified_iterations, step_metadata, manually_triggered,
        use_nearby_neighbor, previous_build_number, retries, force)
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
    self.previous_build_number = previous_build_number
    self.retries = retries
    self.force = force

  def _StartOffPSTPeakHours(self, *args, **kwargs):
    """Starts the pipeline off PST peak hours if not triggered manually."""
    kwargs['eta'] = swarming_util.GetETAToStartAnalysis(self.manually_triggered)
    self.start(*args, **kwargs)

  def _RetryWithDelay(self, *args, **kwargs):
    """Trys to start the pipeline later."""
    kwargs['countdown'] = kwargs.get(
        'retries', 1) * flake_constants.BASE_COUNT_DOWN_SECONDS
    self.start(*args, **kwargs)

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
          previous_build_number=None,
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
      previous_build_number (int): The build number that was previously
          analyzed. This is used to determine the step size.
      retries (int): Number of retries of this pipeline. If reties exceeds the
          MAX_RETRY_TIMES, start this pipeline off peak hours.
      force (bool): Force this build to run from scratch,
          a rerun by an admin will trigger this.

    Returns:
      A dict of lists for reliable/flaky tests.
    """
    # If the preferred_run_build_number is None, that means that the build-level
    # flake analysis is complete, we should clean up and start the next pipeline
    if preferred_run_build_number is None:
      yield FinishBuildAnalysisPipeline(
          analysis_urlsafe_key, lower_bound_build_number,
          upper_bound_build_number, user_specified_iterations, force)
      return
    if previous_build_number is None:
      previous_build_number = preferred_run_build_number

    # Don't trust incoming variables to be ints because they're coming
    # from FlakeAnalysisRequest which intakes from http. Cast and assert
    # on current/previous build numbers to fail fast.
    preferred_run_build_number = int(preferred_run_build_number)
    previous_build_number = int(previous_build_number)
    step_size = previous_build_number - preferred_run_build_number

    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis
    algorithm_settings = analysis.algorithm_parameters.get('swarming_rerun')
    analysis.Update(
        start_time=time_util.GetUTCNow(), status=analysis_status.RUNNING)
    logging.info('%s/%s/%s/%s/%s Running with analysis algorithm settings %s',
                 analysis.master_name, analysis.builder_name,
                 analysis.build_number, analysis.step_name, analysis.test_name,
                 algorithm_settings)

    iterations = flake_analysis_util.GetIterationsToRerun(
        user_specified_iterations, analysis)
    hard_timeout_seconds = _GetHardTimeoutSeconds(
        self.master_name, self.builder_name, self.triggering_build_number,
        self.step_name, iterations)
    actual_run_build_number = _GetBestBuildNumberToRun(
        self.master_name, self.builder_name, preferred_run_build_number,
        self.step_name, self.test_name, lower_bound_build_number,
        upper_bound_build_number, step_size,
        iterations) if use_nearby_neighbor else preferred_run_build_number

    # If retries has not exceeded max count and there are available bots,
    # we can start the analysis.
    can_start_analysis = (swarming_util.BotsAvailableForTask(step_metadata) if
                          retries <= flake_constants.MAX_RETRY_TIMES else True)
    if can_start_analysis:
      # Bots are available or pipeline starts off peak hours,
      # trigger the task.
      logging.info(('%s/%s/%s/%s/%s Bots are avialable to analyze build '
                    '%s with %s iterations and %dsec timeout'),
                   analysis.master_name, analysis.builder_name,
                   analysis.build_number, analysis.step_name,
                   analysis.test_name, actual_run_build_number, iterations,
                   hard_timeout_seconds)

      task_id = yield TriggerFlakeSwarmingTaskPipeline(
          self.master_name,
          self.builder_name,
          actual_run_build_number,
          self.step_name, [self.test_name],
          iterations,
          hard_timeout_seconds,
          force=force)

      with pipeline.InOrder():
        yield SaveLastAttemptedSwarmingTaskIdPipeline(
            analysis_urlsafe_key, task_id, actual_run_build_number)

        yield ProcessFlakeSwarmingTaskResultPipeline(
            self.master_name, self.builder_name, actual_run_build_number,
            self.step_name, task_id, self.triggering_build_number,
            self.test_name, analysis.version_number)

        yield UpdateFlakeAnalysisDataPointsPipeline(analysis_urlsafe_key,
                                                    actual_run_build_number)

        next_build_number = yield NextBuildNumberPipeline(
            analysis.key.urlsafe(), actual_run_build_number,
            lower_bound_build_number, upper_bound_build_number,
            user_specified_iterations)

      yield RecursiveFlakePipeline(
          analysis_urlsafe_key,
          next_build_number,
          lower_bound_build_number,
          upper_bound_build_number,
          user_specified_iterations,
          step_metadata=step_metadata,
          manually_triggered=manually_triggered,
          use_nearby_neighbor=use_nearby_neighbor,
          previous_build_number=actual_run_build_number,
          retries=retries,
          force=force)
    else:  # Can't start analysis, reschedule.
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
          previous_build_number=previous_build_number,
          retries=retries,
          force=force)

      # Disable attribute 'target' defined outside __init__ pylint warning,
      # because pipeline generates its own __init__ based on run function.
      pipeline_job.target = (  # pylint: disable=W0201
          appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND))

      if retries > flake_constants.MAX_RETRY_TIMES:
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
        countdown = retries * flake_constants.BASE_COUNT_DOWN_SECONDS
        logging.info('No available swarming bots, RecursiveFlakePipeline on '
                     'MasterFlakeAnalysis %s/%s/%s/%s/%s will be tried after'
                     '%d seconds', self.master_name, self.builder_name,
                     self.triggering_build_number, self.step_name,
                     self.test_name, countdown)
