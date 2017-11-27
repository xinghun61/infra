# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import time

from google.appengine.api import taskqueue

from common import constants
from common import exceptions
from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from common.waterfall.buildbucket_client import BuildbucketBuild
from gae_libs import appengine_util
from gae_libs.pipelines import pipeline
from gae_libs.pipeline_wrapper import BasePipeline
from model.flake.flake_try_job_data import FlakeTryJobData
from model.wf_try_job_data import WfTryJobData
from services import try_job as try_job_service


class MonitorTryJobPipeline(BasePipeline):
  """A pipeline for monitoring a try job and recording results when it's done.

  The result will be stored to compile_results or test_results according to
  which type of build failure we are running try job for.
  """

  async = True

  def __init__(self, *args, **kwargs):
    super(MonitorTryJobPipeline, self).__init__(*args, **kwargs)
    # This dictionary needs to be serializable so that the tests can simulate
    # callbacks to this pipeline.
    self.last_params = {}

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, urlsafe_try_job_key, try_job_type, try_job_id):
    """Monitors try job until it's complete.

    This method stores parameters in self so that the callback method can
    perform appropriate checks.

    callback(), defined below is expected to run when a pubsub notification from
    the buildbucket service is sent to this application indicating that the job
    has changed status.

    callback() is also run in two occassions separate from pubsub:
      - at the end of this run method (i.e. when creating this pipeline)
      - after timeout_hours have passed without the job completing.

    Args:
      urlsafe_try_job_key (str): The urlsafe key for the corresponding try job
        entity.
      try_job_type (str): The type of the try job.
      try_job_id (str): The try job id to query buildbucket with.
    """
    if not try_job_id:
      self.complete()
      return

    try_job_data = try_job_service.GetOrCreateTryJobData(
        try_job_type, try_job_id, urlsafe_try_job_key)
    # Check if callback url is already registered with the TryJobData entity to
    # guarantee this run method is idempotent when called again with the same
    # params.
    if try_job_data.callback_url and (
        self.pipeline_id in try_job_data.callback_url):
      return

    self.last_params = try_job_service.InitializeParams(
        try_job_id, try_job_type, urlsafe_try_job_key)

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

  def finalized(self):
    try:
      try_job_id = self.kwargs.get('try_job_id')
      if not try_job_id and len(self.args) > 2:
        try_job_id = self.args[2]
      if try_job_id:
        taskqueue.Queue(
            constants.WATERFALL_ANALYSIS_QUEUE).delete_tasks_by_name(
                [try_job_id + '_cleanup_task'])
      else:
        logging.error('Did not receive a try_job_id at construction.')
    except taskqueue.BadTaskStateError, e:  # pragma: no cover
      logging.debug('Could not delete cleanup task: %s', e.message)
    return super(MonitorTryJobPipeline, self).finalized()

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

  # Arguments number differs from overridden method - pylint: disable=W0221
  def callback(self, *args, **kwargs):
    """Transitional callback.

    This temporary hack should accept callbacks in the old format
    as well as the new one.
    """
    assert not args
    if 'callback_params' in kwargs:
      return self._callback(**kwargs)
    return self._callback(callback_params=kwargs)

  def _callback(self, callback_params, pipeline_id=None):
    """Updates the TryJobData entities with status from buildbucket."""
    # callback_params may have been serialized if the callback was converted to
    # a URL.
    if isinstance(callback_params, basestring):
      callback_params = json.loads(callback_params)
    self.last_params = callback_params

    _ = pipeline_id  # We do nothing with this id.

    try_job_id = callback_params['try_job_id']
    assert try_job_id

    try_job_type = callback_params['try_job_type']
    deadline = callback_params['deadline']
    timeout_hours = callback_params['timeout_hours']
    backoff_time = callback_params['backoff_time']

    if try_job_type == failure_type.FLAKY_TEST:
      try_job_data = FlakeTryJobData.Get(try_job_id)
    else:
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
      self.complete(result)
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
      try_job_service.UpdateTryJobMetadata(try_job_data, try_job_type, build,
                                           error, True)
      # Explicitly abort the whole pipeline.
      raise pipeline.Abort('Try job %s timed out after %d hours.' %
                           (try_job_id, timeout_hours))

    # Ensure last_buildbucket_response is always the most recent
    # whenever available during intermediate queries.
    try_job_service._UpdateLastBuildbucketResponse(try_job_data, build)
