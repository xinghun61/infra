# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from waterfall.flake import flake_analysis_util
from waterfall.flake import flake_constants
from waterfall.flake.save_last_attempted_swarming_task_id_pipeline import (
    SaveLastAttemptedSwarmingTaskIdPipeline)
from waterfall.flake.update_flake_analysis_data_points_pipeline import (
    UpdateFlakeAnalysisDataPointsPipeline)
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)


class AnalyzeFlakeForBuildNumberPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self,
          analysis_urlsafe_key,
          build_number,
          iterations,
          timeout,
          rerun=False):
    """Pipeline to analyze one build number of a flake analysis.

    Args:
      analysis_urlsafe_key (str): A url-safe key corresponding to a
          MasterFlakeAnalysis for which this analysis represents.
      build_number (int): The build number to run.
      iterations (int): The number of iterations each swarming
          task should run, as supplied by the user. If None is specified,
          Findit will decide how many iterations to rerun.
      timeout (int): The number of seconds for the swarming task timeout.
      rerun (bool): Force this build to run from scratch,
          a rerun by an admin will trigger this.
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    with pipeline.InOrder():
      task_id = yield TriggerFlakeSwarmingTaskPipeline(
          analysis.master_name,
          analysis.builder_name,
          build_number,
          analysis.step_name, [analysis.test_name],
          iterations_to_rerun=iterations,
          hard_timeout_seconds=timeout,
          force=rerun)
      yield SaveLastAttemptedSwarmingTaskIdPipeline(analysis_urlsafe_key,
                                                    task_id, build_number)
      yield ProcessFlakeSwarmingTaskResultPipeline(
          analysis.master_name, analysis.builder_name, build_number,
          analysis.step_name, task_id, analysis.build_number,
          analysis.test_name, analysis.version_number)
      yield UpdateFlakeAnalysisDataPointsPipeline(analysis_urlsafe_key,
                                                  build_number)
