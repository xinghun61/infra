# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for try-job-related operations.

Failure type specific logic is in corresponding modules. This module is for
shared logic.

It provides functions to:
  * Get matching failure group.
  * Get suspects from heuristic results.
  * Preliminary check to decide if a new try job is needed.
  * Get trybot for try jobs.
  * Trigger a try job.
  * Monitor a try job.
"""

import copy
from datetime import timedelta
import json
import logging
import time

from google.appengine.ext import ndb

from common import exceptions
from common.findit_http_client import FinditHttpClient
from common.findit_http_client import HttpClientMetricsInterceptor
from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from common.waterfall import try_job_error
from common.waterfall.buildbucket_client import BuildbucketBuild
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import analysis_status
from libs import time_util
from model import result_status
from model.flake.flake_try_job_data import FlakeTryJobData
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_failure_group import WfFailureGroup
from model.wf_try_job import WfTryJob
from model.wf_try_bot_cache import WfTryBotCache
from model.wf_try_job_data import WfTryJobData
from services import gtest
from services import monitoring
from waterfall import buildbot
from waterfall import swarming_util
from waterfall import waterfall_config

UNKNOWN = 'UNKNOWN'


def _ShouldBailOutForOutdatedBuild(build):
  return (build.start_time is None or
          (time_util.GetUTCNow() - build.start_time).days > 0)


def _BlameListsIntersection(blame_list_1, blame_list_2):
  return set(blame_list_1) & set(blame_list_2)


def _GetSuspectedCLsWithFailures(heuristic_result):
  """Generates a list of suspected CLs with failures.

  Args:
    heuristic_result: the heuristic_result from which to generate the list of
    suspected CLs with failures.

  Returns:
    A list of suspected CLs with failures that each could look like:

        [step_name, revision, test_name]

    or could look like:

        [step_name, revision, None]
  """
  suspected_cls_with_failures = []

  if not heuristic_result:
    return suspected_cls_with_failures

  # Iterates through the failures, tests, and suspected_cls, appending suspected
  # CLs and failures to the list.
  for failure in heuristic_result['failures']:
    if failure.get('tests'):
      for test in failure['tests']:
        for suspected_cl in test.get('suspected_cls', []):
          suspected_cls_with_failures.append([
              gtest.RemovePlatformFromStepName(failure['step_name']),
              suspected_cl['revision'], test['test_name']
          ])
    else:
      for suspected_cl in failure['suspected_cls']:
        suspected_cls_with_failures.append([
            gtest.RemovePlatformFromStepName(failure['step_name']),
            suspected_cl['revision'], None
        ])

  return suspected_cls_with_failures


def _LinkAnalysisToBuildFailureGroup(master_name, builder_name, build_number,
                                     failure_group_key):
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  analysis.failure_group_key = failure_group_key
  analysis.put()


def _CreateBuildFailureGroup(master_name,
                             builder_name,
                             build_number,
                             build_failure_type,
                             blame_list,
                             suspected_tuples,
                             output_nodes=None,
                             failed_steps_and_tests=None):
  new_group = WfFailureGroup.Create(master_name, builder_name, build_number)
  new_group.created_time = time_util.GetUTCNow()
  new_group.build_failure_type = build_failure_type
  new_group.blame_list = blame_list
  new_group.suspected_tuples = suspected_tuples
  new_group.output_nodes = output_nodes
  new_group.failed_steps_and_tests = failed_steps_and_tests
  new_group.put()


def _GetMatchingGroup(wf_failure_groups, blame_list, suspected_tuples):
  for group in wf_failure_groups:
    if _BlameListsIntersection(group.blame_list, blame_list):
      if suspected_tuples == group.suspected_tuples:
        return group

  return None


def GetMatchingFailureGroups(build_failure_type):
  earliest_time = time_util.GetUTCNow() - timedelta(
      seconds=waterfall_config.GetTryJobSettings().get(
          'max_seconds_look_back_for_group'))
  return WfFailureGroup.query(
      ndb.AND(WfFailureGroup.build_failure_type == build_failure_type,
              WfFailureGroup.created_time >= earliest_time)).fetch()


@ndb.transactional
def ReviveOrCreateTryJobEntity(master_name, builder_name, build_number,
                               force_try_job):
  """Checks try job entity to further determine if need a new try job.

  * If there is an entity for a running or completed try job, no need for new
    job.
  * If there is an entity for a failed try job, revive the entity and start a
    new job.
  * If there is no entity, create one.

  Returns:
    A bool to indicate if a try job entity is revived or created.
    The try job entities' key.
  """
  try_job_entity_revived_or_created = True
  try_job = WfTryJob.Get(master_name, builder_name, build_number)

  if try_job:
    if try_job.failed or force_try_job:
      try_job.status = analysis_status.PENDING
      try_job.put()
    else:
      try_job_entity_revived_or_created = False
  else:
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.put()

  return try_job_entity_revived_or_created, try_job.key


def IsBuildFailureUniqueAcrossPlatforms(master_name,
                                        builder_name,
                                        build_number,
                                        build_failure_type,
                                        blame_list,
                                        heuristic_result,
                                        groups,
                                        output_nodes=None,
                                        failed_steps_and_tests=None):
  """Checks if there is an existing group with the same failure and suspects."""
  suspected_tuples = sorted(_GetSuspectedCLsWithFailures(heuristic_result))
  existing_group = _GetMatchingGroup(groups, blame_list, suspected_tuples)

  # Create a new WfFailureGroup if we've encountered a unique build failure.
  if existing_group:
    logging.info('A group already exists, no need for a new try job.')
    _LinkAnalysisToBuildFailureGroup(master_name, builder_name, build_number, [
        existing_group.master_name, existing_group.builder_name,
        existing_group.build_number
    ])
  else:
    logging.info('A new try job should be run for this unique build failure.')
    _CreateBuildFailureGroup(
        master_name,
        builder_name,
        build_number,
        build_failure_type,
        blame_list,
        suspected_tuples,
        output_nodes=output_nodes,
        failed_steps_and_tests=failed_steps_and_tests)
    _LinkAnalysisToBuildFailureGroup(master_name, builder_name, build_number,
                                     [master_name, builder_name, build_number])

  return not existing_group


def NeedANewWaterfallTryJob(master_name, builder_name, build_number,
                            force_try_job):
  """Preliminary check if a new try job is needed.

  Checks if a tryserver is setup for the builder,
  and only runs for builds start within 24 hours, unless it's a forced rerun.
  """
  tryserver_mastername, tryserver_buildername = (
      waterfall_config.GetWaterfallTrybot(master_name, builder_name))

  if not tryserver_mastername or not tryserver_buildername:
    logging.info('%s, %s is not supported yet.', master_name, builder_name)
    return False

  if not force_try_job:
    build = WfBuild.Get(master_name, builder_name, build_number)

    if _ShouldBailOutForOutdatedBuild(build):
      logging.error('Build time %s is more than 24 hours old. '
                    'Try job will not be triggered.' % build.start_time)
      return False

  return True


def GetSuspectsFromHeuristicResult(heuristic_result):
  if not heuristic_result:
    return []

  suspected_revisions = set()
  for failure in heuristic_result.get('failures', []):
    for cl in failure['suspected_cls']:
      suspected_revisions.add(cl['revision'])
  return list(suspected_revisions)


def GetResultAnalysisStatus(analysis, result):
  """Returns the analysis status based on existing status and try job result.

  Args:
    analysis: The WfAnalysis entity corresponding to this try job.
    result: A result dict containing the result of this try job.

  Returns:
    A result_status code.
  """

  old_result_status = analysis.result_status

  # Only return an updated analysis result status if no results were already
  # found (by the heuristic-based approach) but were by the try job. Note it is
  # possible the heuristic-based result was triaged before the completion of
  # this try job.

  # TODO(chanli): Remove the case where result is a dict in the change of
  # refactoring identify_test_try_job_culprit_pipeline.
  try_job_found_culprit = result and (result.get('culprit') if isinstance(
      result, dict) else result.culprit)
  if (try_job_found_culprit and
      (old_result_status is None or
       old_result_status == result_status.NOT_FOUND_UNTRIAGED or
       old_result_status == result_status.NOT_FOUND_INCORRECT or
       old_result_status == result_status.NOT_FOUND_CORRECT)):
    return result_status.FOUND_UNTRIAGED

  return old_result_status


def GetUpdatedAnalysisResult(analysis, flaky_failures):
  if not analysis or not analysis.result or not analysis.result.get('failures'):
    return {}, False

  analysis_result = copy.deepcopy(analysis.result)
  all_flaky = swarming_util.UpdateAnalysisResult(analysis_result,
                                                 flaky_failures)

  return analysis_result, all_flaky


def GetBuildProperties(pipeline_input, try_job_type):
  master_name, builder_name, build_number = pipeline_input.build_key.GetParts()
  properties = {
      'recipe':
          'findit/chromium/%s' %
          (failure_type.GetDescriptionForFailureType(try_job_type)),
      'good_revision':
          pipeline_input.good_revision,
      'bad_revision':
          pipeline_input.bad_revision,
      'target_mastername':
          master_name,
      'referenced_build_url':
          buildbot.CreateBuildUrl(master_name, builder_name, build_number),
      'suspected_revisions':
          pipeline_input.suspected_revisions or [],
  }

  return properties


def TriggerTryJob(master_name, builder_name, tryserver_mastername,
                  tryserver_buildername, properties, additional_parameters,
                  try_job_type, cache_name, dimensions, notification_id):

  # Certain parts of the recipe depend on the 'mastername' property being set
  # to values like `tryserver.chromium.linux` etc., these values should
  # eventually be derived from the target mastername, but in order to stabilize
  # the trybots during the migration to luci-lite, we instead use the names of
  # the buildbot trybot masters. (As is the practice in other vitual trybot
  # builders, see for example
  # https://chromium.googlesource.com/chromium/src.git/+/infra/config/cr-buildbucket.cfg#139

  # TODO(crbug.com/787096): Remove these two lines once we have a better way of
  # telling the recipe how to configure the builder.
  if tryserver_buildername == 'findit_variable':
    # Get the matching buildbot try master.
    properties['mastername'] = waterfall_config.GetWaterfallTrybot(
        master_name, builder_name, force_buildbot=True)[0]

  try_job = buildbucket_client.TryJob(
      tryserver_mastername, tryserver_buildername, None, properties, [],
      additional_parameters, cache_name, dimensions)
  # This is a no-op if the tryjob is not on swarmbucket.
  swarming_util.AssignWarmCacheHost(try_job, cache_name, FinditHttpClient())
  error, build = buildbucket_client.TriggerTryJobs([try_job],
                                                   notification_id)[0]

  monitoring.OnTryJobTriggered(try_job_type, master_name, builder_name)

  if error:
    return None, error

  return build.id, None


@ndb.transactional
def CreateTryJobData(build_id,
                     try_job_key,
                     has_compile_targets,
                     has_heuristic_results,
                     try_job_type,
                     runner_id=None):
  try_job_data = WfTryJobData.Create(build_id)
  try_job_data.created_time = time_util.GetUTCNow()
  try_job_data.has_compile_targets = has_compile_targets
  try_job_data.has_heuristic_results = has_heuristic_results
  try_job_data.try_job_key = try_job_key
  try_job_data.try_job_type = failure_type.GetDescriptionForFailureType(
      try_job_type)
  try_job_data.runner_id = runner_id
  try_job_data.put()


def UpdateTryJob(master_name, builder_name, build_number, build_id,
                 try_job_type):
  try_job = WfTryJob.Get(master_name, builder_name, build_number)

  if try_job_type == failure_type.COMPILE:
    try_job.compile_results.append({'try_job_id': build_id})
  else:
    try_job.test_results.append({'try_job_id': build_id})
  try_job.try_job_ids.append(build_id)
  try_job.put()
  return try_job


def UpdateTryJobResultWithCulprit(try_job_result, new_result, try_job_id,
                                  culprits):
  if culprits:
    updated = False
    for result_to_update in try_job_result:
      if try_job_id == result_to_update['try_job_id']:
        result_to_update.update(new_result)
        updated = True
        break

    if not updated:
      try_job_result.append(new_result)


def PrepareParametersToScheduleTryJob(master_name,
                                      builder_name,
                                      build_number,
                                      failure_info,
                                      heuristic_result,
                                      urlsafe_try_job_key,
                                      force_buildbot=False):
  parameters = {}

  parameters['build_key'] = {
      'master_name': master_name,
      'builder_name': builder_name,
      'build_number': build_number
  }
  parameters['bad_revision'] = failure_info['builds'][str(build_number)][
      'chromium_revision']
  parameters['suspected_revisions'] = GetSuspectsFromHeuristicResult(
      heuristic_result)
  parameters['force_buildbot'] = force_buildbot
  parameters['urlsafe_try_job_key'] = urlsafe_try_job_key
  return parameters


def _GetError(buildbucket_response, buildbucket_error, timed_out, no_report):
  """Determines whether or not a try job error occured.

  Args:
    buildbucket_response: A dict of the json response from buildbucket.
    buildbucket_error: A BuildBucketError object returned from the call to
      buildbucket_client.GetTryJobs()
    timed_out: A bool whether or not Findit abandoned monitoring the try job.
    no_report: A bool whether we get result report.

  Returns:
    A tuple containing an error dict and number representing an error code, or
    (None, None) if no error was determined to have occured.
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
      # Generic buildbucket-reported error which can occur if an exception is
      # thrown, disk is full, compile fails during a test try job, etc.
      return ({
          'message': 'Buildbucket reported a general error.',
          'reason': UNKNOWN
      }, try_job_error.INFRA_FAILURE)
    elif buildbucket_failure_reason == 'INFRA_FAILURE':
      return ({
          'message': ('Try job encountered an infra issue during '
                      'execution.'),
          'reason':
              UNKNOWN
      }, try_job_error.INFRA_FAILURE)
    elif buildbucket_failure_reason:
      return ({
          'message': buildbucket_failure_reason,
          'reason': UNKNOWN
      }, try_job_error.UNKNOWN)

    # Check result_details_json for errors.
    result_details_json = json.loads(
        buildbucket_response.get('result_details_json', '{}')) or {}
    error = result_details_json.get('error', {})
    if error:
      return ({
          'message': 'Buildbucket reported an error.',
          'reason': error.get('message', UNKNOWN)
      }, try_job_error.CI_REPORTED_ERROR)

    if no_report:
      return ({
          'message': 'No result report was found.',
          'reason': UNKNOWN
      }, try_job_error.UNKNOWN)

  return None, None


