# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common import constants
from libs import analysis_status
from libs import time_util
from gae_libs import appengine_util
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from model.flake.flake_swarming_task import FlakeSwarmingTask
from waterfall import monitoring
from waterfall import swarming_util
from waterfall.flake import flake_analysis_util
from waterfall.flake import flake_constants
from waterfall.flake.analyze_flake_for_build_number_pipeline import (
    AnalyzeFlakeForBuildNumberPipeline)
from waterfall.flake.save_last_attempted_swarming_task_id_pipeline import (
    SaveLastAttemptedSwarmingTaskIdPipeline)
from waterfall.flake.update_flake_analysis_data_points_pipeline import (
    UpdateFlakeAnalysisDataPointsPipeline)
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)


def _HasPassRateConverged(pass_rate_a, pass_rate_b):
  """Determines if the pass rate has converged to an acceptable level.

  Args:
    pass_rate_a (float): pass rate at one point in time.
    pass_rate_b (float): pass rate at a different point in time.

  Returns:
    True if there are sufficient iterations to determine convergence
  """
  return (pass_rate_a is not None and pass_rate_b is not None and
          abs(pass_rate_a - pass_rate_b) < flake_constants.CONVERGENCE_PERCENT)


def _MinimumIterationsReached(iterations_completed_a, iterations_completed_b):
  """Determines if the minimum iterations have been reached for this build.

  iterations_completed_a should have happened before iterations_completed_b.

  Args:
    iterations_completed_a (int): number of iterations completed for
        point a.
    iterations_completed_b (int): number of iterations completed for
        point b.
  Returns:
    True if the minimum iterations have been reached and
    iterations_completed_a < iterations_completed_b.
  """
  return (iterations_completed_a is not None and
          iterations_completed_b is not None and iterations_completed_a >
          flake_constants.MINIMUM_ITERATIONS_REQUIRED_FOR_CONVERGENCE and
          iterations_completed_b > iterations_completed_a)


def _GetSwarmingTaskErrorCode(analysis, flake_swarming_task,
                              previous_pass_rate):
  """Check the flake swarming task for error, and increment the model.

  Args:
    analysis (MasterFlakeAnalysis): The current flake analysis.
    flake_swarming_task (FlakeSwarmingTask): The swarming task to examine.
    previous_pass_rate (float): The pass rate from a previous iteration of
        determinetruepassratepipeline, used to determine if this is the first
        iteration of the pipeline.

  Return:
    (int) Error code of the swarming task error if any, else None.
  """
  if previous_pass_rate is None:
    return None

  if flake_swarming_task and flake_swarming_task.error:
    analysis.LogInfo(
        'Swarming task attempt ended in error. Analysis already had %d errors' %
        analysis.swarming_task_attempts_for_build)
    analysis.swarming_task_attempts_for_build += 1
    analysis.put()
    return flake_swarming_task.error.get('code')
  return None


def _UpdateAnalysisWithSwarmingTaskError(flake_swarming_task, analysis):
  # Report the last flake swarming task's error that it encountered.
  logging.error('Error in Swarming task %s', flake_swarming_task)

  error = flake_swarming_task.error or {
      'error': 'Swarming task failed',
      'message': 'The last swarming task did not complete as expected'
  }

  analysis.Update(
      status=analysis_status.ERROR, error=error, end_time=time_util.GetUTCNow())
  duration = analysis.end_time - analysis.start_time
  monitoring.analysis_durations.add(duration.total_seconds(), {
      'type': 'flake',
      'result': 'error',
  })


def _GetTimeoutForTask(analysis, timeout_per_test, iterations_for_task):
  """Returns the timeout for a swarming task.

  Returns either timeout_per_test * iterations_for_task or the default timeout
  for a swarming task (whichever is greater).

  Args:
    analysis (MasterFlakeAnalysis): The analysis we're getting parameters for.
    timeout_per_test (int): timeout per test derived from the previous data
        points.
    iterations_for_task (int): total number of iterations for the task derived
        from the previous data points.
  Returns:
    (int) timeout for a swarming task.
  """
  return max(timeout_per_test * iterations_for_task,
             analysis.algorithm_parameters.get('swarming_rerun', {}).get(
                 'timeout_per_swarming_task_seconds',
                 flake_constants.DEFAULT_TIMEOUT_PER_SWARMING_TASK_SECONDS))


def _CalculateRunParametersForSwarmingTask(analysis, build_number):
  """Calculates and returns the iterations and timeout for swarming tasks

  Args:
    analysis (MasterFlakeAnalysis): The analysis we're getting parameters for.
    build_number (int): The current build number running.

  Returns:
      ((int) iterations, (int) timeout) Tuple containing the iterations to run
          for this swarming task, and the timeout for that task.abs
  """
  timeout_per_test = flake_analysis_util.EstimateSwarmingIterationTimeout(
      analysis, build_number)
  iterations_for_task = (
      flake_analysis_util.CalculateNumberOfIterationsToRunWithinTimeout(
          analysis, timeout_per_test))
  time_for_task_seconds = _GetTimeoutForTask(analysis, timeout_per_test,
                                             iterations_for_task)

  # If we're above the iteration maximum, then bring it down. Don't touch
  # the timeout, swarming will return after the iterations are complete.
  max_iterations_per_task = analysis.algorithm_parameters.get(
      'swarming_rerun', {}).get('max_iterations_per_task',
                                flake_constants.MAX_ITERATIONS_PER_TASK)
  iterations_for_task = min(max_iterations_per_task, iterations_for_task)
  return iterations_for_task, time_for_task_seconds


