# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from model.wf_swarming_task import WfSwarmingTask
from waterfall import swarming_util
from waterfall import try_job_util
from waterfall import waterfall_config
from waterfall.identify_try_job_culprit_pipeline import (
    IdentifyTryJobCulpritPipeline)
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.process_swarming_tasks_result_pipeline import (
    StepHasFirstTimeFailure)
from waterfall.schedule_compile_try_job_pipeline import (
    ScheduleCompileTryJobPipeline)
from waterfall.schedule_test_try_job_pipeline import (
    ScheduleTestTryJobPipeline)


def _GetLastPassCompile(build_number, failed_steps):
  if (failed_steps.get('compile') and
      failed_steps['compile']['first_failure'] == build_number and
      failed_steps['compile'].get('last_pass') is not None):
    return failed_steps['compile']['last_pass']
  return None


def _GetLastPassTest(build_number, failed_steps):
  for step_failure in failed_steps.itervalues():
    for test_failure in step_failure.get('tests', {}).itervalues():
      if (test_failure['first_failure'] == build_number and
          test_failure.get('last_pass') is not None):
        return test_failure['last_pass']
  return None


def _GetLastPass(build_number, failure_info, try_job_type):
  if try_job_type == failure_type.COMPILE:
    return _GetLastPassCompile(build_number, failure_info['failed_steps'])
  elif try_job_type == failure_type.TEST:
    return _GetLastPassTest(build_number, failure_info['failed_steps'])
  else:
    return None


def _GetSuspectsFromHeuristicResult(heuristic_result):
  if not heuristic_result:
    return []

  suspected_revisions = set()
  for failure in heuristic_result.get('failures', []):
    for cl in failure['suspected_cls']:
      suspected_revisions.add(cl['revision'])
  return list(suspected_revisions)


def _GetReliableTests(master_name, builder_name, build_number, failure_info):
  task_results = {}
  for step_name, step_failure in failure_info['failed_steps'].iteritems():
    if not StepHasFirstTimeFailure(step_failure.get('tests', {}), build_number):
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


class StartTryJobOnDemandPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, failure_info, signals,
          heuristic_result, build_completed, force_try_job):
    """Starts a try job if one is needed for the given failure."""

    if not build_completed:  # Only start try-jobs for completed builds.
      return

    need_try_job, try_job_key = try_job_util.NeedANewWaterfallTryJob(
        master_name, builder_name, build_number, failure_info, signals,
        heuristic_result, force_try_job)

    if not need_try_job:
      return

    try_job_type = failure_info['failure_type']
    last_pass = _GetLastPass(build_number, failure_info, try_job_type)
    if last_pass is None:  # pragma: no cover
      logging.warning('Couldn"t start try job for build %s, %s, %d because'
                      ' last_pass is not found.', master_name, builder_name,
                      build_number)
      return

    good_revision = failure_info['builds'][str(last_pass)]['chromium_revision']
    bad_revision = failure_info['builds'][str(build_number)][
        'chromium_revision']
    suspected_revisions = _GetSuspectsFromHeuristicResult(heuristic_result)

    if try_job_type == failure_type.COMPILE:
      compile_targets = try_job_util.GetFailedTargetsFromSignals(
          signals, master_name, builder_name)
      dimensions = waterfall_config.GetTrybotDimensions(master_name,
                                                        builder_name)
      cache_name = swarming_util.GetCacheName(master_name, builder_name)
      try_job_id = yield ScheduleCompileTryJobPipeline(
          master_name, builder_name, build_number, good_revision, bad_revision,
          try_job_type, compile_targets, suspected_revisions, cache_name,
          dimensions)
    else:
      # If try_job_type is other type, the pipeline has returned.
      # So here the try_job_type is failure_type.TEST.

      # Gets the swarming tasks' results.
      task_results = _GetReliableTests(master_name, builder_name, build_number,
                                       failure_info)

      parent_mastername = failure_info.get('parent_mastername') or master_name
      parent_buildername = failure_info.get('parent_buildername') or (
          builder_name)
      dimensions = waterfall_config.GetTrybotDimensions(parent_mastername,
                                                        parent_buildername)
      cache_name = swarming_util.GetCacheName(parent_mastername,
                                              parent_buildername)

      try_job_id = yield ScheduleTestTryJobPipeline(
          master_name, builder_name, build_number, good_revision, bad_revision,
          try_job_type, suspected_revisions, cache_name, dimensions,
          task_results)

    try_job_result = yield MonitorTryJobPipeline(try_job_key.urlsafe(),
                                                 try_job_type, try_job_id)

    yield IdentifyTryJobCulpritPipeline(master_name, builder_name, build_number,
                                        try_job_type, try_job_id,
                                        try_job_result)
