# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common import appengine_util
from common import constants
from model import analysis_status
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
          targeted_tests.append(failure_name)

    need_new_try_job = need_new_try_job or failure_need_try_job
    last_pass = (failure_last_pass if failure_last_pass and
                 failure_last_pass < last_pass else last_pass)

  return targeted_tests, need_new_try_job, last_pass


@ndb.transactional
def _NeedANewTryJob(
    master_name, builder_name, build_number, failed_steps, failure_result_map):
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

  if need_new_try_job:
    try_job = WfTryJob.Get(
        master_name, builder_name, build_number)

    if try_job:
      if try_job.failed:
        try_job.status = analysis_status.PENDING
        try_job.put()
      else:
        need_new_try_job = False
    else:
      try_job = WfTryJob.Create(
          master_name, builder_name, build_number)
      try_job.put()

  return need_new_try_job, last_pass, try_job_type, targeted_tests


def _GetFailedTargetsFromSignals(signals, master_name, builder_name):
  compile_targets = []

  if not signals or 'compile' not in signals:
    return compile_targets

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


def ScheduleTryJobIfNeeded(failure_info, signals=None, build_completed=False):
  # Do not schedule try-jobs or Swarming tasks until the build is completed.
  if not build_completed:
    return {}

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

  failure_result_map = {}
  need_new_try_job, last_pass, try_job_type, targeted_tests = (
      _NeedANewTryJob(master_name, builder_name, build_number,
                      failed_steps, failure_result_map))

  if need_new_try_job:
    compile_targets = (_GetFailedTargetsFromSignals(
        signals, master_name, builder_name)
                       if try_job_type == TryJobType.COMPILE else None)

    pipeline = (
        swarming_tasks_to_try_job_pipeline.SwarmingTasksToTryJobPipeline(
            master_name, builder_name, build_number,
            builds[str(last_pass)]['chromium_revision'],
            builds[str(build_number)]['chromium_revision'],
            builds[str(build_number)]['blame_list'],
            try_job_type, compile_targets, targeted_tests))

    pipeline.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    pipeline.start(queue_name=constants.WATERFALL_TRY_JOB_QUEUE)

    if try_job_type == TryJobType.TEST:  # pragma: no cover
      logging_str = (
          'Swarming task was scheduled for build %s, %s, %s: %s because of'
          ' %s failure. A try job may be triggered if some reliable failure'
          ' is detected in the task.') % (
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