def _TestDoesNotExist(pass_rate_a, pass_rate_b):
  """Check if the test exists, used before checking for convergence.

  Args:
    pass_rate_a (float): pass rate at one point in time.
    pass_rate_b (float): pass rate at a different point in time.

  Returns:
    True if the pass rates indicate that the tests exist, False otherwise.
  """
  return (pass_rate_a == flake_constants.PASS_RATE_TEST_NOT_FOUND or
          pass_rate_b == flake_constants.PASS_RATE_TEST_NOT_FOUND)


class DetermineTruePassRatePipeline(BasePipeline):
  """Determines the true pass rate at a build_number."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self,
          analysis_urlsafe_key,
          build_number,
          rerun,
          previous_pass_rate=None,
          previous_iterations_completed=None):
    """Pipeline to find the true pass rate of a test at a given build number.

    Args:
      analysis_urlsafe_key (str): A url-safe key corresponding to a
          MasterFlakeAnalysis for which this analysis represents.
      build_number (int): The build number to run.
      rerun (bool): Force this build to run from scratch,
          a rerun by an admin will trigger this.
      previous_pass_rate (float): The pass rate from a previous run of this
          pipeline.
      previous_iterations_completed (int): Number of iterations completed up
          to before the last swarming task.
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    max_iterations_to_rerun = (analysis.algorithm_parameters.get(
        'max_iterations_to_rerun',
        flake_constants.DEFAULT_MAX_ITERATIONS_TO_RERUN))

    # Extract pass rate and iterations information before running the task.
    data_point_for_build_number = (
        analysis.FindMatchingDataPointWithBuildNumber(build_number))
    pass_rate = (data_point_for_build_number.pass_rate
                 if data_point_for_build_number else None)
    iterations_completed = (data_point_for_build_number.iterations
                            if data_point_for_build_number else 0)

    # If max iterations have been performed, and the pass rate hasn't converged
    # just move on to the next build number.
    if iterations_completed >= max_iterations_to_rerun:
      analysis.LogInfo(
          'Max iterations reached for build number %d' % build_number)

      # Reset analysis after the build number has been run.
      analysis.swarming_task_attempts_for_build = 0
      analysis.put()

      return

    flake_swarming_task = FlakeSwarmingTask.Get(
        analysis.master_name, analysis.builder_name, build_number,
        analysis.step_name, analysis.test_name)

    # Only get the error code if looking at tasks this pipeline has executed.
    swarming_error_code = _GetSwarmingTaskErrorCode(
        analysis, flake_swarming_task, previous_pass_rate)

    # If there are too many swarming tasks that fail for a certain build_number
    # bail out completely.
    max_swarming_retries_per_build = (analysis.algorithm_parameters.get(
        'swarming_task_retries_per_build',
        flake_constants.MAX_SWARMING_TASK_RETRIES_PER_BUILD))
    if (analysis.swarming_task_attempts_for_build >=
        max_swarming_retries_per_build):
      assert flake_swarming_task
      _UpdateAnalysisWithSwarmingTaskError(flake_swarming_task, analysis)
      update_flake_bug_pipeline = UpdateFlakeBugPipeline(analysis_urlsafe_key)
      update_flake_bug_pipeline.target = appengine_util.GetTargetNameForModule(
          constants.WATERFALL_BACKEND)
      update_flake_bug_pipeline.start(queue_name=self.queue_name or
                                      constants.DEFAULT_QUEUE)
      analysis.LogError('Swarming task %s ended in error after %d attempts.' %
                        (flake_swarming_task,
                         analysis.swarming_task_attempts_for_build))
      analysis.Update(swarming_task_attempts_for_build=0)

      raise pipeline.Abort()

    analysis.LogInfo(
        'Completed total %s iterations at build number %s. previous pass rate '
        'is %s, pass rate is %s' % (iterations_completed, build_number,
                                    previous_pass_rate, pass_rate))

    if _TestDoesNotExist(previous_pass_rate, pass_rate):
      analysis.LogInfo('No test found at build number %d' % build_number)
      return
    elif (_MinimumIterationsReached(previous_iterations_completed,
                                    iterations_completed) and
          _HasPassRateConverged(previous_pass_rate, pass_rate)):
      analysis.LogInfo(
          'Pass rate has converged for build number %d.' % build_number)

      # Reset analysis after the build number has been run.
      analysis.swarming_task_attempts_for_build = 0
      analysis.put()
      return

    (iterations_for_task,
     time_for_task_seconds) = _CalculateRunParametersForSwarmingTask(
         analysis, build_number)

    if swarming_error_code == swarming_util.TIMED_OUT:
      # If the previous run timed out, run a smaller, fixed, number of
      # iterations so it's liekly to finish.
      iterations_for_task = (analysis.algorithm_parameters.get(
          'iterations_to_run_after_timeout',
          flake_constants.DEFAULT_ITERATIONS_TO_RUN_AFTER_TIMEOUT))

    analysis.LogInfo('Running %d iterations with a %d second timeout' %
                     (iterations_for_task, time_for_task_seconds))

    # If the swarming task already exists, delete it so no caching occurs.
    if flake_swarming_task:
      flake_swarming_task.key.delete()

    # Run swarming task, aggregate results and recurse
    with pipeline.InOrder():
      yield AnalyzeFlakeForBuildNumberPipeline(
          analysis_urlsafe_key, build_number, iterations_for_task,
          time_for_task_seconds, rerun)
      yield DetermineTruePassRatePipeline(
          analysis_urlsafe_key,
          build_number,
          rerun,
          previous_pass_rate=pass_rate,
          previous_iterations_completed=iterations_completed)