def UpdateTryJobMetadata(try_job_data,
                         try_job_type=None,
                         buildbucket_build=None,
                         buildbucket_error=None,
                         timed_out=None,
                         report=None,
                         already_set_started=True,
                         callback_url=None,
                         callback_target=None):
  buildbucket_response = {}

  if buildbucket_build:
    try_job_data.request_time = (
        try_job_data.request_time or
        time_util.MicrosecondsToDatetime(buildbucket_build.request_time))

    # If start_time hasn't been set, use request_time.
    start_time = try_job_data.request_time
    if (buildbucket_build.status == BuildbucketBuild.STARTED and
        not already_set_started):
      # It is possible a fast build goes from
      # 'SCHEDULED' to 'COMPLETED' between queries, so start_time may be
      # unavailable.
      start_time = time_util.MicrosecondsToDatetime(
          buildbucket_build.updated_time)

    try_job_data.start_time = try_job_data.start_time or start_time

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
    monitoring.OnTryJobError(try_job_type, error_dict, try_job_data.master_name,
                             try_job_data.builder_name)

  try_job_data.callback_url = try_job_data.callback_url or callback_url
  try_job_data.callback_target = try_job_data.callback_target or callback_target

  try_job_data.put()


def _UpdateLastBuildbucketResponse(try_job_data, build):
  if not build or not build.response:
    return
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


