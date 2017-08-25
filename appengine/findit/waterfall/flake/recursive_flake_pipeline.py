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
from waterfall.flake.determine_true_pass_rate_pipeline import (
    DetermineTruePassRatePipeline)
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

    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis
    algorithm_settings = analysis.algorithm_parameters.get('swarming_rerun')
    analysis.Update(
        start_time=time_util.GetUTCNow(), status=analysis_status.RUNNING)
    logging.info('%s/%s/%s/%s/%s Running with analysis algorithm settings %s',
                 analysis.master_name, analysis.builder_name,
                 analysis.build_number, analysis.step_name, analysis.test_name,
                 algorithm_settings)

    # If retries has not exceeded max count and there are available bots,
    # we can start the analysis.
    can_start_analysis = (swarming_util.BotsAvailableForTask(step_metadata) if
                          retries <= flake_constants.MAX_RETRY_TIMES else True)
    if can_start_analysis:
      # Bots are available or pipeline starts off peak hours,
      # trigger the task.
      logging.info(('%s/%s/%s/%s/%s Bots are avialable to analyze build %s'),
                   analysis.master_name, analysis.builder_name,
                   analysis.build_number, analysis.step_name,
                   analysis.test_name, preferred_run_build_number)

      with pipeline.InOrder():
        yield DetermineTruePassRatePipeline(analysis_urlsafe_key,
                                            preferred_run_build_number, force)

        next_build_number = yield NextBuildNumberPipeline(
            analysis.key.urlsafe(), preferred_run_build_number,
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
          previous_build_number=preferred_run_build_number,
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
