# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

from common import exceptions
from common.waterfall import failure_type
from gae_libs.pipelines import AsynchronousPipeline
from gae_libs.pipelines import pipeline
from services import try_job
from services.parameters import TestTryJobResult
from services.parameters import RunTestTryJobParameters
from services.test_failure import test_try_job


class RunTestTryJobPipeline(AsynchronousPipeline):
  """A pipeline for scheduling and monitoring a try job and
     recording results when it's done.
  """

  input_type = RunTestTryJobParameters
  output_type = TestTryJobResult

  def TimeoutSeconds(self):
    return 10 * 60 * 60  # 10 hours. This will enable a timeout callback.

  def OnTimeout(self, arg, parameters):
    # TODO(crbug.com/835066): Capture metrics for pipeline timeouts.
    super(RunTestTryJobPipeline, self).OnTimeout(arg, parameters)
    try_job_id = parameters.get('try_job_id')
    try_job.OnTryJobTimeout(try_job_id, failure_type.TEST)

  def RunImpl(self, run_try_job_params):
    if self.GetCallbackParameters().get('try_job_id'):
      # For idempotent operation.
      logging.warning('RunImpl invoked again after try job is scheduled.')
      return

    try_job_id = test_try_job.ScheduleTestTryJob(run_try_job_params,
                                                 self.pipeline_id)
    if not try_job_id:
      # Retry upon failure.
      raise pipeline.Retry('Failed to schedule a try job for %s/%s/%d.' %
                           run_try_job_params.build_key.GetParts())

    self.SaveCallbackParameters({'try_job_id': try_job_id})

  def CallbackImpl(self, _run_try_job_params, parameters):
    """Updates the TryJobData entity with status from Buildbucket."""
    if not parameters.get('try_job_id'):
      # Try_job_id is not saved in callback parameters yet,
      # retries the callback.
      return 'Try_job_id not found for pipeline %s' % self.pipeline_id, None

    try_job_id = parameters['try_job_id']
    build_json = json.loads(parameters['build_json'])
    try:
      result = test_try_job.OnTryJobStateChanged(try_job_id, build_json)
      if result is None:
        return None
      return None, result
    except exceptions.RetryException as e:  # Indicate an error to retry.
      return 'Error on updating try-job result: %s' % e.error_message, None
