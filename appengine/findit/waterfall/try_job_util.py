# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging

from google.appengine.ext import ndb

from common import appengine_util
from common import constants
from common.waterfall import failure_type
from model import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_failure_group import WfFailureGroup
from model.wf_try_job import WfTryJob
from waterfall import swarming_tasks_to_try_job_pipeline
from waterfall import waterfall_config
from waterfall.try_job_type import TryJobType


def _CheckFailureForTryJobKey(
    master_name, builder_name, build_number,
    failure_result_map, failed_step_or_test, failure):
  """Compares the current_failure and first_failure for each failed_step/test.

  If equal, a new try_job needs to start;
  If not, apply the key of the first_failure's try_job to this failure.
  """
  # TODO(chanli): Need to compare failures across builders
  # after the grouping of failures is implemented.
  # TODO(chanli): Need to handle cases where first failure is actually
  # more than 20 builds back. The implementation should not be here,
  # but need to be taken care of.
  if not failure.get('last_pass'):
    # Bail out since cannot figure out the good_revision.
    return False, None

  if failure['current_failure'] == failure['first_failure']:
    failure_result_map[failed_step_or_test] = '%s/%s/%s' % (
        master_name, builder_name, build_number)
    return True, failure['last_pass']  # A new try_job is needed.
  else:
    failure_result_map[failed_step_or_test] = '%s/%s/%s' % (
        master_name, builder_name, failure['first_failure'])
    return False, None


