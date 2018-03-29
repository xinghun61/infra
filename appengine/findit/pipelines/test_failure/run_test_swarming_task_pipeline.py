# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import exceptions
from dto.run_swarming_task_parameters import RunSwarmingTaskParameters
from gae_libs.pipelines import AsynchronousPipeline
from gae_libs.pipelines import pipeline
from services.test_failure import test_swarming
from waterfall import waterfall_config


class RunTestSwarmingTaskPipeline(AsynchronousPipeline):
  """A pipeline for triggering and monitoring a swarming rerun and
     recording results when it's done."""

  input_type = RunSwarmingTaskParameters
  output_type = bool

  def TimeoutSeconds(self):
    timeout_hours = waterfall_config.GetSwarmingSettings().get(
        'task_timeout_hours', 24)
    return timeout_hours * 60 * 60

  def OnTimeout(self, run_swarming_task_params, parameters):
    task_id = parameters['task_id']
    test_swarming.OnSwarmingTaskTimeout(run_swarming_task_params, task_id)

  def RunImpl(self, run_swarming_task_params):
    if self.GetCallbackParameters().get('task_id'):
      # For idempotent operation.
      logging.warning('RunImpl invoked again after swarming task is triggered.')
      return

    task_id = test_swarming.TriggerSwarmingTask(run_swarming_task_params,
                                                self.pipeline_id)
    if not task_id:
      # Retry upon failure.
      master_name, builder_name, build_number = (
          run_swarming_task_params.build_key.GetParts())
      raise pipeline.Retry(
          'Failed to schedule a swarming task for %s/%s/%d/%s.' %
          (master_name, builder_name, build_number,
           run_swarming_task_params.step_name))

    self.SaveCallbackParameters({'task_id': task_id})

  def CallbackImpl(self, run_swarming_task_params, parameters):
    """Updates the WfSwarmingTask entity with status from swarming."""
    task_id = parameters['task_id']
    try:
      pipeline_completed = test_swarming.OnSwarmingTaskStateChanged(
          run_swarming_task_params, task_id)
      if not pipeline_completed:
        return None
      return None, pipeline_completed
    except exceptions.RetryException as e:  # Indicate an error to retry.
      return ('Error on updating swarming task result: %s' % e.error_message,
              None)
