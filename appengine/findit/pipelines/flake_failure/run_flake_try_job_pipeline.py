# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import time

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from common import constants
from common import exceptions
from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from common.waterfall.buildbucket_client import BuildbucketBuild
from dto.flake_try_job_result import FlakeTryJobResult
from gae_libs import appengine_util
from gae_libs.pipelines import AsynchronousPipeline
from gae_libs.pipelines import pipeline
from libs.list_of_basestring import ListOfBasestring
from libs.structured_object import StructuredObject
from model.flake.flake_try_job_data import FlakeTryJobData
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

  # The key to the try job entity this pipeline is responsible for.
  urlsafe_try_job_key = basestring


class RunFlakeTryJobPipeline(AsynchronousPipeline):
  """Schedules, monitors, and records results for a Flake Try Job."""

  async = True
  input_type = RunFlakeTryJobParameters
  output_type = FlakeTryJobResult

  def __init__(self, *args, **kwargs):
    super(RunFlakeTryJobPipeline, self).__init__(*args, **kwargs)
    # This dictionary needs to be serializable so that the tests can simulate
    # callbacks to this pipeline.
    self.last_params = {}

  def _TimedOut(self, deadline):
    return time.time() > deadline

  def OnFinalized(self, run_try_job_params):
    try:
      try_job_id = try_job_service.GetCurrentTryJobID(
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
    assert run_try_job_params.analysis_urlsafe_key
    analysis = ndb.Key(urlsafe=run_try_job_params.analysis_urlsafe_key).get()
    assert analysis

    try:
      try_job_id = flake_try_job.ScheduleFlakeTryJob(run_try_job_params,
                                                     self.pipeline_id)
      if not try_job_id:
        analysis.LogError('Failed to schedule a flake try job for %s' %
                          run_try_job_params.revision)
        self.complete({})  # TODO(lijeffrey): remove this temporary hack.
        return

      try_job_type = failure_type.FLAKY_TEST
      urlsafe_try_job_key = run_try_job_params.urlsafe_try_job_key
      try_job_data = try_job_service.GetOrCreateTryJobData(
          try_job_type, try_job_id, urlsafe_try_job_key)

      self.last_params = try_job_service.InitializeParams(
          try_job_id, try_job_type, urlsafe_try_job_key)

      # TODO(crbug.com/789218): Add callback_url and callback_target to request
      # of scheduling try job.
      callback_url = self.get_callback_url(
          callback_params=json.dumps(self.last_params))

      try_job_service.UpdateTryJobMetadata(
          try_job_data,
          callback_url=callback_url,
          callback_target=appengine_util.GetTargetNameForModule(
              constants.WATERFALL_BACKEND))

      # Guarantee one callback 10 minutes after the deadline to clean up even if
      # buildbucket fails to call us back.
      self.DelayCallback(
          (self.last_params['timeout_hours'] * 60 + 10) * 60,
          self.last_params,
          name=try_job_id + '_cleanup_task')

      # Run immediately in case the job already went from scheduled to started.
      self.callback(callback_params=self.last_params)

    except exceptions.RetryException as e:
      raise pipeline.Retry('Error "%s" occurred: "%s"' % (e.error_reason,
                                                          e.error_message))

  def DelayCallback(self, countdown, callback_params, name=None):
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

  # Unused argument - pylint: disable=W0613
  def CallbackImpl(self, run_try_job_params, callback_params):
    """Updates the FlakeTryJobData entity with status from buildbucket."""
    # callback_params may have been serialized if the callback was converted to
    # a URL.
    analysis = ndb.Key(urlsafe=run_try_job_params.analysis_urlsafe_key).get()
    assert analysis

    callback_params = callback_params.get('callback_params', callback_params)

    if isinstance(callback_params, basestring):
      callback_params = json.loads(callback_params)
    self.last_params = callback_params

    try_job_id = callback_params['try_job_id']
    assert try_job_id

    deadline = callback_params['deadline']
    timeout_hours = callback_params['timeout_hours']
    backoff_time = callback_params['backoff_time']

    try_job_data = FlakeTryJobData.Get(try_job_id)

    error, build = buildbucket_client.GetTryJobs([try_job_id])[0]

    if error:
      analysis.LogWarning('Error detected trying to get try job, retry later')
      try:
        new_params = try_job_service.OnGetTryJobError(
            callback_params, try_job_data, build, error)
        self.DelayCallback(backoff_time, callback_params=new_params)
        return
      except exceptions.RetryException as e:
        raise pipeline.Retry('Error "%s" occured: %s.' % (e.error_reason,
                                                          e.error_message))
    if build.status == BuildbucketBuild.COMPLETED:
      analysis.LogInfo(
          'Try job completed for revision %s' % run_try_job_params.revision)
      result = try_job_service.OnTryJobCompleted(callback_params, try_job_data,
                                                 build, error)
      return None, FlakeTryJobResult.FromSerializable(result)

    new_params = try_job_service.OnTryJobRunning(callback_params, try_job_data,
                                                 build, error)
    if new_params:
      try_job_service.UpdateTryJobMetadata(
          try_job_data,
          callback_url=self.get_callback_url(
              callback_params=json.dumps(new_params)))

    if self._TimedOut(deadline):
      try_job_service.UpdateTryJobMetadata(
          try_job_data, failure_type.FLAKY_TEST, build, error, True)
      # Explicitly abort the whole pipeline.
      raise pipeline.Abort('Try job %s timed out after %d hours.' %
                           (try_job_id, timeout_hours))

    # Ensure last_buildbucket_response is always the most recent
    # whenever available during intermediate queries.
    try_job_service._UpdateLastBuildbucketResponse(try_job_data, build)
