# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging
import mock

from common import acl
from common import constants
from gae_libs.pipelines import pipeline_handlers
from model.flake.flake_swarming_task import FlakeSwarmingTask
from waterfall import buildbot
from waterfall import swarming_util
from waterfall.flake import trigger_flake_swarming_task_service_pipeline
from waterfall.flake.trigger_flake_swarming_task_service_pipeline import (
    TriggerFlakeSwarmingTaskServicePipeline)
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.test import wf_testcase
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)


class TriggerFlakeSwarmingTaskServicePipelineTest(
    wf_testcase.WaterfallTestCase):

  app_module = pipeline_handlers._APP

  @mock.patch.object(acl, 'CanTriggerNewAnalysis', return_value=True)
  @mock.patch.object(buildbot, 'GetStepLog', return_value={})
  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=True)
  def testScheduleFlakeSwarmingTaskBotsAvailable(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    iterations_to_rerun = 100

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.queued = True
    task.put()

    queue_name = 'queue'
    with mock.patch.object(TriggerFlakeSwarmingTaskServicePipeline,
                           'start') as mocked_trigger_task:
      trigger_flake_swarming_task_service_pipeline.ScheduleFlakeSwarmingTask(
          master_name, builder_name, build_number, step_name, test_name,
          iterations_to_rerun, queue_name)
      mocked_trigger_task.assert_called_with(queue_name=queue_name)

  @mock.patch.object(acl, 'CanTriggerNewAnalysis', return_value=True)
  @mock.patch.object(buildbot, 'GetStepLog', return_value={})
  @mock.patch.object(swarming_util, 'BotsAvailableForTask', return_value=False)
  @mock.patch.object(
      swarming_util, 'GetETAToStartAnalysis', return_value=datetime(2017, 7, 5))
  def testScheduleFlakeSwarmingTaskOffPeakHours(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    iterations_to_rerun = 100

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.queued = True
    task.put()

    queue_name = 'queue'
    with mock.patch.object(TriggerFlakeSwarmingTaskServicePipeline,
                           'start') as mocked_trigger_task:
      trigger_flake_swarming_task_service_pipeline.ScheduleFlakeSwarmingTask(
          master_name, builder_name, build_number, step_name, test_name,
          iterations_to_rerun, queue_name)
      mocked_trigger_task.assert_called_with(
          queue_name=queue_name, eta=datetime(2017, 7, 5))

  def testTriggerFlakeSwarmingTaskServicePipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    task_id = 'task_id'
    iterations_to_rerun = 100

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.queued = True
    task.put()

    self.MockPipeline(
        TriggerFlakeSwarmingTaskPipeline,
        task_id,
        expected_args=[
            master_name, builder_name, build_number, step_name, [test_name],
            iterations_to_rerun
        ],
        expected_kwargs={})
    self.MockPipeline(
        ProcessFlakeSwarmingTaskResultPipeline,
        '',
        expected_args=[
            master_name, builder_name, build_number, step_name, task_id, None,
            test_name, None
        ],
        expected_kwargs={})
    pipeline_job = TriggerFlakeSwarmingTaskServicePipeline(
        master_name, builder_name, build_number, step_name, test_name,
        iterations_to_rerun)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
