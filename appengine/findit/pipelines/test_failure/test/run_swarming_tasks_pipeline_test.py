# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from dto.run_swarming_tasks_input import RunSwarmingTasksInput
from dto.run_swarming_task_parameters import RunSwarmingTaskParameters
from gae_libs.pipelines import pipeline_handlers
from pipelines.test_failure.run_swarming_tasks_pipeline import (
    RunSwarmingTasksPipeline)
from pipelines.test_failure.run_test_swarming_task_pipeline import (
    RunTestSwarmingTaskPipeline)
from services.test_failure import test_swarming
from waterfall.test import wf_testcase


class RunSwarmingTasksPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      test_swarming,
      'GetFirstTimeTestFailuresToRunSwarmingTasks',
      return_value={
          'step1': ['test1']
      })
  def testRunSwarmingTasksPipeline(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 31

    build_key = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number
    }
    wrapper_params_json = {
        'build_key': build_key,
        'heuristic_result': {},
        'force': False
    }

    sub_params1_json = {
        'build_key': build_key,
        'step_name': 'step1',
        'tests': ['test1']
    }
    sub_params1 = RunSwarmingTaskParameters.FromSerializable(sub_params1_json)
    self.MockAsynchronousPipeline(RunTestSwarmingTaskPipeline, sub_params1,
                                  True)

    wrapper_params = RunSwarmingTasksInput.FromSerializable(wrapper_params_json)
    p = RunSwarmingTasksPipeline(wrapper_params)
    p.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    mock_fn.assert_called_once_with(wrapper_params)
