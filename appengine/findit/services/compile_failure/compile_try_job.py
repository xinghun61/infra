# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for compile-try-job-related operations.

It provides functions to:
  * Decide if a new compile try job is needed.
  * Get failed targets.
  * Get parameters for starting a new compile try job.
"""

import logging

from common.waterfall import failure_type
from model.wf_analysis import WfAnalysis
from services import try_job
from waterfall import build_util
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
