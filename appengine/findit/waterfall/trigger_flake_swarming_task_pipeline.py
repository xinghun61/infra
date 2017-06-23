# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.flake.flake_swarming_task import FlakeSwarmingTask
from waterfall import monitoring
from waterfall import waterfall_config
from waterfall.trigger_base_swarming_task_pipeline import (
    TriggerBaseSwarmingTaskPipeline)


class TriggerFlakeSwarmingTaskPipeline(TriggerBaseSwarmingTaskPipeline):
  """A pipeline to check if selected tests of a step are flaky.

  This pipeline only supports test steps that run on Swarming and support the
  gtest filter.
  """

  def _GetArgs(self, master_name, builder_name, build_number, step_name, tests):
    test_name = tests[0]  # Only one test per pipeline.
    return (master_name, builder_name, build_number, step_name, test_name)

  # pylint: disable=arguments-differ
  def _GetSwarmingTask(self, master_name, builder_name, build_number, step_name,
                       test_name):
    # Get the appropriate kind of Swarming Task (Flake).
    swarming_task = FlakeSwarmingTask.Get(master_name, builder_name,
                                          build_number, step_name, test_name)
    return swarming_task

  # pylint: disable=arguments-differ
  def _CreateSwarmingTask(self, master_name, builder_name, build_number,
                          step_name, test_name):
    # Create the appropriate kind of Swarming Task (Flake).
    swarming_task = FlakeSwarmingTask.Create(master_name, builder_name,
                                             build_number, step_name, test_name)
    return swarming_task

  def _GetIterationsToRerun(self):
    flake_settings = waterfall_config.GetCheckFlakeSettings()
    swarming_rerun_settings = flake_settings.get('swarming_rerun', {})
    return swarming_rerun_settings.get('iterations_to_rerun', 100)

  def _OnTaskTriggered(self):  # pragma: no cover.
    monitoring.swarming_tasks.increment({
        'operation': 'trigger',
        'category': 'identify-regression-range'
    })

  def _GetAdditionalTags(self):  # pragma: no cover.
    return ['purpose:identify-regression-range']
