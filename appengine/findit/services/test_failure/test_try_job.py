# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for test-try-job-related operations.

It provides functions to:
  * Decide if a new test try job is needed.
  * Get reliable failures based on swarming rerun results.
  * Get parameters for starting a new test try job.
"""

import logging

from common.waterfall import failure_type
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from services import try_job
from services.test_failure import ci_test_failure
from waterfall import build_util
from waterfall import swarming_util
from waterfall import waterfall_config


def _GetStepsAndTests(failed_steps):
  """Extracts failed steps and tests from failed_steps data structure.

  Args:
    failed_steps: Failed steps and test, plus extra information. Example:
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
    for test_name in step.get('tests', [None]):
      failed_steps_and_tests.append([step_name, test_name])

  return sorted(failed_steps_and_tests)


def _GetMatchingTestFailureGroups(failed_steps_and_tests):
  groups = try_job.GetMatchingFailureGroups(failure_type.TEST)
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

  return try_job.IsBuildFailureUniqueAcrossPlatforms(
      master_name,
      builder_name,
      build_number,
      build_failure_type,
      blame_list,
      heuristic_result,
      groups,
      failed_steps_and_tests=failed_steps_and_tests)


def _HasBuildKeyForBuildInfoInFailureResultMap(master_name, builder_name,
                                               build_number):
  """Checks if there is any first failed test."""
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  failure_result_map = analysis.failure_result_map
  current_build_key = build_util.CreateBuildId(master_name, builder_name,
                                               build_number)
  for step_keys in failure_result_map.itervalues():
    for test_key in step_keys.itervalues():
      if test_key == current_build_key:
        return True
  return False


def _NeedANewTestTryJob(master_name, builder_name, build_number, force_try_job):

  if (not force_try_job and
      waterfall_config.ShouldSkipTestTryJobs(master_name, builder_name)):
    logging.info('Test try jobs on %s, %s are not supported yet.', master_name,
                 builder_name)
    return False

  return _HasBuildKeyForBuildInfoInFailureResultMap(master_name, builder_name,
                                                    build_number)


def NeedANewTestTryJob(master_name,
                       builder_name,
                       build_number,
                       failure_info,
                       heuristic_result,
                       force_try_job=False):
  """Decides if a new test try job is needed.

  A new test try job is needed if:
  1. It passed preliminary checks in try_job.NeedANewWaterfallTryJob,
  2. It's for a test failure,
  3. It contains some first failed steps/tests,
  4. There is no other running or completed try job.

  Returns:
    A bool to indicate if a new try job is needed.
    A key to the entity of the try job.
  """
  need_new_try_job = try_job.NeedANewWaterfallTryJob(
      master_name, builder_name, build_number, force_try_job)

  if not need_new_try_job:
    return False, None

  try_job_type = failure_info['failure_type']
  if try_job_type != failure_type.TEST:
    logging.error('Checking for a test try job but got a %s failure.',
                  failure_type.GetDescriptionForFailureType(try_job_type))
    return False, None

  need_new_try_job = _NeedANewTestTryJob(master_name, builder_name,
                                         build_number, force_try_job)

  # TODO(chanli): enable the feature to trigger single try job for a group
  # when notification is ready.
  # We still call _IsBuildFailureUniqueAcrossPlatforms just so we have data for
  # failure groups.

  # TODO(chanli): Add checking for culprits of the group when enabling
  # single try job: add current build to suspected_cl.builds if the try job for
  # this group has already completed.
  if need_new_try_job:
    _IsTestFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, try_job_type,
        failure_info['builds'][str(build_number)]['blame_list'],
        failure_info['failed_steps'], heuristic_result)

  try_job_was_created, try_job_key = try_job.ReviveOrCreateTryJobEntity(
      master_name, builder_name, build_number, force_try_job)
  need_new_try_job = need_new_try_job and try_job_was_created
  return need_new_try_job, try_job_key


def _GetLastPassTest(build_number, failed_steps):
  for step_failure in failed_steps.itervalues():
    for test_failure in step_failure.get('tests', {}).itervalues():
      if (test_failure['first_failure'] == build_number and
          test_failure.get('last_pass') is not None):
        return test_failure['last_pass']
  return None


def _GetGoodRevisionTest(master_name, builder_name, build_number, failure_info):
  last_pass = _GetLastPassTest(build_number, failure_info['failed_steps'])
  if last_pass is None:
    logging.warning('Couldn"t start try job for build %s, %s, %d because'
                    ' last_pass is not found.', master_name, builder_name,
                    build_number)
    return None

  return failure_info['builds'][str(last_pass)]['chromium_revision']


def GetParametersToScheduleTestTryJob(master_name, builder_name, build_number,
                                      failure_info, heuristic_result):
  parameters = {}
  parameters['bad_revision'] = failure_info['builds'][str(build_number)][
      'chromium_revision']
  parameters['suspected_revisions'] = try_job.GetSuspectsFromHeuristicResult(
      heuristic_result)
  parameters['good_revision'] = _GetGoodRevisionTest(master_name, builder_name,
                                                     build_number, failure_info)

  parameters['task_results'] = GetReliableTests(master_name, builder_name,
                                                build_number, failure_info)

  parent_mastername = failure_info.get('parent_mastername') or master_name
  parent_buildername = failure_info.get('parent_buildername') or (builder_name)
  parameters['dimensions'] = waterfall_config.GetTrybotDimensions(
      parent_mastername, parent_buildername)
  parameters['cache_name'] = swarming_util.GetCacheName(parent_mastername,
                                                        parent_buildername)
  return parameters


# TODO(chanli@): move this function to swarming task related module.
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
