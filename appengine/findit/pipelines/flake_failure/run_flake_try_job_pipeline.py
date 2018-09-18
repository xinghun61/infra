# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

from common import exceptions
from common.waterfall import failure_type
from dto.flake_try_job_result import FlakeTryJobResult
from gae_libs.pipelines import AsynchronousPipeline
from gae_libs.pipelines import pipeline
from libs.list_of_basestring import ListOfBasestring
from libs.structured_object import StructuredObject
from services import try_job as try_job_service
from services.flake_failure import flake_try_job


class RunFlakeTryJobParameters(StructuredObject):
  # The urlsafe-key of the analysis in progress.
  analysis_urlsafe_key = basestring

  # The git revision to trigger the try job against.
  revision = basestring

  # The name of the cache on the bot to use.
  flake_cache_name = basestring

  # The dimensions of the bot.
  dimensions = ListOfBasestring

  # The isolate target name containing the test.
  isolate_target_name = basestring

  # The key to the try job entity this pipeline is responsible for.
  urlsafe_try_job_key = basestring


class RunFlakeTryJobPipeline(AsynchronousPipeline):
  """Schedules, monitors, and records results for a Flake Try Job."""

  input_type = RunFlakeTryJobParameters
  output_type = FlakeTryJobResult

  def TimeoutSeconds(self):
    return 10 * 60 * 60  # 10 hours. This will enable a timeout callback.

  def OnTimeout(self, arg, parameters):
    # TODO(crbug.com/835066): Capture metrics for pipeline timeouts.
    super(RunFlakeTryJobPipeline, self).OnTimeout(arg, parameters)
    try_job_id = parameters.get('try_job_id')
    try_job_service.OnTryJobTimeout(try_job_id, failure_type.FLAKY_TEST)

  def RunImpl(self, run_try_job_params):
    if self.GetCallbackParameters().get('try_job_id'):
      # For idempotent operation.
      logging.warning('RunImpl invoked again after try job is scheduled.')
      return

    try_job_id = flake_try_job.ScheduleFlakeTryJob(run_try_job_params,
                                                   self.pipeline_id)
    if not try_job_id:
      raise pipeline.Retry(
          'Failed to schedule a flake try job at revision {}'.format(
              run_try_job_params.revision))

    self.SaveCallbackParameters({'try_job_id': try_job_id})

  def CallbackImpl(self, _run_try_job_params, callback_params):
    """Updates the FlakeTryJobData entity with status from buildbucket."""
    try_job_id = callback_params.get('try_job_id')
    if not try_job_id:
      return ('Try_job_id not found for pipeline {}'.format(self.pipeline_id),
              None)

    build_json = json.loads(callback_params['build_json'])

    try:
      result = flake_try_job.OnTryJobStateChanged(try_job_id, build_json)
      if result is None:
        return None
      return None, result
    except exceptions.RetryException as e:  # Indicate an error to retry.
      return 'Error updating try job result: {}'.format(e.error_message), None
