# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common.findit_http_client import FinditHttpClient
from common import constants
from gae_libs import appengine_util
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from model.flake.flake_swarming_task import FlakeSwarmingTask
from waterfall import buildbot
from waterfall import swarming_util
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)


def ScheduleFlakeSwarmingTask(master_name, builder_name, build_number,
                              step_name, test_name, iterations_to_rerun,
                              queue_name):
  pipeline_job = TriggerFlakeSwarmingTaskServicePipeline(
      master_name, builder_name, build_number, step_name, test_name,
      iterations_to_rerun)

  # pylint: disable=W0201
  pipeline_job.target = appengine_util.GetTargetNameForModule(
      constants.WATERFALL_BACKEND)

  step_metadata = buildbot.GetStepLog(master_name, builder_name, build_number,
                                      step_name,
                                      FinditHttpClient(), 'step_metadata')

  if swarming_util.BotsAvailableForTask(step_metadata):
    # Sufficient bots are avialable, trigger the swarming task immediately.
    pipeline_job.start(queue_name=queue_name)
  else:
    # Not enough bots are available. Queue this task and start it off peak hours
    # when there are more resources available.
    pipeline_job.start(
        queue_name=queue_name, eta=swarming_util.GetETAToStartAnalysis(False))


class TriggerFlakeSwarmingTaskServicePipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, step_name, test_name,
          iterations_to_rerun):
    task = FlakeSwarmingTask.Get(master_name, builder_name, build_number,
                                 step_name, test_name)
    assert task

    with pipeline.InOrder():
      task_id = yield TriggerFlakeSwarmingTaskPipeline(
          master_name, builder_name, build_number, step_name, [test_name],
          iterations_to_rerun)
      yield ProcessFlakeSwarmingTaskResultPipeline(
          master_name, builder_name, build_number, step_name, task_id, None,
          test_name, None)
