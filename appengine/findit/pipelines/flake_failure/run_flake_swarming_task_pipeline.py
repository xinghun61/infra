# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Handles triggering and reporting flake swarming task results."""
import logging

from common import exceptions
from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from gae_libs.pipelines import AsynchronousPipeline
from gae_libs.pipelines import pipeline
from libs.structured_object import StructuredObject
from services.flake_failure import flake_swarming


class RunFlakeSwarmingTaskInput(StructuredObject):
  # The urlsafe key of the MasterFlakeAnalysis in progress.
  analysis_urlsafe_key = basestring

  # The commit position to run the flake swarming task against.
  commit_position = int

  # The isolate sha pointing to the binaries to test.
  isolate_sha = basestring

  # The number of iterations to run.
  iterations = int

  # The number of seconds the task must complete within.
  timeout_seconds = int


class RunFlakeSwarmingTaskPipeline(AsynchronousPipeline):
  """Triggers, waits for, and returns results of a flake swarming task."""

  input_type = RunFlakeSwarmingTaskInput
  output_type = FlakeSwarmingTaskOutput

  def TimeoutSeconds(self):
    return 24 * 60 * 60  # 24 hours. This will enable a timeout callback.

  def OnTimeout(self, pipeline_parameters, callback_parameters):
    # TODO(crbug.com/835066): Capture metrics for pipeline timeouts.
    super(RunFlakeSwarmingTaskPipeline, self).OnTimeout(pipeline_parameters,
                                                        pipeline_parameters)
    task_id = callback_parameters.get('task_id')
    return flake_swarming.OnSwarmingTaskTimeout(task_id)

  def RunImpl(self, pipeline_parameters):
    if self.GetCallbackParameters().get('task_id'):
      # For idempotent operation.
      logging.warning(
          'RunImpl invoked again after swarming task was already triggered.')
      return

    task_id = flake_swarming.TriggerSwarmingTask(
        pipeline_parameters.analysis_urlsafe_key,
        pipeline_parameters.isolate_sha, pipeline_parameters.iterations,
        pipeline_parameters.timeout_seconds, self.pipeline_id)

    if not task_id:
      # Retry upon failure.
      raise pipeline.Retry('Failed to schedule a swarming task')

    self.SaveCallbackParameters({'task_id': task_id})

  def CallbackImpl(self, _, callback_parameters):
    """Returns the results of the swarming task."""
    if not callback_parameters.get('task_id'):
      # Task_id is not saved in callback parameters yet, retries the callback.
      return 'Task_id not found for pipeline %s' % self.pipeline_id, None

    task_id = callback_parameters['task_id']
    try:
      results = flake_swarming.OnSwarmingTaskStateChanged(task_id)
      if not results:
        # No task state, further callback is needed.
        return None
      return None, results
    except exceptions.RetryException as e:  # Indicate an error to retry.
      return ('Error getting swarming task result: {}'.format(e.error_message),
              None)
