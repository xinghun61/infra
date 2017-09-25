# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for compile-try-job-related operations.

It provides functions to:
  * Decide if a new compile try job is needed.
  * Get failed targets.
  * Get parameters for starting a new compile try job.
"""

import copy
import logging

from google.appengine.ext import ndb

from common import constants
from common.waterfall import failure_type
from libs import analysis_status
from model import analysis_approach_type
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_try_job import WfTryJob
from services import try_job
from services.compile_failure import compile_failure_analysis
from waterfall import build_util
from waterfall import suspected_cl_util
from waterfall import swarming_util
from waterfall import waterfall_config


def _GetOutputNodes(signals):
  if not signals or 'compile' not in signals:
    return []

  # Compile failures with no output nodes will be considered unique.
  return signals['compile'].get('failed_output_nodes', [])


def _GetMatchingCompileFailureGroups(output_nodes):
  groups = try_job.GetMatchingFailureGroups(failure_type.COMPILE)
  # Output nodes should already be unique and sorted.
  return [group for group in groups if group.output_nodes == output_nodes]


def _IsCompileFailureUniqueAcrossPlatforms(
    master_name, builder_name, build_number, build_failure_type, blame_list,
    signals, heuristic_result):

  if build_failure_type != failure_type.COMPILE:
    logging.info('Expected compile failure but get %s failure.',
                 failure_type.GetDescriptionForFailureType(build_failure_type))
    return True

  output_nodes = _GetOutputNodes(signals)
  if not output_nodes:
    return True
  groups = _GetMatchingCompileFailureGroups(output_nodes)

  return try_job.IsBuildFailureUniqueAcrossPlatforms(
      master_name,
      builder_name,
      build_number,
      build_failure_type,
      blame_list,
      heuristic_result,
      groups,
      output_nodes=output_nodes)


def _NeedANewCompileTryJob(master_name, builder_name, build_number,
                           failure_info):

  compile_failure = failure_info['failed_steps'].get('compile', {})
  if compile_failure:
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.failure_result_map['compile'] = build_util.CreateBuildId(
        master_name, builder_name, compile_failure['first_failure'])
    analysis.put()

    if compile_failure['first_failure'] == compile_failure['current_failure']:
      return True

  return False


def NeedANewCompileTryJob(master_name,
                          builder_name,
                          build_number,
                          failure_info,
                          signals,
                          heuristic_result,
                          force_try_job=False):
  """Decides if a new compile try job is needed.

  A new compile try job is needed if:
  1. It passed preliminary checks in try_job.NeedANewWaterfallTryJob,
  2. It's for a compile failure,
  3. It's a first failure,
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
  if try_job_type != failure_type.COMPILE:
    logging.error('Checking for a compile try job but got a %s failure.',
                  failure_type.GetDescriptionForFailureType(try_job_type))
    return False, None

  need_new_try_job = _NeedANewCompileTryJob(master_name, builder_name,
                                            build_number, failure_info)

  # TODO(chanli): enable the feature to trigger single try job for a group
  # when notification is ready.
  # We still call _IsBuildFailureUniqueAcrossPlatforms just so we have data for
  # failure groups.

  # TODO(chanli): Add checking for culprits of the group when enabling
  # single try job: add current build to suspected_cl.builds if the try job for
  # this group has already completed.
  if need_new_try_job:
    _IsCompileFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, try_job_type,
        failure_info['builds'][str(build_number)]['blame_list'], signals,
        heuristic_result)

  try_job_was_created, try_job_key = try_job.ReviveOrCreateTryJobEntity(
      master_name, builder_name, build_number, force_try_job)
  need_new_try_job = need_new_try_job and try_job_was_created
  return need_new_try_job, try_job_key


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


def _GetLastPassCompile(build_number, failed_steps):
  if (failed_steps.get('compile') and
      failed_steps['compile']['first_failure'] == build_number and
      failed_steps['compile'].get('last_pass') is not None):
    return failed_steps['compile']['last_pass']
  return None


def _GetGoodRevisionCompile(master_name, builder_name, build_number,
                            failure_info):
  last_pass = _GetLastPassCompile(build_number, failure_info['failed_steps'])
  if last_pass is None:
    logging.warning('Couldn"t start try job for build %s, %s, %d because'
                    ' last_pass is not found.', master_name, builder_name,
                    build_number)
    return None

  return failure_info['builds'][str(last_pass)]['chromium_revision']


