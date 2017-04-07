# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import timedelta
import logging

from google.appengine.ext import ndb

from common.waterfall import failure_type
from libs import analysis_status
from libs import time_util
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_failure_group import WfFailureGroup
from model.wf_try_job import WfTryJob
from waterfall import build_util
from waterfall import waterfall_config


def _ShouldBailOutForOutdatedBuild(build):
  return (build.start_time is None or
          (time_util.GetUTCNow() - build.start_time).days > 0)


def _BlameListsIntersection(blame_list_1, blame_list_2):
  return set(blame_list_1) & set(blame_list_2)


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


def _RemovePlatformFromStepName(step_name):
  """Returns step name without platform.

  Args:
    step_name: Raw step name. Example: 'net_unittests on Windows-10'.

  Returns:
    Step name without platform or the string ' on '. Example: 'net_unittests'.
  """
  separator = ' on '
  return step_name.split(separator)[0]


def GetSuspectedCLsWithFailures(heuristic_result):
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
              _RemovePlatformFromStepName(failure['step_name']),
              suspected_cl['revision'],
              test['test_name']])
    else:
      for suspected_cl in failure['suspected_cls']:
        suspected_cls_with_failures.append([
            _RemovePlatformFromStepName(failure['step_name']),
            suspected_cl['revision'],
            None])

  return suspected_cls_with_failures


def _LinkAnalysisToBuildFailureGroup(
    master_name, builder_name, build_number, failure_group_key):
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  analysis.failure_group_key = failure_group_key
  analysis.put()


def _CreateBuildFailureGroup(
    master_name, builder_name, build_number, build_failure_type, blame_list,
    suspected_tuples, output_nodes=None, failed_steps_and_tests=None):
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


def _GetOutputNodes(signals):
  if not signals or 'compile' not in signals:
    return []

  # Compile failures with no output nodes will be considered unique.
  return signals['compile'].get('failed_output_nodes', [])


def _GetMatchingFailureGroups(build_failure_type):
  earliest_time = time_util.GetUTCNow() - timedelta(
      seconds=waterfall_config.GetTryJobSettings().get(
          'max_seconds_look_back_for_group'))
  return WfFailureGroup.query(ndb.AND(
      WfFailureGroup.build_failure_type == build_failure_type,
      WfFailureGroup.created_time >= earliest_time)).fetch()


def _GetMatchingCompileFailureGroups(output_nodes):
  groups = _GetMatchingFailureGroups(failure_type.COMPILE)
  # Output nodes should already be unique and sorted.
  return [group for group in groups if group.output_nodes == output_nodes]


def _GetMatchingTestFailureGroups(failed_steps_and_tests):
  groups = _GetMatchingFailureGroups(failure_type.TEST)
  return [group for group in groups
          if group.failed_steps_and_tests == failed_steps_and_tests]


def _IsBuildFailureUniqueAcrossPlatforms(
    master_name, builder_name, build_number, build_failure_type, blame_list,
    failed_steps, signals, heuristic_result):
  output_nodes = None
  failed_steps_and_tests = None

  if build_failure_type == failure_type.COMPILE:
    output_nodes = _GetOutputNodes(signals)
    if not output_nodes:
      return True
    groups = _GetMatchingCompileFailureGroups(output_nodes)
  elif build_failure_type == failure_type.TEST:
    failed_steps_and_tests = _GetStepsAndTests(failed_steps)
    if not failed_steps_and_tests:
      return True
    groups = _GetMatchingTestFailureGroups(failed_steps_and_tests)
  else:
    logging.info('Grouping %s failures is not supported. Only Compile and Test'
                 'failures can be grouped.' %
                 failure_type.GetDescriptionForFailureType(build_failure_type))
    return True

  suspected_tuples = sorted(GetSuspectedCLsWithFailures(heuristic_result))
  existing_group = _GetMatchingGroup(groups, blame_list, suspected_tuples)

  # Create a new WfFailureGroup if we've encountered a unique build failure.
  if existing_group:
    logging.info('A group already exists, no need for a new try job.')
    _LinkAnalysisToBuildFailureGroup(
        master_name, builder_name, build_number,
        [existing_group.master_name, existing_group.builder_name,
         existing_group.build_number])
  else:
    logging.info('A new try job should be run for this unique build failure.')
    _CreateBuildFailureGroup(
        master_name, builder_name, build_number, build_failure_type, blame_list,
        suspected_tuples, output_nodes, failed_steps_and_tests)
    _LinkAnalysisToBuildFailureGroup(master_name, builder_name, build_number,
                                     [master_name, builder_name, build_number])

  return not existing_group


