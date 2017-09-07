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
  # TODO(wylieb): Figure out if convergence percent should be configurable.
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


def _CheckSwarmingTaskForError(analysis, flake_swarming_task):
  """Check the flake swarming task for error, and increment the model.

  Args:
    analysis (MasterFlakeAnalysis): The current flake analysis.
    flake_swarming_task (FlakeSwarmingTask): The swarming task to examine.
  """
  if (flake_swarming_task and
      flake_swarming_task.status == analysis_status.ERROR):
    analysis.LogInfo(
        'Swarming task attempt in error. Analysis already had %d errors' %
        analysis.swarming_task_attempts_for_build)
    analysis.swarming_task_attempts_for_build += 1
    analysis.put()


def _UpdateAnalysisWithSwarmingTaskError(flake_swarming_task, analysis):
  # Report the last flake swarming task's error that it encountered.
  logging.error('Error in Swarming task %s', flake_swarming_task)

  error = flake_swarming_task.error or {
      'error': 'Swarming task failed',
      'message': 'The last swarming task did not complete as expected'
  }
  analysis.Update(
      status=analysis_status.ERROR, error=error, end_time=time_util.GetUTCNow())


def _CalculateRunParametersForSwarmingTask(analysis, target_iterations):
  """Calculates and returns the iterations and timeout for swarming tasks

  Args:
    analysis (MasterFlakeAnalysis): The analysis we're getting parameters for.
    target_iterations (int): The number of iterations we'd like to run.

  Returns:
      ((int) iterations, (int) timeout) Tuple containing the iterations to run
          for this swarming task, and the timeout for that task.abs
  """
  timeout_per_test = flake_analysis_util.EstimateSwarmingIterationTimeout(
      analysis)
  iterations_for_task = (
      flake_analysis_util.CalculateNumberOfIterationsToRunWithinTimeout(
          analysis, target_iterations, timeout_per_test))
  time_for_task_seconds = timeout_per_test * iterations_for_task
  return (iterations_for_task, time_for_task_seconds)


def _GetTargetIterations(iterations_completed, max_iterations_to_rerun):
  """Returns the number of iterations that should be run for a swarming task.

    Args:
        iterations_completed (int): the number of iterations completed at the
            current build.
        max_iterations_to_rerun (int): the maximum number of iterations to run
            for any given build.
    Returns:
      (int) The number of iterations that should be run for a swarming task.
  """
  # TODO(757920): Factor DEFAULT_ITERATIONS_PER_TASK out to config.
  if iterations_completed and max_iterations_to_rerun:
    return min(max_iterations_to_rerun - iterations_completed,
               flake_constants.DEFAULT_ITERATIONS_PER_TASK)
  return flake_constants.DEFAULT_ITERATIONS_PER_TASK


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
          previous_pass_rate=None,
          previous_iterations_completed=None,
          rerun=False):
    """Pipeline to find the true pass rate of a test at a given build number.

    Args:
      analysis_urlsafe_key (str): A url-safe key corresponding to a
          MasterFlakeAnalysis for which this analysis represents.
      build_number (int): The build number to run.
      previous_pass_rate (float): The pass rate from a previous run of this
          pipeline.
      previous_iterations_completed (int): Number of iterations completed up
          to before the last swarming task.
      rerun (bool): Force this build to run from scratch,
          a rerun by an admin will trigger this.
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

    _CheckSwarmingTaskForError(analysis, flake_swarming_task)

    # If there are too many swarming tasks that fail for a certain build_number
    # bail out completely.
    # TODO(757911): Factor out MAX_SWARMING_TASK_RETRIES_PER_BUILD to config.
    # TODO(757923): Add analysis-level swarming task retry limit.
    if (analysis.swarming_task_attempts_for_build >=
        flake_constants.MAX_SWARMING_TASK_RETRIES_PER_BUILD):
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

    # How many iterations, and the timeout for the task.
    target_iterations = _GetTargetIterations(iterations_completed,
                                             max_iterations_to_rerun)
    (iterations_for_task,
     time_for_task_seconds) = _CalculateRunParametersForSwarmingTask(
         analysis, target_iterations)

    analysis.LogInfo('Running %d iterations with a %d second timeout' %
                     (iterations_for_task, time_for_task_seconds))

    # If the swarming task already exists, reset it so no caching occurs.
    if flake_swarming_task:
      flake_swarming_task.successes = None
      flake_swarming_task.tries = None
      flake_swarming_task.put()

    # Run swarming task, aggregate results and recurse
    with pipeline.InOrder():
      yield AnalyzeFlakeForBuildNumberPipeline(
          analysis_urlsafe_key,
          build_number,
          iterations_for_task,
          time_for_task_seconds,
          rerun=rerun)
      yield DetermineTruePassRatePipeline(
          analysis_urlsafe_key,
          build_number,
          previous_pass_rate=pass_rate,
          previous_iterations_completed=iterations_completed,
          rerun=rerun)