def GetParametersToScheduleCompileTryJob(master_name, builder_name,
                                         build_number, failure_info, signals,
                                         heuristic_result):
  parameters = {}
  parameters['bad_revision'] = failure_info['builds'][str(build_number)][
      'chromium_revision']
  parameters['suspected_revisions'] = try_job.GetSuspectsFromHeuristicResult(
      heuristic_result)
  parameters['good_revision'] = _GetGoodRevisionCompile(
      master_name, builder_name, build_number, failure_info)

  parameters['compile_targets'] = _GetFailedTargetsFromSignals(
      signals, master_name, builder_name)
  parameters['dimensions'] = waterfall_config.GetTrybotDimensions(
      master_name, builder_name)
  parameters['cache_name'] = swarming_util.GetCacheName(master_name,
                                                        builder_name)
  return parameters


def GetFailedRevisionFromCompileResult(compile_result):
  """Determines the failed revision given compile_result.

  Args:
    compile_result: A dict containing the results from a compile. Please refer
    to try_job_result_format.md for format check.

  Returns:
    The failed revision from compile_results, or None if not found.
  """
  return (compile_result.get('report', {}).get('culprit')
          if compile_result else None)


def _GetRevisionsInRange(sub_ranges):
  """Get revisions in regression range by flattening sub_ranges.

  sub_ranges is in a format like [[None, 'r1', 'r2'], ['r3', 'r4', 'r5']].
  """
  return [
      revision for sub_range in sub_ranges for revision in sub_range if revision
  ]


def CompileFailureIsFlaky(result):
  """Decides if the compile failure is flaky.

  A compile failure should be flaky if compile try job failed at good revision.
  """
  if not result:
    return False

  try_job_result = result.get('report', {}).get('result')
  sub_ranges = result.get('report', {}).get('metadata', {}).get('sub_ranges')

  if (not try_job_result or  # There is some issue with try job, cannot decide.
      not sub_ranges or  # Missing range information.
      # All passed. It could be because of flaky compile, but is not guaranteed.
      'failed' not in try_job_result.values()):
    return False

  tested_revisions = try_job_result.keys()
  # Looks for the good revision which will not be in sub_ranges.
  good_revision = list(
      set(tested_revisions) - set(_GetRevisionsInRange(sub_ranges)))
  return bool(good_revision)


@ndb.transactional
def UpdateTryJobResult(master_name, builder_name, build_number, result,
                       try_job_id, culprits):
  try_job_result = WfTryJob.Get(master_name, builder_name, build_number)
  if culprits:
    updated = False
    for result_to_update in try_job_result.compile_results:
      if try_job_id == result_to_update['try_job_id']:
        result_to_update.update(result)
        updated = True
        break

    if not updated:  # pragma: no cover
      try_job_result.compile_results.append(result)

  try_job_result.status = analysis_status.COMPLETED
  try_job_result.put()


def _GetUpdatedAnalysisResult(analysis, flaky_compile):

  # Analysis only needs to update if the compile failure is actually flaky.
  if (not analysis.result or not analysis.result.get('failures') or
      not flaky_compile):
    return analysis.result

  analysis_result = copy.deepcopy(analysis.result)
  for failure in analysis_result['failures']:
    if failure['step_name'] == constants.COMPILE_STEP_NAME:
      failure['flaky'] = True

  return analysis_result


@ndb.transactional
def UpdateWfAnalysisWithTryJobResult(master_name, builder_name, build_number,
                                     result, culprits, flaky_compile):
  if not culprits and not flaky_compile:
    return

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  assert analysis
  # Update analysis result and suspected CLs with results of this try job if
  # culprits were found or failures are flaky.
  updated_result = _GetUpdatedAnalysisResult(analysis, flaky_compile)
  updated_result_status = try_job.GetResultAnalysisStatus(
      analysis, result) if not flaky_compile else result_status.FLAKY
  updated_suspected_cls = compile_failure_analysis.GetUpdatedSuspectedCLs(
      analysis, culprits)
  if (analysis.result_status != updated_result_status or
      analysis.suspected_cls != updated_suspected_cls or
      analysis.result != updated_result):
    analysis.result_status = updated_result_status
    analysis.suspected_cls = updated_suspected_cls
    analysis.result = updated_result
    analysis.put()


def UpdateSuspectedCLs(master_name, builder_name, build_number, culprits):
  if not culprits:
    return

  # Creates or updates each suspected_cl.
  for culprit in culprits.values():
    revision = culprit['revision']
    failures = {'compile': []}

    suspected_cl_util.UpdateSuspectedCL(culprit['repo_name'], revision,
                                        culprit.get('commit_position'),
                                        analysis_approach_type.TRY_JOB,
                                        master_name, builder_name, build_number,
                                        failure_type.COMPILE, failures, None)
