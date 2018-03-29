# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.run_swarming_tasks_input import RunSwarmingTasksInput
from dto.run_swarming_task_parameters import RunSwarmingTaskParameters
from gae_libs.pipelines import GeneratorPipeline
from pipelines.test_failure.run_test_swarming_task_pipeline import (
    RunTestSwarmingTaskPipeline)
from services.test_failure import test_swarming


class RunSwarmingTasksPipeline(GeneratorPipeline):
  """Wrapper pipeline that spawns swarming task pipelines for new failed
    test steps in a build.

  This pipeline will get all first time failed test steps that have not been
  deflaked then run swarming reruns for each step.
  """
  input_type = RunSwarmingTasksInput

  def RunImpl(self, run_swarming_tasks_input):
    steps = test_swarming.GetFirstTimeTestFailuresToRunSwarmingTasks(
        run_swarming_tasks_input)
    for step_name, base_tests in steps.iteritems():
      run_swarming_task_params = RunSwarmingTaskParameters(
          build_key=run_swarming_tasks_input.build_key,
          step_name=step_name,
          tests=base_tests)
      yield RunTestSwarmingTaskPipeline(run_swarming_task_params)
