# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import time

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from common import constants
from common.findit_http_client import FinditHttpClient
from common import monitoring
from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from common.waterfall import try_job_error
from common.waterfall.buildbucket_client import BuildbucketBuild
from gae_libs import appengine_util
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from libs import time_util
from model.flake.flake_try_job_data import FlakeTryJobData
from model.wf_try_bot_cache import WfTryBotCache
from model.wf_try_job_data import WfTryJobData
from waterfall import buildbot
from waterfall import swarming_util
from waterfall import waterfall_config


def _GetError(buildbucket_response, buildbucket_error, timed_out, no_report):
  """Determines whether or not a try job error occurred.

  Args:
    buildbucket_response: A dict of the json response from buildbucket.
    buildbucket_error: A BuildBucketError object returned from the call to
      buildbucket_client.GetTryJobs()
    timed_out: A bool whether or not Findit abandoned monitoring the try job.
    no_report: A bool whether we get result report.

  Returns:
    A tuple containing an error dict and number representing an error code, or
    (None, None) if no error was determined to have occurred.
  """

  if buildbucket_error:
    return ({
        'message': buildbucket_error.message,
        'reason': buildbucket_error.reason
    }, try_job_error.BUILDBUCKET_REQUEST_ERROR)

  if timed_out:
    return ({
        'message':
            'Try job monitoring was abandoned.',
        'reason':
            'Timeout after %s hours' %
            (waterfall_config.GetTryJobSettings().get('job_timeout_hours'))
    }, try_job_error.TIMEOUT)

  if buildbucket_response:
    # Check buildbucket_response.
    buildbucket_failure_reason = buildbucket_response.get('failure_reason')
    if buildbucket_failure_reason == 'BUILD_FAILURE':
      # Generic buildbucket-reported error which can occurr if an exception is
      # thrown, disk is full, compile fails during a test try job, etc.
      return ({
          'message': 'Buildbucket reported a general error.',
          'reason': MonitorTryJobPipeline.UNKNOWN
      }, try_job_error.INFRA_FAILURE)
    elif buildbucket_failure_reason == 'INFRA_FAILURE':
      return ({
          'message': ('Try job encountered an infra issue during '
                      'execution.'),
          'reason':
              MonitorTryJobPipeline.UNKNOWN
      }, try_job_error.INFRA_FAILURE)
    elif buildbucket_failure_reason:
      return ({
          'message': buildbucket_failure_reason,
          'reason': MonitorTryJobPipeline.UNKNOWN
      }, try_job_error.UNKNOWN)

    # Check result_details_json for errors.
    result_details_json = json.loads(
        buildbucket_response.get('result_details_json', '{}')) or {}
    error = result_details_json.get('error', {})
    if error:
      return ({
          'message': 'Buildbucket reported an error.',
          'reason': error.get('message', MonitorTryJobPipeline.UNKNOWN)
      }, try_job_error.CI_REPORTED_ERROR)

    if no_report:
      return ({
          'message': 'No result report was found.',
          'reason': MonitorTryJobPipeline.UNKNOWN
      }, try_job_error.UNKNOWN)

  return None, None


def _OnTryJobError(try_job_type, error_dict, master_name,
                   builder_name):  # pragma: no cover
  monitoring.try_job_errors.increment({
      'type': try_job_type,
      'error': error_dict.get('message', 'unknown'),
      'master_name': master_name,
      'builder_name': builder_name
  })


