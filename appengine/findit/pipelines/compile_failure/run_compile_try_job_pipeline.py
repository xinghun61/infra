# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import time

from google.appengine.api import taskqueue

from common.waterfall import failure_type
from common import constants
from common import exceptions
from common.waterfall import buildbucket_client
from common.waterfall.buildbucket_client import BuildbucketBuild
from gae_libs import appengine_util
from gae_libs.pipelines import AsynchronousPipeline
from gae_libs.pipelines import pipeline
from model.wf_try_job_data import WfTryJobData
from services import try_job as try_job_service
from services.compile_failure import compile_try_job
from services.parameters import CompileTryJobResult
from services.parameters import RunCompileTryJobParameters


class RunCompileTryJobPipeline(AsynchronousPipeline):
  """A pipeline for scheduling and monitoring a try job and
     recording results when it's done."""

  async = True
  input_type = RunCompileTryJobParameters
  output_type = CompileTryJobResult

  def __init__(self, *args, **kwargs):
    super(RunCompileTryJobPipeline, self).__init__(*args, **kwargs)
    # This dictionary needs to be serializable so that the tests can simulate
    # callbacks to this pipeline.
    self.last_params = {}

  def OnFinalized(self, run_try_job_params):
    try:
      try_job_id = try_job_service.GetCurrentWaterfallTryJobID(
          run_try_job_params.urlsafe_try_job_key, self.pipeline_id)
      if try_job_id:
        taskqueue.Queue(
            constants.WATERFALL_ANALYSIS_QUEUE).delete_tasks_by_name(
                [try_job_id + '_cleanup_task'])
      else:
        logging.error('Did not receive a try_job_id at construction.')
    except taskqueue.BadTaskStateError, e:  # pragma: no cover
      logging.debug('Could not delete cleanup task: %s', e.message)

  def RunImpl(self, run_try_job_params):
    try:
      try_job_id = compile_try_job.ScheduleCompileTryJob(
          run_try_job_params, self.pipeline_id)
      if not try_job_id:
        logging.error('Failed to schedule a try job for %s/%s/%d.' %
                      run_try_job_params.build_key.GetParts())
        self.Complete(None)
        return

      try_job_type = failure_type.COMPILE
      urlsafe_try_job_key = run_try_job_params.urlsafe_try_job_key
      try_job_data = try_job_service.GetOrCreateTryJobData(
          try_job_type, try_job_id, urlsafe_try_job_key)

      self.last_params = try_job_service.InitializeParams(
          try_job_id, try_job_type, urlsafe_try_job_key)

      # TODO(crbug/789218): Add callback_url and callback_target to request of
      # scheduling try job.
      callback_url = self.get_callback_url(
          callback_params=json.dumps(self.last_params))

      try_job_service.UpdateTryJobMetadata(
          try_job_data,
          callback_url=callback_url,
          callback_target=appengine_util.GetTargetNameForModule(
              constants.WATERFALL_BACKEND))

      # Guarantee one callback 10 minutes after the deadline to clean up even if
      # buildbucket fails to call us back.
      self.delay_callback(
          (self.last_params['timeout_hours'] * 60 + 10) * 60,
          self.last_params,
          name=try_job_id + '_cleanup_task')

      # Run immediately in case the job already went from scheduled to started.
      self.callback(callback_params=self.last_params)

    except exceptions.RetryException as e:
      raise pipeline.Retry('Error "%s" occurred: "%s"' % (e.error_reason,
                                                          e.error_message))

  def delay_callback(self, countdown, callback_params, name=None):
    target = appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND)

    try:
      task = self.get_callback_task(
          countdown=countdown,
          target=target,
          params={'callback_params': json.dumps(callback_params)},
          name=name)
      task.add(queue_name=constants.WATERFALL_ANALYSIS_QUEUE)
    except taskqueue.TombstonedTaskError:
      logging.warning(
          'A task named %s has already been added to the task queue', name)

  def CallbackImpl(self, run_try_job_params, callback_params):
    """Updates the TryJobData entities with status from buildbucket."""
    # callback_params may have been serialized if the callback was converted to
    # a URL.
    _ = run_try_job_params  # We do nothing with this input.
    callback_params = callback_params.get('callback_params', callback_params)

    if isinstance(callback_params, basestring):
      callback_params = json.loads(callback_params)
    self.last_params = callback_params

    try_job_id = callback_params['try_job_id']
    assert try_job_id

    deadline = callback_params['deadline']
    timeout_hours = callback_params['timeout_hours']
    backoff_time = callback_params['backoff_time']

    try_job_data = WfTryJobData.Get(try_job_id)

    error, build = buildbucket_client.GetTryJobs([try_job_id])[0]

    if error:
      try:
        new_params = try_job_service.OnGetTryJobError(
            callback_params, try_job_data, build, error)
        self.delay_callback(backoff_time, callback_params=new_params)
        return
      except exceptions.RetryException as e:
        raise pipeline.Retry('Error "%s" occured: %s.' % (e.error_reason,
                                                          e.error_message))
    elif build.status == BuildbucketBuild.COMPLETED:
      result = try_job_service.OnTryJobCompleted(callback_params, try_job_data,
                                                 build, error)
      result = CompileTryJobResult.FromSerializable(result)
      self.Complete(result)
      return
    else:
      new_params = try_job_service.OnTryJobRunning(callback_params,
                                                   try_job_data, build, error)
      if new_params:
        try_job_service.UpdateTryJobMetadata(
            try_job_data,
            callback_url=self.get_callback_url(
                callback_params=json.dumps(new_params)))

    if time.time() > deadline:  # pragma: no cover
      try_job_service.UpdateTryJobMetadata(try_job_data, failure_type.COMPILE,
                                           build, error, True)
      # Explicitly abort the whole pipeline.
      raise pipeline.Abort('Try job %s timed out after %d hours.' %
                           (try_job_id, timeout_hours))

    # Ensure last_buildbucket_response is always the most recent
    # whenever available during intermediate queries.
    try_job_service._UpdateLastBuildbucketResponse(try_job_data, build)