@ndb.transactional
def _UpdateTryJobResult(urlsafe_try_job_key,
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
  else:
    # Normally result for current try job should have been saved in
    # schedule_try_job_pipeline, so this branch shouldn't be reached.
    result_to_update.append(result)

  if status == BuildbucketBuild.STARTED:
    try_job.status = analysis_status.RUNNING

  try_job.put()

  return result_to_update


def GetOrCreateTryJobData(try_job_type, try_job_id, urlsafe_try_job_key):
  if try_job_type == failure_type.FLAKY_TEST:
    try_job_kind = FlakeTryJobData
  else:
    try_job_kind = WfTryJobData
  try_job_data = try_job_kind.Get(try_job_id)

  if not try_job_data:
    logging.warning('%(kind)s entity does not exist for id %(id)s: creating it',
                    {'kind': try_job_kind,
                     'id': try_job_id})
    try_job_data = try_job_kind.Create(try_job_id)
    try_job_data.try_job_key = ndb.Key(urlsafe=urlsafe_try_job_key)

  return try_job_data


def InitializeParams(try_job_id, try_job_type, urlsafe_try_job_key):
  timeout_hours = waterfall_config.GetTryJobSettings().get('job_timeout_hours')
  default_pipeline_wait_seconds = waterfall_config.GetTryJobSettings().get(
      'server_query_interval_seconds')
  max_error_times = waterfall_config.GetTryJobSettings().get(
      'allowed_response_error_times')

  deadline = time.time() + timeout_hours * 60 * 60
  already_set_started = False
  backoff_time = default_pipeline_wait_seconds
  error_count = 0

  return {
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


def _GetUpdatedParams(params, **kwargs):
  new_params = copy.deepcopy(params)
  for key, value in kwargs.iteritems():
    new_params[key] = value
  return new_params


def OnGetTryJobError(params, try_job_data, build, error):
  if params['error_count'] < params['max_error_times']:
    error_count = params['error_count'] + 1
    return _GetUpdatedParams(params, error_count=error_count)
  else:
    # Buildbucket has responded error more than 5 times, retry pipeline.
    UpdateTryJobMetadata(try_job_data, params['try_job_type'], build, error,
                         False)
    raise exceptions.RetryException(error.reason, error.message)


def OnTryJobCompleted(params, try_job_data, build, error):
  try_job_id = params['try_job_id']
  try_job_type = params['try_job_type']
  swarming_task_id = buildbot.GetSwarmingTaskIdFromUrl(build.url)

  # We want to retry 404s due to logdog's propagation delay (inherent to
  # pubsub) of up to 3 minutes.
  http_client = FinditHttpClient(interceptor=HttpClientMetricsInterceptor(
      no_retry_codes=[200, 302, 401, 403, 409, 501]))

  if swarming_task_id:
    try:
      report = swarming_util.GetStepLog(try_job_id, 'report', http_client,
                                        'report')
      if report:
        _RecordCacheStats(build, report)
    except (ValueError, TypeError) as e:
      report = {}
      logging.exception('Failed to load result report for swarming/%s '
                        'due to exception %s.' % (swarming_task_id, e.message))
  else:
    try_job_master_name, try_job_builder_name, try_job_build_number = (
        buildbot.ParseBuildUrl(build.url))

    try:
      report = buildbot.GetStepLog(try_job_master_name, try_job_builder_name,
                                   try_job_build_number, 'report', http_client,
                                   'report')
    except (ValueError, TypeError) as e:
      report = {}
      logging.exception(
          'Failed to load result report for %s/%s/%s due to exception %s.' %
          (try_job_master_name, try_job_builder_name, try_job_build_number,
           e.message))

  UpdateTryJobMetadata(try_job_data, try_job_type, build, error, False, report
                       if report else {})
  result_to_update = _UpdateTryJobResult(params['urlsafe_try_job_key'],
                                         try_job_type, try_job_id, build.url,
                                         BuildbucketBuild.COMPLETED, report)
  return result_to_update[-1]


def OnTryJobRunning(params, try_job_data, build, error):
  try_job_id = params['try_job_id']
  try_job_type = params['try_job_type']
  if (not params['already_set_started'] and
      build.status == BuildbucketBuild.STARTED):
    # It is possible this branch is skipped if a fast build goes from
    # 'SCHEDULED' to 'COMPLETED' between queries.
    _UpdateTryJobResult(params['urlsafe_try_job_key'], try_job_type, try_job_id,
                        build.url, BuildbucketBuild.STARTED)

    # Update as much try job metadata as soon as possible to avoid data
    # loss in case of errors.
    UpdateTryJobMetadata(
        try_job_data,
        try_job_type,
        build,
        error,
        False,
        None,
        already_set_started=False)

    return _GetUpdatedParams(
        params,
        error_count=0,
        backoff_time=params['default_pipeline_wait_seconds'],
        already_set_started=True)
  return None


def GetCurrentWaterfallTryJobID(urlsafe_try_job_key, runner_id):
  try_job = (ndb.Key(urlsafe=urlsafe_try_job_key).get()
             if urlsafe_try_job_key else None)
  if not try_job or not try_job.try_job_ids:
    return None

  try_job_ids = try_job.try_job_ids
  for i in xrange(len(try_job_ids) - 1, -1, -1):
    try_job_id = try_job_ids[i]
    try_job_data = WfTryJobData.Get(try_job_id)
    if not try_job_data:
      continue

    if try_job_data.runner_id == runner_id:
      return try_job_id
  return None
