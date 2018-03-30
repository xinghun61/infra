# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import exceptions
from dto.collect_swarming_task_results_inputs import (
    CollectSwarmingTaskResultsInputs)
from dto.collect_swarming_task_results_outputs import (
    CollectSwarmingTaskResultsOutputs)
from gae_libs.pipelines import AsynchronousPipeline
from services.test_failure import test_swarming
from waterfall import waterfall_config

_COUNTDOWN_LIMIT = 6
_COUNTDOWN_DEFAULT = 1


def _GetCountDown(callback_count):
  """Gets how long should next task waits.

  The wait time decreases linearly until hits the limit.
  """
  wait_min = (
      _COUNTDOWN_LIMIT - callback_count
      if _COUNTDOWN_LIMIT > callback_count else _COUNTDOWN_DEFAULT)
  return wait_min * 60


class CollectSwarmingTaskResultsPipeline(AsynchronousPipeline):
  """A pipeline to collect results of all swarming reruns.
  """

  input_type = CollectSwarmingTaskResultsInputs
  output_type = CollectSwarmingTaskResultsOutputs

  def TimeoutSeconds(self):
    timeout_hours = waterfall_config.GetSwarmingSettings().get(
        'task_timeout_hours', 24)
    return timeout_hours * 60 * 60

  def OnTimeout(self, _collect_consistent_failure_params, _parameters):
    logging.error('Timed out when collecting results of swarming tasks.')

  def RunImpl(self, collect_consistent_failure_params):
    if 'steps' in self.GetCallbackParameters():
      # For idempotent operation.
      logging.warning(
          'RunImpl invoked again for collecting swarming task results.')
      return

    steps = test_swarming.GetStepsToCollectSwarmingTaskResults(
        collect_consistent_failure_params)

    self.SaveCallbackParameters({'steps': steps, 'callback_count': 0})

    # Schedules a callback immediately.
    self.ScheduleCallbackTask(countdown=0)

  def CallbackImpl(self, collect_consistent_failure_params, parameters):
    """Checks the WfSwarmingTask entities to get consistently failed tests."""
    steps = parameters['steps']

    callback_count = parameters['callback_count'] + 1
    try:
      consistent_failures = (
          test_swarming.GetConsistentFailuresWhenAllTasksComplete(
              collect_consistent_failure_params, steps))
      if not consistent_failures:
        self.SaveCallbackParameters({
            'steps': steps,
            'callback_count': callback_count
        })
        self.ScheduleCallbackTask(countdown=_GetCountDown(callback_count))
        return None
      return None, consistent_failures
    except exceptions.RetryException as e:  # Indicate an error to retry.
      return ('Error on updating swarming task result: %s' % e.error_message,
              None)
