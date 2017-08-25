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
    True if the pass rates are not None, and the absolute difference between
    them is within a convergence percent difference.
  """
  # TODO(wylieb): Figure out if convergence percent should be configurable.
  return (pass_rate_a is not None and pass_rate_b is not None and
          abs(pass_rate_a - pass_rate_b) < flake_constants.CONVERGENCE_PERCENT)


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


class DetermineTruePassRatePipeline(BasePipeline):
  """Determines the true pass rate at a build_number."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, analysis_urlsafe_key, build_number, rerun=False):
    """Pipeline to find the true pass rate of a test at a given build number.

    Args:
      analysis_urlsafe_key (str): A url-safe key corresponding to a
          MasterFlakeAnalysis for which this analysis represents.
      build_number (int): The build number to run.
      rerun (bool): Force this build to run from scratch,
          a rerun by an admin will trigger this.
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    max_iterations_to_rerun = (analysis.algorithm_parameters.get(
        'max_iterations_to_rerun',
        flake_constants.DEFAULT_MAX_ITERATIONS_TO_RERUN))
    data_point_for_build_number = (
        analysis.FindMatchingDataPointWithBuildNumber(build_number))
    iterations_completed = (data_point_for_build_number.iterations
                            if data_point_for_build_number else 0)

    # If max iterations have been performed, and the pass rate hasn't converged
    # just move on to the next build number.
    if iterations_completed >= max_iterations_to_rerun:
      logging.info('%s/%s/%s/%s/%s Max iterations reached for build number %d',
                   analysis.master_name, analysis.builder_name,
                   analysis.build_number, analysis.step_name,
                   analysis.test_name, build_number)

      # Reset analysis after the build number has been run.
      analysis.swarming_task_attempts_for_build = 0
      analysis.put()

      return

    # If there are too many swarming tasks that fail for a certain build_number
    # bail out completely.
    # TODO(757911): Factor out MAX_SWARMING_TASK_RETRIES_PER_BUILD to config.
    # TODO(757923): Add analysis-level swarming task retry limit.
    if (analysis.swarming_task_attempts_for_build >=
        flake_constants.MAX_SWARMING_TASK_RETRIES_PER_BUILD):
      flake_swarming_task = FlakeSwarmingTask.Get(
          analysis.master_name, analysis.builder_name, build_number,
          analysis.step_name, analysis.test_name)
      assert flake_swarming_task
      _UpdateAnalysisWithSwarmingTaskError(flake_swarming_task, analysis)
      update_flake_bug_pipeline = UpdateFlakeBugPipeline(analysis_urlsafe_key)
      update_flake_bug_pipeline.target = appengine_util.GetTargetNameForModule(
          constants.WATERFALL_BACKEND)
      update_flake_bug_pipeline.start(queue_name=self.queue_name or
                                      constants.DEFAULT_QUEUE)
      logging.warning('Swarming task %s ended in error after %d attempts.',
                      flake_swarming_task,
                      analysis.swarming_task_attempts_for_build)
      raise pipeline.Abort()

    # Before we run the swarming task, get the pass rate.
    data_point_for_build_number = (
        analysis.FindMatchingDataPointWithBuildNumber(build_number))
    pass_rate_before = (data_point_for_build_number.pass_rate
                        if data_point_for_build_number else None)

    # Get the number of iterations and the timeout for the main swarming task.
    # TODO(757920): Factor DEFAULT_ITERATIONS_PER_TASK out to config.
    target_iterations = min(max_iterations_to_rerun - iterations_completed,
                            flake_constants.DEFAULT_ITERATIONS_PER_TASK)
    (iterations_for_task,
     time_for_task_seconds) = _CalculateRunParametersForSwarmingTask(
         analysis, target_iterations)

    logging.info(
        '%s/%s/%s/%s/%s Running %d iterations with a %d second timeout',
        analysis.master_name, analysis.builder_name, analysis.build_number,
        analysis.step_name, analysis.test_name, iterations_for_task,
        time_for_task_seconds)

    # Run swarming task, and aggregate results.
    flake_run_pipeline = yield AnalyzeFlakeForBuildNumberPipeline(
        analysis_urlsafe_key,
        build_number,
        iterations_for_task,
        time_for_task_seconds,
        rerun=rerun)

    with pipeline.After(flake_run_pipeline):
      flake_swarming_task = FlakeSwarmingTask.Get(
          analysis.master_name, analysis.builder_name, build_number,
          analysis.step_name, analysis.test_name)
      assert flake_swarming_task

      if flake_swarming_task.status == analysis_status.ERROR:
        analysis.swarming_task_attempts_for_build += 1
        analysis.put()

      # After we run the swarming task, get the pass rate.
      data_point_for_build_number = (
          analysis.FindMatchingDataPointWithBuildNumber(build_number))
      pass_rate_after = (data_point_for_build_number.pass_rate
                         if data_point_for_build_number else None)

      if pass_rate_after is not None:
        logging.info('%s/%s/%s/%s/%s Completed run of %d iterations at '
                     'build number %d. Pass rate is %.2f', analysis.master_name,
                     analysis.builder_name, analysis.build_number,
                     analysis.step_name, analysis.test_name,
                     iterations_for_task, build_number, pass_rate_after)
      else:
        logging.info('%s/%s/%s/%s/%s Failed run of %d iterations at '
                     'build number %d.', analysis.master_name,
                     analysis.builder_name, analysis.build_number,
                     analysis.step_name, analysis.test_name,
                     iterations_for_task, build_number)

      if _HasPassRateConverged(pass_rate_before, pass_rate_after):
        logging.info('%s/%s/%s/%s/%s pass rate has converged for build number'
                     ' %d.', analysis.master_name, analysis.builder_name,
                     analysis.build_number, analysis.step_name,
                     analysis.test_name, build_number)

        # Reset analysis after the build number has been run.
        analysis.swarming_task_attempts_for_build = 0
        analysis.put()

        return
      else:
        logging.info('%s/%s/%s/%s/%s pass rate has not converged for'
                     'build number %d, rerunning pipeline.',
                     analysis.master_name, analysis.builder_name,
                     analysis.build_number, analysis.step_name,
                     analysis.test_name, build_number)
        yield DetermineTruePassRatePipeline(
            analysis_urlsafe_key, build_number, rerun=rerun)
