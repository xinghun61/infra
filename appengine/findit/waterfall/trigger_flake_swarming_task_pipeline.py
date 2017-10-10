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

  def _NeedANewSwarmingTask(self, *args, **_):
    """Creates or resets an existing flake swarming task entity.

    For determining the true pass rate of tests, multiple swarming tasks at the
    same build configuration are run until the pass rates converge or up to a
    total maximum number of iterations. Thus when triggering a flake swarming
    task, a new task is always needed and the old data should always be reset
    to avoid unintentional caching.

    TODO(crbug.com/772169): It is possible a request made through Findit API
    triggers an analysis at the same build configuration, which may result in
    conflicts through multiple pipelines modifying the same swarming task
    entity. This is expected to be extremely rare, but should be handled.

    Args:
      *args ([(str), (str), (int), (str), (str)]): The master_name,
          builder_name, build_number, step_name, test_name to reference an
          existing task with.

    Returns:
      True upon creating or resetting a swarming task.
    """
    swarming_task = (self._GetSwarmingTask(*args) or
                     self._CreateSwarmingTask(*args))

    # Queued will be set to true if The task has been created but has not yet
    # been executed for cases it was triggered through Findit API. Queued should
    # Be preserved in case multiple requests come through Findit API for the
    # same configuration but the task has not yet been run, such as due to
    # bot unavailability.
    queued = swarming_task.queued
    swarming_task.Reset()
    swarming_task.queued = queued
    swarming_task.put()

    return True

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