def _UpdateTryJobMetadata(try_job_data,
                          try_job_type,
                          buildbucket_build,
                          buildbucket_error,
                          timed_out,
                          report=None):
  buildbucket_response = {}

  if buildbucket_build:
    try_job_data.request_time = (
        try_job_data.request_time or
        time_util.MicrosecondsToDatetime(buildbucket_build.request_time))
    # If start_time hasn't been set, use request_time.
    try_job_data.start_time = try_job_data.start_time or (
        try_job_data.request_time)
    try_job_data.end_time = time_util.MicrosecondsToDatetime(
        buildbucket_build.end_time)

    if try_job_type != failure_type.FLAKY_TEST:  # pragma: no branch
      if report:
        try_job_data.number_of_commits_analyzed = len(report.get('result', {}))
        try_job_data.regression_range_size = report.get(
            'metadata', {}).get('regression_range_size')
      else:
        try_job_data.number_of_commits_analyzed = 0
        try_job_data.regression_range_size = None

    try_job_data.try_job_url = buildbucket_build.url
    buildbucket_response = buildbucket_build.response
    try_job_data.last_buildbucket_response = buildbucket_response

  # report should only be {} when error happens on getting report after try job
  # completed. If try job is still running, report will be set to None.
  error_dict, error_code = _GetError(buildbucket_response, buildbucket_error,
                                     timed_out, report == {})

  if error_dict:
    try_job_data.error = error_dict
    try_job_data.error_code = error_code
    _OnTryJobError(try_job_type, error_dict, try_job_data.master_name,
                   try_job_data.builder_name)

  try_job_data.put()


def _DictsAreEqual(dict_1, dict_2, exclude_keys=None):
  if dict_1 == dict_2:
    return True

  if dict_1 is None or dict_2 is None:
    return False

  if exclude_keys is None:
    exclude_keys = []

  for key, value in dict_1.iteritems():
    if key not in exclude_keys and (key not in dict_2 or dict_2[key] != value):
      return False

  for key, value in dict_2.iteritems():
    if key not in exclude_keys and (key not in dict_1 or dict_1[key] != value):
      return False

  return True


def _UpdateLastBuildbucketResponse(try_job_data, build):
  if not build or not build.response:  # pragma: no cover
    return

  if not _DictsAreEqual(
      try_job_data.last_buildbucket_response,
      build.response,
      exclude_keys=['utcnow_ts']):
    try_job_data.last_buildbucket_response = build.response
    try_job_data.put()


def _RecordCacheStats(build, report):
  """Save the bot's state at the end of a successful.

  This function aims to save the following data in the data store:
   - The last revision that the bot synced to under the specific work
     directory (named cache) it used for its local checkout.
   - The latest revision fetched into the bot's local git cache, which is shared
     accross all work directories.

  These are saved as commit positions rather than revision hashes for faster
  comparisons when selecting a bot for new tryjobs.
  """
  bot = swarming_util.GetBot(build)
  cache_name = swarming_util.GetBuilderCacheName(build)
  if bot and cache_name:
    git_repo = CachedGitilesRepository(
        FinditHttpClient(),
        'https://chromium.googlesource.com/chromium/src.git')

    last_checked_out_revision = report.get('last_checked_out_revision')
    last_checked_out_cp = (
        git_repo.GetChangeLog(last_checked_out_revision).commit_position
        if last_checked_out_revision else None)

    cached_revision = report.get('previously_cached_revision')
    cached_cp = git_repo.GetChangeLog(
        cached_revision).commit_position if cached_revision else None

    bad_revision = json.loads(build.response.get('parameters_json', '{}')).get(
        'properties', {}).get('bad_revision')
    bad_cp = git_repo.GetChangeLog(
        bad_revision).commit_position if bad_revision else None

    # If the bad_revision is later than the previously cached revision, that
    # means that the bot had to sync with the remote repository, and the local
    # git cache was updated to that revision at least.
    latest_synced_cp = max(bad_cp, cached_cp)

    cache_stats = WfTryBotCache.Get(cache_name)
    cache_stats.AddBot(bot, last_checked_out_cp, latest_synced_cp)

    # TODO(robertocn): Record the time it took to complete the task
    # with a cold or warm cache.
    cache_stats.put()


