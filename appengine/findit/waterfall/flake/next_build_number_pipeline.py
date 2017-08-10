# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import constants
from libs import analysis_status
from libs import time_util
from gae_libs import appengine_util
from gae_libs.pipeline_wrapper import BasePipeline, pipeline
from google.appengine.ext import ndb
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import waterfall_config
from waterfall.flake import flake_analysis_util, lookback_algorithm
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline


def _UpdateAnalysisWithSwarmingTaskError(flake_swarming_task, analysis):
  # Report the last flake swarming task's error that it encountered.
  logging.error('Error in Swarming task %s', flake_swarming_task)

  error = flake_swarming_task.error or {
      'error': 'Swarming task failed',
      'message': 'The last swarming task did not complete as expected'
  }
  analysis.Update(
      status=analysis_status.ERROR, error=error, end_time=time_util.GetUTCNow())


class NextBuildNumberPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  # Unused argument - pylint: disable=W0613
  def run(self, analysis_urlsafe_key, current_build_number,
          lower_bound_build_number, upper_bound_build_number,
          user_specified_iterations):
    """Pipeline for determining the next build number to analyze.

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

    Returns:
      (int) Next build number to run.
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    master_name = analysis.master_name
    builder_name = analysis.builder_name
    triggering_build_number = analysis.build_number
    step_name = analysis.step_name
    test_name = analysis.test_name

    logging.info('%s/%s/%s/%s/%s completed analysis on build number %s',
                 master_name, builder_name, triggering_build_number, step_name,
                 test_name, current_build_number)

    flake_swarming_task = FlakeSwarmingTask.Get(
        analysis.master_name, analysis.builder_name, current_build_number,
        analysis.step_name, analysis.test_name)

    # Abort analysis if a swarming task had an error.
    if flake_swarming_task.status == analysis_status.ERROR:
      _UpdateAnalysisWithSwarmingTaskError(flake_swarming_task, analysis)
      update_flake_bug_pipeline = UpdateFlakeBugPipeline(analysis_urlsafe_key)
      update_flake_bug_pipeline.target = appengine_util.GetTargetNameForModule(
          constants.WATERFALL_BACKEND)
      update_flake_bug_pipeline.start(queue_name=constants.DEFAULT_QUEUE)
      logging.warning('Swarming task %s ended in error.', flake_swarming_task)
      raise pipeline.Abort()

    analysis.Update(
        algorithm_parameters=waterfall_config.GetCheckFlakeSettings())

    # Figure out what build_number to trigger a swarming rerun on next, if any.
    data_points_within_range = analysis.GetDataPointsWithinBuildNumberRange(
        lower_bound_build_number, upper_bound_build_number)
    logging.info(('%s/%s/%s/%s/%s Determining next data point to analyze based '
                  'on %s'), master_name, builder_name, triggering_build_number,
                 step_name, test_name, data_points_within_range)
    data_points = flake_analysis_util.NormalizeDataPointsByBuildNumber(
        data_points_within_range)
    next_build_number, suspected_build, updated_iterations_to_rerun = (
        lookback_algorithm.GetNextRunPointNumber(
            data_points, analysis.algorithm_parameters.get('swarming_rerun')))
    logging.info(('%s/%s/%s/%s/%s next_build_number: %s, suspected_build: %s '
                  'updated_iterations_to_rerun: %s'), master_name, builder_name,
                 triggering_build_number, step_name, test_name,
                 next_build_number, suspected_build,
                 updated_iterations_to_rerun)

    if updated_iterations_to_rerun and user_specified_iterations is None:
      # The lookback algorithm determined the build needs to be rerun with more
      # iterations.
      flake_analysis_util.UpdateIterationsToRerun(analysis,
                                                  updated_iterations_to_rerun)
      analysis.RemoveDataPointWithBuildNumber(next_build_number)
      analysis.put()

    logging.info(('%s/%s/%s/%s/%s Starting RecursiveFlakePipeline on the '
                  'next build number: %s'), master_name, builder_name,
                 triggering_build_number, step_name, test_name,
                 next_build_number)

    return next_build_number
