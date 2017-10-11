# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import monitoring
from model.wf_swarming_task import WfSwarmingTask
from waterfall import waterfall_config
from waterfall.trigger_base_swarming_task_pipeline import (
    TriggerBaseSwarmingTaskPipeline)


class TriggerSwarmingTaskPipeline(TriggerBaseSwarmingTaskPipeline):
  """A pipeline to trigger a Swarming task to re-run selected tests of a step.

  This pipeline only supports test steps that run on Swarming and support the
  gtest filter.
  """

  def _GetArgs(self, master_name, builder_name, build_number, step_name, _):
    return master_name, builder_name, build_number, step_name

  # Arguments number differs from overridden method - pylint: disable=W0221
  def _GetSwarmingTask(self, master_name, builder_name, build_number,
                       step_name):
    return WfSwarmingTask.Get(master_name, builder_name, build_number,
                              step_name)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def _CreateSwarmingTask(self, master_name, builder_name, build_number,
                          step_name):
    return WfSwarmingTask.Create(master_name, builder_name, build_number,
                                 step_name)

  def _GetIterationsToRerun(self):
    return waterfall_config.GetSwarmingSettings().get('iterations_to_rerun')

  def _OnTaskTriggered(self):  # pragma: no cover.
    monitoring.swarming_tasks.increment({
        'operation': 'trigger',
        'category': 'identify-flake'
    })

  def _GetAdditionalTags(self):  # pragma: no cover.
    return ['purpose:identify-flake']
