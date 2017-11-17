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
"""

import copy
from datetime import timedelta
import logging

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from libs import analysis_status
from libs import time_util
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_failure_group import WfFailureGroup
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from services import gtest
from services import monitoring
from waterfall import buildbot
from waterfall import swarming_util
from waterfall import waterfall_config


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
  try_job_found_culprit = result and result.get('culprit')
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
def CreateTryJobData(build_id, try_job_key, has_compile_targets,
                     has_heuristic_results, try_job_type):
  try_job_data = WfTryJobData.Create(build_id)
  try_job_data.created_time = time_util.GetUTCNow()
  try_job_data.has_compile_targets = has_compile_targets
  try_job_data.has_heuristic_results = has_heuristic_results
  try_job_data.try_job_key = try_job_key
  try_job_data.try_job_type = failure_type.GetDescriptionForFailureType(
      try_job_type)
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
  return parameters