def _CheckIfNeedNewTryJobForTestFailure(
    failure_level, master_name, builder_name, build_number,
    failure_result_map, failures):
  """Traverses failed steps or tests to check if a new try job is needed."""
  need_new_try_job = False
  last_pass = build_number
  targeted_tests = {} if failure_level == 'step' else []

  for failure_name, failure in failures.iteritems():
    if 'tests' in failure:
      failure_result_map[failure_name] = {}
      failure_targeted_tests, failure_need_try_job, failure_last_pass = (
          _CheckIfNeedNewTryJobForTestFailure(
              'test', master_name, builder_name, build_number,
              failure_result_map[failure_name], failure['tests']))
      if failure_need_try_job:
        targeted_tests[failure_name] = failure_targeted_tests
    else:
      failure_need_try_job, failure_last_pass = _CheckFailureForTryJobKey(
          master_name, builder_name, build_number,
          failure_result_map, failure_name, failure)
      if failure_need_try_job:
        if failure_level == 'step':
          targeted_tests[failure_name] = []
        else:
          targeted_tests.append(failure.get('base_test_name', failure_name))

    need_new_try_job = need_new_try_job or failure_need_try_job
    last_pass = (failure_last_pass if failure_last_pass and
                 failure_last_pass < last_pass else last_pass)

  return targeted_tests, need_new_try_job, last_pass


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
              failure['step_name'],
              suspected_cl['revision'],
              test['test_name']])
    else:
      for suspected_cl in failure['suspected_cls']:
        suspected_cls_with_failures.append([
            failure['step_name'],
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


def _GetMatchingCompileFailureGroups(output_nodes):
  # Output nodes should already be unique and sorted.
  return WfFailureGroup.query(ndb.AND(
      WfFailureGroup.build_failure_type == failure_type.COMPILE,
      WfFailureGroup.output_nodes == output_nodes
  )).fetch()


def _GetMatchingTestFailureGroups(failed_steps_and_tests):
  return WfFailureGroup.query(ndb.AND(
      WfFailureGroup.build_failure_type == failure_type.TEST,
      WfFailureGroup.failed_steps_and_tests == failed_steps_and_tests
  )).fetch()


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
def ReviveOrCreateTryJobEntity(
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

  return try_job_entity_revived_or_created


def _NeedANewTryJob(
    master_name, builder_name, build_number, build_failure_type, failed_steps,
    failure_result_map, builds, signals, heuristic_result, force_try_job=False):
  """Checks if a new try_job is needed."""
  need_new_try_job = False
  last_pass = build_number

  if 'compile' in failed_steps:
    try_job_type = TryJobType.COMPILE
    targeted_tests = None
    need_new_try_job, last_pass = _CheckFailureForTryJobKey(
        master_name, builder_name, build_number,
        failure_result_map, TryJobType.COMPILE, failed_steps['compile'])
  else:
    try_job_type = TryJobType.TEST
    targeted_tests, need_new_try_job, last_pass = (
        _CheckIfNeedNewTryJobForTestFailure(
            'step', master_name, builder_name, build_number, failure_result_map,
            failed_steps))

  # TODO(josiahk): Integrate this into need_new_try_job boolean
  _IsBuildFailureUniqueAcrossPlatforms(
      master_name, builder_name, build_number, build_failure_type,
      builds[str(build_number)]['blame_list'], failed_steps, signals,
      heuristic_result)

  need_new_try_job = (
      need_new_try_job and ReviveOrCreateTryJobEntity(
          master_name, builder_name, build_number, force_try_job))

  return need_new_try_job, last_pass, try_job_type, targeted_tests


def _GetFailedTargetsFromSignals(signals, master_name, builder_name):
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


def _GetSuspectsFromHeuristicResult(heuristic_result):
  suspected_revisions = set()
  if not heuristic_result:
    return list(suspected_revisions)
  for failure in heuristic_result.get('failures', []):
    for cl in failure['suspected_cls']:
      suspected_revisions.add(cl['revision'])
  return list(suspected_revisions)


def _ShouldBailOutForOutdatedBuild(build):
  return (datetime.utcnow() - build.start_time).days > 0


def ScheduleTryJobIfNeeded(failure_info, signals, heuristic_result,
                           force_try_job=False):
  master_name = failure_info['master_name']
  builder_name = failure_info['builder_name']
  build_number = failure_info['build_number']
  failed_steps = failure_info.get('failed_steps', [])
  builds = failure_info.get('builds', {})

  tryserver_mastername, tryserver_buildername = (
      waterfall_config.GetTrybotForWaterfallBuilder(master_name, builder_name))

  if not tryserver_mastername or not tryserver_buildername:
    logging.info('%s, %s is not supported yet.', master_name, builder_name)
    return {}

  if not force_try_job:
    build = WfBuild.Get(master_name, builder_name, build_number)

    if _ShouldBailOutForOutdatedBuild(build):
      logging.error('Build time %s is more than 24 hours old. '
                    'Try job will not be triggered.' % build.start_time)
      return {}

    if (failure_info['failure_type'] == failure_type.TEST and
        waterfall_config.ShouldSkipTestTryJobs(master_name, builder_name)):
      logging.info('Test try jobs on %s, %s are not supported yet.',
                   master_name, builder_name)
      return {}

  failure_result_map = {}
  need_new_try_job, last_pass, try_job_type, targeted_tests = (
      _NeedANewTryJob(master_name, builder_name, build_number,
                      failure_info['failure_type'], failed_steps,
                      failure_result_map, builds, signals, heuristic_result,
                      force_try_job))

  if need_new_try_job:
    compile_targets = (_GetFailedTargetsFromSignals(
        signals, master_name, builder_name)
                       if try_job_type == TryJobType.COMPILE else None)
    suspected_revisions = _GetSuspectsFromHeuristicResult(heuristic_result)

    pipeline = (
        swarming_tasks_to_try_job_pipeline.SwarmingTasksToTryJobPipeline(
            master_name, builder_name, build_number,
            builds[str(last_pass)]['chromium_revision'],
            builds[str(build_number)]['chromium_revision'],
            builds[str(build_number)]['blame_list'],
            try_job_type, compile_targets, targeted_tests, suspected_revisions,
            force_try_job))

    pipeline.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    pipeline.start(queue_name=constants.WATERFALL_TRY_JOB_QUEUE)

    if try_job_type == TryJobType.TEST:  # pragma: no cover
      logging_str = (
          'Trying to schedule swarming task(s) for build %s, %s, %s: %s'
          ' because of %s failure. A try job may be triggered if some reliable'
          ' failure is detected in task(s).') % (
              master_name, builder_name, build_number,
              pipeline.pipeline_status_path, try_job_type)
    else:  # pragma: no cover
      logging_str = (
          'Try job was scheduled for build %s, %s, %s: %s because of %s '
          'failure.') % (
              master_name, builder_name, build_number,
              pipeline.pipeline_status_path, try_job_type)
    logging.info(logging_str)

  return failure_result_map