@ndb.transactional
def _ReviveOrCreateTryJobEntity(
    master_name, builder_name, build_number, force_try_job):
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


def _NeedANewCompileTryJob(
    master_name, builder_name, build_number, failure_info):

  compile_failure = failure_info['failed_steps'].get('compile', {})
  if compile_failure:
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.failure_result_map['compile'] = build_util.CreateBuildId(
        master_name, builder_name, compile_failure['first_failure'])
    analysis.put()

    if compile_failure['first_failure'] == compile_failure['current_failure']:
      return True

  return False


def GetBuildKeyForBuildInfoInFailureResultMap(
    master_name, builder_name, build_number):
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  failure_result_map = analysis.failure_result_map
  current_build_key = build_util.CreateBuildId(
      master_name, builder_name, build_number)
  for step_keys in failure_result_map.itervalues():
    for test_key in step_keys.itervalues():
      if test_key == current_build_key:
        return True
  return False


def _NeedANewTestTryJob(
    master_name, builder_name, build_number, failure_info, force_try_job):
  if failure_info['failure_type'] != failure_type.TEST:
    return False

  if (not force_try_job and
      waterfall_config.ShouldSkipTestTryJobs(master_name, builder_name)):
    logging.info('Test try jobs on %s, %s are not supported yet.',
                 master_name, builder_name)
    return False

  return GetBuildKeyForBuildInfoInFailureResultMap(
      master_name, builder_name, build_number)


def NeedANewWaterfallTryJob(
    master_name, builder_name, build_number, failure_info, signals,
    heuristic_result, force_try_job=False):

  tryserver_mastername, tryserver_buildername = (
      waterfall_config.GetWaterfallTrybot(master_name, builder_name))
  try_job_type = failure_info['failure_type']

  if not tryserver_mastername or not tryserver_buildername:
    logging.info('%s, %s is not supported yet.', master_name, builder_name)
    return False, None

  if not force_try_job:
    build = WfBuild.Get(master_name, builder_name, build_number)

    if _ShouldBailOutForOutdatedBuild(build):
      logging.error('Build time %s is more than 24 hours old. '
                    'Try job will not be triggered.' % build.start_time)
      return False, None

  if try_job_type == failure_type.COMPILE:
    need_new_try_job = _NeedANewCompileTryJob(
        master_name, builder_name, build_number, failure_info)
  else:
    need_new_try_job = _NeedANewTestTryJob(
        master_name, builder_name, build_number, failure_info, force_try_job)

  # TODO(chanli): enable the feature to trigger single try job for a group
  # when notification is ready.
  # We still call _IsBuildFailureUniqueAcrossPlatforms just so we have data for
  # failure groups.

  # TODO(chanli): Add checking for culprits of the group when enabling
  # single try job: add current build to suspected_cl.builds if the try job for
  # this group has already completed.
  if need_new_try_job:
    _IsBuildFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, try_job_type,
        failure_info['builds'][str(build_number)]['blame_list'],
        failure_info['failed_steps'], signals, heuristic_result)

  try_job_was_created, try_job_key = _ReviveOrCreateTryJobEntity(
      master_name, builder_name, build_number, force_try_job)
  need_new_try_job = need_new_try_job and try_job_was_created
  return need_new_try_job, try_job_key


def GetFailedTargetsFromSignals(signals, master_name, builder_name):
  compile_targets = []

  if not signals or 'compile' not in signals:
    return compile_targets

  if signals['compile'].get('failed_output_nodes'):
    return signals['compile'].get('failed_output_nodes')

  strict_regex = waterfall_config.EnableStrictRegexForCompileLinkFailures(
      master_name, builder_name)
  for source_target in signals['compile'].get('failed_targets', []):
    # For link failures, we pass the executable targets directly to try-job, and
    # there is no 'source' for link failures.
    # For compile failures, only pass the object files as the compile targets
    # for the bots that we use strict regex to extract such information.
    if not source_target.get('source') or strict_regex:
      compile_targets.append(source_target.get('target'))

  return compile_targets
