# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from common import appengine_util
from common import constants
from common.pipeline_wrapper import BasePipeline

from model import analysis_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)


class RecursiveFlakePipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, run_build_number, step_name,
          test_name, master_build_number, queue_name=constants.DEFAULT_QUEUE):
    # Call trigger pipeline (flake style).
    task_id = yield TriggerFlakeSwarmingTaskPipeline(master_name, builder_name,
                          run_build_number, step_name, [test_name])
    # Pass the trigger pipeline into a process pipeline.
    test_result_future = yield ProcessFlakeSwarmingTaskResultPipeline(
        master_name, builder_name, run_build_number,
        step_name, task_id, master_build_number, test_name)
    yield NextBuildNumberPipeline(
        master_name, builder_name, master_build_number,
        step_name, test_name, test_result_future, queue_name)

class NextBuildNumberPipeline(BasePipeline):
  # Arguments number differs from overridden method - pylint: disable=W0221
  # Unused argument - pylint: disable=W0613
  def run(self, master_name, builder_name, master_build_number, step_name,
          test_name, test_result_future, queue_name):
    # Get MasterFlakeAnalysis success list corresponding to parameters.
    master = MasterFlakeAnalysis.Get(master_name, builder_name,
                                     master_build_number, step_name, test_name)
    # Figure out what build_number we should call, if any
    # This is a placeholder for testing:
    next_run = False
    if len(master.build_numbers) < 10:
      # TODO(caiw): Develop algorithm to optimize this.
      next_run = min(master.build_numbers) - 10
    if next_run:
      pipeline_job = RecursiveFlakePipeline(
          master_name, builder_name, next_run, step_name, test_name,
          master_build_number)
      #pylint: disable=W0201
      pipeline_job.target = appengine_util.GetTargetNameForModule(
          constants.WATERFALL_BACKEND)
      pipeline_job.start(queue_name=queue_name)
