# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for test-try-job-related operations.

It provides functions to:
  * Decide if a new test try job is needed.
  * Get reliable failures based on swarming rerun results.
  * Get parameters for starting a new test try job.
"""

from collections import defaultdict
import copy
import logging

from google.appengine.ext import ndb

from common import exceptions
from common.waterfall import failure_type
from libs import analysis_status
from model import analysis_approach_type
from model import result_status
from model.base_build_model import BaseBuildModel
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from services import build_failure_analysis
from services import git
from services import try_job as try_job_service
from services.parameters import FailureToCulpritMap
from services.parameters import RunTestTryJobParameters
from services.parameters import TestTryJobResult
from services.test_failure import ci_test_failure
from services.test_failure import test_failure_analysis
from waterfall import suspected_cl_util
from waterfall import waterfall_config


def _GetStepsAndTests(failed_steps):
  """Extracts failed steps and tests from failed_steps data structure.

  Args:
    failed_steps(TestFailedSteps): Failed steps and test information.
    Example of a serialized TestFailedSteps:
    {
        'step_a': {
            'last_pass': 4,
            'tests': {
                'test1': {
                    'last_pass': 4,
                    'current_failure': 6,
                    'first_failure': 5
                },
                'test2': {
                    'last_pass': 4,
                    'current_failure': 6,
                    'first_failure': 5
                }
            },
            'current_failure': 6,
            'first_failure': 5,
            'list_isolated_data': [
                {
                    'isolatedserver': 'https://isolateserver.appspot.com',
                    'namespace': 'default-gzip',
                    'digest': 'abcd'
                }
            ]
        },
        'step_b': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

  Returns:
    failed_steps_and_tests: Sorted list of lists of step and test names.
    Example:
    [
        ['step_a', 'test1'],
        ['step_a', 'test2'],
        ['step_b', None]
    ]
  """

  failed_steps_and_tests = []

  if not failed_steps:
    return failed_steps_and_tests

  for step_name, step in failed_steps.iteritems():
    for test_name in (step.tests or [None]):
      failed_steps_and_tests.append([step_name, test_name])

  return sorted(failed_steps_and_tests)


def _GetMatchingTestFailureGroups(failed_steps_and_tests):
  groups = try_job_service.GetMatchingFailureGroups(failure_type.TEST)
  return [
      group for group in groups
      if group.failed_steps_and_tests == failed_steps_and_tests
  ]


def _IsTestFailureUniqueAcrossPlatforms(master_name, builder_name, build_number,
                                        build_failure_type, blame_list,
                                        failed_steps, heuristic_result):

  if build_failure_type != failure_type.TEST:
    logging.info('Expected test failure but get %s failure.' %
                 failure_type.GetDescriptionForFailureType(build_failure_type))
    return True

  failed_steps_and_tests = _GetStepsAndTests(failed_steps)
  if not failed_steps_and_tests:
    return True
  groups = _GetMatchingTestFailureGroups(failed_steps_and_tests)
  suspected_cls_with_failures = (
      test_failure_analysis.GetSuspectedCLsWithFailures(
          master_name, builder_name, build_number, heuristic_result))

  # TODO(crbug/808699): update this function call when refactor
  # start_compile_try_job_pipeline.
  return try_job_service.IsBuildFailureUniqueAcrossPlatforms(
      master_name,
      builder_name,
      build_number,
      build_failure_type,
      blame_list,
      suspected_cls_with_failures,
      groups,
      failed_steps_and_tests=failed_steps_and_tests)


def _HasBuildKeyForBuildInfoInFailureResultMap(master_name, builder_name,
                                               build_number):
  """Checks if there is any first failed test."""
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  failure_result_map = analysis.failure_result_map
  current_build_key = BaseBuildModel.CreateBuildId(master_name, builder_name,
                                                   build_number)
  for step_keys in failure_result_map.itervalues():
    for test_key in step_keys.itervalues():
      if test_key == current_build_key:
        return True
  return False


def _NeedANewTestTryJob(start_test_try_job_inputs):
  """Decides if a new test try job is needed.

  A new test try job is needed if:
  1. It passed preliminary checks in try_job_service.NeedANewWaterfallTryJob,
  2. It's for a test failure,
  3. It contains some first failed steps/tests

  Returns:
    A bool to indicate if a new try job is needed.
  """
  master_name, builder_name, build_number = (
      start_test_try_job_inputs.build_key.GetParts())
  force = start_test_try_job_inputs.force
  build_completed = start_test_try_job_inputs.build_completed

  # TODO(crbug/808699):  update this function call when refactor
  # start_compile_try_job_pipeline.
  need_new_try_job = try_job_service.NeedANewWaterfallTryJob(
      master_name,
      builder_name,
      build_number,
      force,
      build_completed=build_completed)
  if not need_new_try_job:
    return False

  failure_info = start_test_try_job_inputs.heuristic_result.failure_info
  if not failure_info or failure_info.failure_type is None:
    return False

  try_job_type = failure_info.failure_type
  if try_job_type != failure_type.TEST:
    logging.error('Checking for a test try job but got a %s failure.',
                  failure_type.GetDescriptionForFailureType(try_job_type))
    return False

  consistent_failures = start_test_try_job_inputs.consistent_failures

  if (not force and
      waterfall_config.ShouldSkipTestTryJobs(master_name, builder_name)):
    logging.info('Test try jobs on %s, %s are not supported yet.', master_name,
                 builder_name)
    return False

  if not consistent_failures.consistent_failures:
    # consistent_failures is empty. Either tests are flaky or task failed.
    logging.info(
        'All tests are flaky or tasks failed, no try job will be triggered.')
    return False

  return _HasBuildKeyForBuildInfoInFailureResultMap(master_name, builder_name,
                                                    build_number)


def GetInformationToStartATestTryJob(start_test_try_job_inputs):
  """Checks if can start a new test try job and gets parameters to start it.

  Returns:
    A bool to indicate if a new try job is needed and can be started.
    A dict of parameters to run the try job if a new one is needed.
  """
  need_new_try_job = _NeedANewTestTryJob(start_test_try_job_inputs)
  if not need_new_try_job:
    return False, None

  master_name, builder_name, build_number = (
      start_test_try_job_inputs.build_key.GetParts())
  force = start_test_try_job_inputs.force
  failure_info = start_test_try_job_inputs.heuristic_result.failure_info
  heuristic_result = start_test_try_job_inputs.heuristic_result.heuristic_result
  try_job_type = failure_info.failure_type
  consistent_failures = start_test_try_job_inputs.consistent_failures

  # TODO(chanli): enable the feature to trigger single try job for a group
  # when notification is ready.
  # We still call _IsBuildFailureUniqueAcrossPlatforms just so we have data for
  # failure groups.

  # TODO(chanli): Add checking for culprits of the group when enabling
  # single try job: add current build to suspected_cl.builds if the try job for
  # this group has already completed.
  _IsTestFailureUniqueAcrossPlatforms(
      master_name, builder_name, build_number, try_job_type,
      failure_info.builds[str(build_number)].blame_list,
      failure_info.failed_steps, heuristic_result)

  try_job_was_created, urlsafe_try_job_key = (
      try_job_service.ReviveOrCreateTryJobEntity(master_name, builder_name,
                                                 build_number, force))
  can_start_new_try_job = need_new_try_job and try_job_was_created

  if not can_start_new_try_job:
    return False, None

  parameters = GetParametersToScheduleTestTryJob(
      master_name, builder_name, build_number, failure_info, heuristic_result,
      urlsafe_try_job_key, consistent_failures)
  if not parameters.good_revision:
    # No last_pass in saved in failure_info.
    return False, None

  return True, parameters


def _GetLastPassTest(build_number, failed_steps):
  for step_failure in failed_steps.itervalues():
    for test_failure in (step_failure.tests or {}).itervalues():
      if (test_failure.first_failure == build_number and
          test_failure.last_pass is not None):
        return test_failure.last_pass
  return None


def _GetGoodRevisionTest(master_name, builder_name, build_number, failure_info):
  last_pass = _GetLastPassTest(build_number, failure_info.failed_steps)
  if last_pass is None:
    logging.warning(
        'Couldn"t start try job for build %s, %s, %d because'
        ' last_pass is not found.', master_name, builder_name, build_number)
    return None

  return failure_info.builds[str(last_pass)].chromium_revision


def GetParametersToScheduleTestTryJob(master_name, builder_name, build_number,
                                      failure_info, heuristic_result,
                                      urlsafe_try_job_key, consistent_failures):
  """Generates RunTestTryJobParameters to trigger a test try job."""
  # TODO(crbug/808699):  update this function call when refactor
  # start_compile_try_job_pipeline.
  parameters = try_job_service.PrepareParametersToScheduleTryJob(
      master_name, builder_name, build_number, failure_info, heuristic_result
      if heuristic_result else None, urlsafe_try_job_key)

  parameters['good_revision'] = _GetGoodRevisionTest(master_name, builder_name,
                                                     build_number, failure_info)
  parameters['targeted_tests'] = (
      consistent_failures.consistent_failures.ToSerializable()
      if consistent_failures else {})

  return RunTestTryJobParameters.FromSerializable(parameters)


def GetReliableTests(master_name, builder_name, build_number, failure_info):
  task_results = {}
  for step_name, step_failure in failure_info['failed_steps'].iteritems():
    if not ci_test_failure.AnyTestHasFirstTimeFailure(
        step_failure.get('tests', {}), build_number):
      continue
    task = WfSwarmingTask.Get(master_name, builder_name, build_number,
                              step_name)

    if not task or not task.classified_tests:
      logging.error('No result for swarming task %s/%s/%s/%s' %
                    (master_name, builder_name, build_number, step_name))
      continue

    if not task.reliable_tests:
      continue

    task_results[task.canonical_step_name or step_name] = task.reliable_tests

  return task_results


def GetBuildProperties(pipeline_input):
  properties = try_job_service.GetBuildProperties(pipeline_input,
                                                  failure_type.TEST)
  properties['target_testername'] = pipeline_input.build_key.builder_name

  return properties


def _GetResultAnalysisStatus(analysis, result, all_flaked=False):
  """Returns the analysis status based on existing status and try job result.

  Args:
    analysis: The WfAnalysis entity corresponding to this try job.
    result: A result dict containing the result of this try job.
    all_flaked: A flag indicates if all failures are flaky.

  Returns:
    A result_status code.
  """
  if all_flaked:
    return result_status.FLAKY

  return try_job_service.GetResultAnalysisStatus(analysis, result)


def _GetTestFailureCausedByCL(result):
  if not result:
    return None

  failures = {}
  for step_name, step_result in result.iteritems():
    if step_result.status == 'failed':
      failures[step_name] = step_result.failures

  return failures


def _GetUpdatedSuspectedCLs(analysis, result, culprits):
  """Returns a list of suspected CLs.

  Args:
    analysis: The WfAnalysis entity corresponding to this try job.
    result: A result dict containing the result of this try job.
    culprits: A list of suspected CLs found by the try job.

  Returns:
    A combined list of suspected CLs from those already in analysis and those
    found by this try job.
  """
  suspected_cls = analysis.suspected_cls[:] if analysis.suspected_cls else []
  suspected_cl_revisions = [cl['revision'] for cl in suspected_cls]

  for revision, try_job_suspected_cl in culprits.iteritems():
    suspected_cl_copy = copy.deepcopy(try_job_suspected_cl)
    if revision not in suspected_cl_revisions:
      suspected_cl_revisions.append(revision)
      failures = _GetTestFailureCausedByCL(
          result.report.result.get(revision) if result else None)
      suspected_cl_copy['failures'] = failures
      suspected_cl_copy['top_score'] = None
      suspected_cls.append(suspected_cl_copy)

  return suspected_cls


def _GetUpdatedAnalysisResult(analysis, flaky_failures):
  if not analysis or not analysis.result or not analysis.result.get('failures'):
    return {}, False

  return test_failure_analysis.UpdateAnalysisResultWithFlakeInfo(
      analysis.result, flaky_failures)


def FindCulpritForEachTestFailure(result):
  culprit_map = defaultdict(dict)
  failed_revisions = set()

  # Recipe should return culprits with the format as:
  # 'culprits': {
  #     'step1': {
  #         'test1': 'rev1',
  #         'test2': 'rev2',
  #         ...
  #     },
  #     ...
  # }
  if result.report.culprits:
    for step_name, tests in result.report.culprits.iteritems():
      culprit_map[step_name]['tests'] = {}
      for test_name, revision in tests.iteritems():
        culprit_map[step_name]['tests'][test_name] = {'revision': revision}
        failed_revisions.add(revision)
  return culprit_map, list(failed_revisions)


def UpdateCulpritMapWithCulpritInfo(culprit_map, culprits):
  """Fills in commit_position and review url for each failed rev in map."""
  for step_culprit in culprit_map.values():
    for test_culprit in (step_culprit.get('tests') or {}).values():
      test_revision = test_culprit['revision']
      test_culprit.update(culprits[test_revision])


def GetCulpritDataForTest(culprit_map):
  """Gets culprit revision for each failure for try job metadata."""
  culprit_data = {}
  for step, step_culprit in culprit_map.iteritems():
    culprit_data[step] = {}
    for test, test_culprit in step_culprit['tests'].iteritems():
      culprit_data[step][test] = test_culprit['revision']
  return culprit_data


@ndb.transactional
def UpdateTryJobResult(parameters, culprits):
  """ Updates try job result with culprit info.
  Args:
    parameters (IdentifyTestTryJobCulpritParameters): Parameters to identify
      culprit from try job result.
    culprits (dict): A dict of culprits info: revision, repo_name,
      commit_position and url.

  """
  master_name, builder_name, build_number = (parameters.build_key.GetParts())
  try_job = WfTryJob.Get(master_name, builder_name, build_number)
  new_result = parameters.result.ToSerializable() if parameters.result else {}
  try_job_id = parameters.result.try_job_id if parameters.result else None
  if culprits:
    try_job_service.UpdateTryJobResult(try_job.test_results, new_result,
                                       try_job_id)
  try_job.status = analysis_status.COMPLETED
  try_job.put()


@ndb.transactional
def UpdateWfAnalysisWithTryJobResult(master_name, builder_name, build_number,
                                     result, culprits, flaky_failures):
  if not culprits and not flaky_failures:
    return

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  # Update analysis result and suspected CLs with results of this try job if
  # culprits were found or failures are flaky.
  updated_result, all_flaked = _GetUpdatedAnalysisResult(
      analysis, flaky_failures)
  updated_result_status = _GetResultAnalysisStatus(analysis, result, all_flaked)
  updated_suspected_cls = _GetUpdatedSuspectedCLs(analysis, result, culprits)
  analysis.UpdateWithNewFindings(
      updated_result_status=updated_result_status,
      updated_suspected_cls=updated_suspected_cls,
      updated_result=updated_result,
      flaky_tests=flaky_failures)


def UpdateSuspectedCLs(master_name, builder_name, build_number, culprits,
                       result):
  if not culprits:
    return

  # Creates or updates each suspected_cl.
  for culprit in culprits.values():
    revision = culprit['revision']
    failures = _GetTestFailureCausedByCL(
        result.report.result.get(revision) if result else None)

    suspected_cl_util.UpdateSuspectedCL(culprit['repo_name'], revision,
                                        culprit.get('commit_position'),
                                        analysis_approach_type.TRY_JOB,
                                        master_name, builder_name, build_number,
                                        failure_type.TEST, failures, None)


def IdentifyTestTryJobCulprits(parameters):
  """Processes try job result and identifies culprit.

  Args:
    parameters (IdentifyTestTryJobCulpritParameters): Parameters to identify
      culprit from try job result.
  """
  culprits = None
  flaky_failures = {}

  master_name, builder_name, build_number = parameters.build_key.GetParts()
  result = parameters.result
  try_job_id = result.try_job_id if result else None
  failure_to_culprit_map = None
  if try_job_id and result and result.report:
    culprit_map, failed_revisions = FindCulpritForEachTestFailure(result)
    culprits = try_job_service.GetCulpritsWithoutNoBlameAccountsCLS(
        git.GetCommitsInfo(failed_revisions))

    if not culprits:
      flaky_failures = result.report.flakes
    if culprits:
      try_job_data = WfTryJobData.Get(try_job_id)
      UpdateCulpritMapWithCulpritInfo(culprit_map, culprits)
      failure_to_culprit_map = GetCulpritDataForTest(culprit_map)
      try_job_data.culprits = failure_to_culprit_map
      try_job_data.put()
      result.culprit = culprit_map

  # Store try-job results.
  UpdateTryJobResult(parameters, culprits)

  # Saves cls found by heuristic approach for later use.
  # This part must be before UpdateWfAnalysisWithTryJobResult().
  heuristic_cls = build_failure_analysis.GetHeuristicSuspectedCLs(
      master_name, builder_name, build_number)

  # Add try-job results to WfAnalysis.
  UpdateWfAnalysisWithTryJobResult(master_name, builder_name, build_number,
                                   result, culprits, flaky_failures)

  # TODO (chanli): Update suspected_cl for builds in the same group with
  # current build.
  # Updates suspected_cl.
  UpdateSuspectedCLs(master_name, builder_name, build_number, culprits, result)

  return culprits, heuristic_cls, FailureToCulpritMap.FromSerializable(
      failure_to_culprit_map)


def ScheduleTestTryJob(parameters, notification_id):
  master_name, builder_name, build_number = (parameters.build_key.GetParts())

  properties = GetBuildProperties(parameters)
  additional_parameters = {'tests': parameters.targeted_tests}

  tryserver_mastername, tryserver_buildername = try_job_service.GetTrybot()

  build_id, error = try_job_service.TriggerTryJob(
      master_name, builder_name, tryserver_mastername, tryserver_buildername,
      properties, additional_parameters,
      failure_type.GetDescriptionForFailureType(failure_type.TEST),
      parameters.cache_name, parameters.dimensions, notification_id)

  if error:
    raise exceptions.RetryException(error.reason, error.message)
  try_job = try_job_service.UpdateTryJob(
      master_name, builder_name, build_number, build_id, failure_type.TEST)

  # Create a corresponding WfTryJobData entity to capture as much metadata as
  # early as possible.
  try_job_service.CreateTryJobData(
      build_id,
      try_job.key,
      False,
      bool(parameters.suspected_revisions),
      failure_type.TEST,
      runner_id=notification_id)

  return build_id


def OnTryJobStateChanged(try_job_id, build_json, run_try_job_params):
  """Updates TryJobData entity with new build state.

  Args:
    try_job_id (str): The build id of the try job.
    build_json (dict): The up-to-date build info.
    run_try_job_params(RunTestTryJobParameters): Parameters to run the try job.

  Returns:
    TestTryJobResult if the try job has completed; otherwise None.
  """
  result, state = try_job_service.OnTryJobStateChanged(
      try_job_id, failure_type.TEST, build_json)

  if state in [analysis_status.COMPLETED, analysis_status.ERROR]:
    # TODO(crbug/869684): Use a gauge metric to track intermittent statuses.
    master_name, builder_name, build_number = (
        run_try_job_params.build_key.GetParts())
    for step_name in run_try_job_params.targeted_tests or {}:
      test_failure_analysis.RecordTestFailureAnalysisStateChange(
          master_name, builder_name, build_number, step_name, state,
          analysis_approach_type.TRY_JOB)

  if result is not None:
    result = TestTryJobResult.FromSerializable(result)
  return result


def OnTryJobTimeout(try_job_id, run_try_job_params):
  try_job_service.OnTryJobTimeout(try_job_id, failure_type.TEST)
  master_name, builder_name, build_number = (
      run_try_job_params.build_key.GetParts())
  for step_name in run_try_job_params.targeted_tests or {}:
    test_failure_analysis.RecordTestFailureAnalysisStateChange(
        master_name, builder_name, build_number, step_name,
        analysis_status.ERROR, analysis_approach_type.TRY_JOB)