class MonitorTryJobPipeline(BasePipeline):
  """A pipeline for monitoring a try job and recording results when it's done.

  The result will be stored to compile_results or test_results according to
  which type of build failure we are running try job for.
  """

  async = True
  UNKNOWN = 'UNKNOWN'

  @ndb.transactional
  def _UpdateTryJobResult(self,
                          urlsafe_try_job_key,
                          try_job_type,
                          try_job_id,
                          try_job_url,
                          status,
                          result_content=None):
    """Updates try job result based on response try job status and result."""
    result = {
        'report': result_content,
        'url': try_job_url,
        'try_job_id': try_job_id,
    }

    try_job = ndb.Key(urlsafe=urlsafe_try_job_key).get()

    if try_job_type == failure_type.FLAKY_TEST:
      result_to_update = try_job.flake_results
    elif try_job_type == failure_type.COMPILE:
      result_to_update = try_job.compile_results
    else:
      result_to_update = try_job.test_results

    if result_to_update and result_to_update[-1]['try_job_id'] == try_job_id:
      result_to_update[-1].update(result)
    else:  # pragma: no cover
      # Normally result for current try job should have been saved in
      # schedule_try_job_pipeline, so this branch shouldn't be reached.
      result_to_update.append(result)

    if status == BuildbucketBuild.STARTED:
      try_job.status = analysis_status.RUNNING

    try_job.put()

    return result_to_update

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

    if try_job_type == failure_type.FLAKY_TEST:
      try_job_kind = FlakeTryJobData
    else:
      try_job_kind = WfTryJobData
    try_job_data = try_job_kind.Get(try_job_id)

    if not try_job_data:
      logging.error('%(kind)s entity does not exist for id %(id)s: creating it',
                    {'kind': try_job_kind,
                     'id': try_job_id})
      try_job_data = try_job_kind.Create(try_job_id)
      try_job_data.try_job_key = ndb.Key(urlsafe=urlsafe_try_job_key)

    # Check if callback url is already registered with the TryJobData entity to
    # guarantee this run method is idempotent when called again with the same
    # params.
    if try_job_data.callback_url and (
        self.pipeline_id in try_job_data.callback_url):
      return

    timeout_hours = waterfall_config.GetTryJobSettings().get(
        'job_timeout_hours')
    default_pipeline_wait_seconds = waterfall_config.GetTryJobSettings().get(
        'server_query_interval_seconds')
    max_error_times = waterfall_config.GetTryJobSettings().get(
        'allowed_response_error_times')

    # TODO(chanli): Make sure total wait time equals to timeout_hours
    # regardless of retries.
    deadline = time.time() + timeout_hours * 60 * 60
    already_set_started = False
    backoff_time = default_pipeline_wait_seconds
    error_count = 0

    self.last_params = {
        'try_job_id': try_job_id,
        'try_job_type': try_job_type,
        'urlsafe_try_job_key': urlsafe_try_job_key,
        'deadline': deadline,
        'already_set_started': already_set_started,
        'error_count': error_count,
        'max_error_times': max_error_times,
        'default_pipeline_wait_seconds': default_pipeline_wait_seconds,
        'timeout_hours': timeout_hours,
        'backoff_time': backoff_time,
    }

    callback_url = self.get_callback_url(
        callback_params=json.dumps(self.last_params))

    try_job_data.callback_url = callback_url
    try_job_data.callback_target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    try_job_data.put()

    # Guarantee one callback 10 minutes after the deadline to clean up even if
    # buildbucket fails to call us back.
    self.delay_callback(
        (timeout_hours * 60 + 10) * 60,
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

    urlsafe_try_job_key = callback_params['urlsafe_try_job_key']
    try_job_type = callback_params['try_job_type']
    deadline = callback_params['deadline']
    already_set_started = callback_params['already_set_started']
    error_count = callback_params['error_count']
    max_error_times = callback_params['max_error_times']
    default_pipeline_wait_seconds = callback_params[
        'default_pipeline_wait_seconds']
    timeout_hours = callback_params['timeout_hours']
    backoff_time = callback_params['backoff_time']

    if try_job_type == failure_type.FLAKY_TEST:
      try_job_data = FlakeTryJobData.Get(try_job_id)
    else:
      try_job_data = WfTryJobData.Get(try_job_id)

    error, build = buildbucket_client.GetTryJobs([try_job_id])[0]

    if error:
      if error_count < max_error_times:
        error_count += 1
        self.delay_callback(
            backoff_time,
            callback_params={
                'try_job_id': try_job_id,
                'try_job_type': try_job_type,
                'urlsafe_try_job_key': urlsafe_try_job_key,
                'deadline': deadline,
                'already_set_started': already_set_started,
                'error_count': error_count,
                'max_error_times': max_error_times,
                'default_pipeline_wait_seconds': default_pipeline_wait_seconds,
                'timeout_hours': timeout_hours,
                'backoff_time': backoff_time * 2,
            })
        return
      else:  # pragma: no cover
        # Buildbucket has responded error more than 5 times, retry pipeline.
        _UpdateTryJobMetadata(try_job_data, try_job_type, build, error, False)
        raise pipeline.Retry('Error "%s" occurred. Reason: "%s"' %
                             (error.message, error.reason))
    elif build.status == BuildbucketBuild.COMPLETED:
      swarming_task_id = buildbot.GetSwarmingTaskIdFromUrl(build.url)

      if swarming_task_id:
        try:
          report = swarming_util.GetStepLog(try_job_id, 'report',
                                            FinditHttpClient(), 'report')
          if report:
            _RecordCacheStats(build, report)
        except (ValueError, TypeError) as e:  # pragma: no cover
          report = {}
          logging.exception('Failed to load result report for swarming/%s '
                            'due to exception %s.' % (swarming_task_id,
                                                      e.message))
      else:
        try_job_master_name, try_job_builder_name, try_job_build_number = (
            buildbot.ParseBuildUrl(build.url))

        try:
          report = buildbot.GetStepLog(try_job_master_name,
                                       try_job_builder_name,
                                       try_job_build_number, 'report',
                                       FinditHttpClient(), 'report')
        except (ValueError, TypeError) as e:  # pragma: no cover
          report = {}
          logging.exception(
              'Failed to load result report for %s/%s/%s due to exception %s.' %
              (try_job_master_name, try_job_builder_name, try_job_build_number,
               e.message))

      _UpdateTryJobMetadata(try_job_data, try_job_type, build, error, False,
                            report if report else {})
      result_to_update = self._UpdateTryJobResult(
          urlsafe_try_job_key, try_job_type, try_job_id, build.url,
          BuildbucketBuild.COMPLETED, report)
      self.complete(result_to_update[-1])
      return
    else:
      error_count = 0
      backoff_time = default_pipeline_wait_seconds
      if build.status == BuildbucketBuild.STARTED and not already_set_started:
        # It is possible this branch is skipped if a fast build goes from
        # 'SCHEDULED' to 'COMPLETED' between queries, so start_time may be
        # unavailable.
        start_time = time_util.MicrosecondsToDatetime(build.updated_time)
        self._UpdateTryJobResult(urlsafe_try_job_key, try_job_type, try_job_id,
                                 build.url, BuildbucketBuild.STARTED)

        already_set_started = True

        # Update as much try job metadata as soon as possible to avoid data
        # loss in case of errors.
        try_job_data.start_time = start_time
        try_job_data.request_time = (
            time_util.MicrosecondsToDatetime(build.request_time))
        try_job_data.try_job_url = build.url
        try_job_data.callback_url = self.get_callback_url(
            callback_params=json.dumps({
                'try_job_id': try_job_id,
                'try_job_type': try_job_type,
                'urlsafe_try_job_key': urlsafe_try_job_key,
                'deadline': deadline,
                'already_set_started': already_set_started,
                'error_count': error_count,
                'max_error_times': max_error_times,
                'default_pipeline_wait_seconds': default_pipeline_wait_seconds,
                'timeout_hours': timeout_hours,
                'backoff_time': backoff_time,
            }))
        try_job_data.put()

    if time.time() > deadline:  # pragma: no cover
      _UpdateTryJobMetadata(try_job_data, try_job_type, build, error, True)
      # Explicitly abort the whole pipeline.
      raise pipeline.Abort('Try job %s timed out after %d hours.' %
                           (try_job_id, timeout_hours))

    # Ensure last_buildbucket_response is always the most recent
    # whenever available during intermediate queries.
    _UpdateLastBuildbucketResponse(try_job_data, build)
