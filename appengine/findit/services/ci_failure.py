# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Logic related to examine builds and determine regression range."""

from collections import defaultdict
import hashlib
import inspect
import logging

from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from gae_libs.caches import PickledMemCache
from libs import analysis_status
from libs.cache_decorator import Cached
from model import analysis_approach_type
from model import result_status
from model.wf_analysis import WfAnalysis
from services import monitoring
from services.parameters import FailureInfoBuild
from services.parameters import FailureInfoBuilds
from waterfall import build_util
from waterfall import buildbot
from waterfall import waterfall_config

_MAX_BUILDS_TO_CHECK = 20
_SUPPORTED_FAILURE_TYPE = [failure_type.COMPILE, failure_type.TEST]
# Caches canonical step name for a week.
_CACHE_EXPIRE_TIME_SECONDS = 7 * 24 * 60 * 60


# TODO(crbug/842980): Deprecate blame_list in builds.
def _GetBlameListAndRevisionForBuild(build_info):
  """Gets blame list and chromium revision info for a build.

  Args:
    build_info (BuildInfo): a BuildInfo instance which contains blame list and
        chromium revision.
  """
  return {
      'chromium_revision': build_info.chromium_revision,
      'blame_list': build_info.blame_list
  }


def _StepMetadataKeyGenerator(func, args, kwargs, namespace=None):
  """Generates a key to a cached canonical step name.

  Using the step_name as key, assuming it's practically not possible for 2 steps
  with different canonical_step_names have exactly the same step_name.

  Args:
    func (function): An arbitrary function.
    args (list): Positional arguments passed to ``func``.
    kwargs (dict): Keyword arguments passed to ``func``.
    namespace (str): A prefix to the key for the cache.

  Returns:
    A string to represent a call to the given function with the given arguments.
  """
  params = inspect.getcallargs(func, *args, **kwargs)
  step_name = params.get('step_name')
  assert step_name
  encoded_params = hashlib.md5(step_name).hexdigest()
  return '%s-%s' % (namespace, encoded_params)


@Cached(
    PickledMemCache(),
    namespace='step_metadata',
    expire_time=_CACHE_EXPIRE_TIME_SECONDS,
    key_generator=_StepMetadataKeyGenerator)
def GetStepMetadata(master_name, builder_name, build_number, step_name):
  return build_util.GetWaterfallBuildStepLog(master_name, builder_name,
                                             build_number, step_name,
                                             FinditHttpClient(),
                                             'step_metadata')


def GetCanonicalStepName(master_name, builder_name, build_number, step_name):
  step_metadata = GetStepMetadata(master_name, builder_name, build_number,
                                  step_name)
  return step_metadata.get(
      'canonical_step_name') if step_metadata else step_name


def GetIsolateTargetName(master_name, builder_name, build_number, step_name):
  """ Returns the isolate_target_name in the step_metadata.

  Args:
    master_name: Master name of the build.
    builder_name: Builder name of the build.
    build_number: Build number of the build.
    step_name: The original step name to get isolate_target_name for, and the
               step name may contain hardware information and 'with(out) patch'
               suffixes.

  Returns:
    The isolate_target_name if it exists, otherwise, None.
  """
  step_metadata = GetStepMetadata(master_name, builder_name, build_number,
                                  step_name)
  return step_metadata.get('isolate_target_name') if step_metadata else None


def _StepIsSupportedForMaster(master_name, builder_name, build_number,
                              step_name):
  if step_name == 'compile':
    canonical_step_name = step_name
  else:
    canonical_step_name = GetCanonicalStepName(master_name, builder_name,
                                               build_number, step_name)
  return waterfall_config.StepIsSupportedForMaster(canonical_step_name,
                                                   master_name)


def _CreateADictOfFailedSteps(build_info):
  """ Returns a dict with build number for failed steps.

  Args:
    failed_steps (list): a list of failed steps.

  Returns:
    A dict like this:
    {
      'step_name': {
        'current_failure': 555,
        'first_failure': 553,
        'supported': True
      },
    }
  """
  failed_steps = dict()
  for step_name in build_info.failed_steps:
    failed_steps[step_name] = {
        'current_failure':
            build_info.build_number,
        'first_failure':
            build_info.build_number,
        'supported':
            _StepIsSupportedForMaster(build_info.master_name,
                                      build_info.builder_name,
                                      build_info.build_number, step_name)
    }

  return failed_steps


def _UpdateStringTypedBuildKeyToInt(builds):
  """Updates the string keys to int keys."""
  updated_builds = FailureInfoBuilds()
  for build_number, build in builds.iteritems():
    updated_builds[int(build_number)] = build
  return updated_builds


def CheckForFirstKnownFailure(master_name, builder_name, build_number,
                              failure_info):
  """Checks for first known failures of the given failed steps.

  Args:
    master_name (str): master of the failed build.
    builder_name (str): builder of the failed build.
    build_number (int): builder number of the current failed build.
    failure_info (CompileFailureInfo, TestFailureInfo): information of the build
      failure.
  Returns:
    failure_info (CompileFailureInfo, TestFailureInfo): updated failure_info.
  """
  failed_steps = failure_info.failed_steps
  failure_info.builds = _UpdateStringTypedBuildKeyToInt(failure_info.builds)
  # Look back for first known failures.
  for build_info in build_util.IteratePreviousBuildsFrom(
      master_name, builder_name, build_number, _MAX_BUILDS_TO_CHECK):
    # Extraction should stop when we reach to the first build.

    failure_info.builds[build_info.build_number] = (
        FailureInfoBuild.FromSerializable(
            _GetBlameListAndRevisionForBuild(build_info)))

    if build_info.result == buildbot.SUCCESS:
      for step_name in failed_steps:
        if failed_steps[step_name].last_pass is None:
          failed_steps[step_name].last_pass = build_info.build_number

      # All steps passed, so stop looking back.
      return failure_info
    else:
      # If a step is not run due to some bot exception, we are not sure
      # whether the step could pass or not. So we only check failed/passed
      # steps here.

      for step_name in build_info.failed_steps:
        if (step_name in failed_steps and
            failed_steps[step_name].last_pass is None):
          failed_steps[step_name].first_failure = build_info.build_number

      for step_name in failed_steps:
        if (step_name in build_info.passed_steps and
            failed_steps[step_name].last_pass is None):
          failed_steps[step_name].last_pass = build_info.build_number

      if all(step_info.last_pass is not None
             for step_info in failed_steps.values()):
        # All failed steps passed in this build cycle.
        return failure_info
  return failure_info


def GetBuildFailureInfo(master_name, builder_name, build_number):
  """Processes build info of a build and gets failure info.

  This function will also update wf_analysis about the build's not passed steps
  and failure type.

  Args:
    master_name (str): Master name of the build.
    builder_name (str): Builder name of the build.
    build_number (int): Number of the build.

  Returns:
    A dict of failure info and a flag for should start analysis.
  """
  status_code, build_info = build_util.GetBuildInfo(master_name, builder_name,
                                                    build_number)
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  assert analysis

  # TODO(crbug/804617): Remove this when new LUCI API is ready.
  if status_code == 404:
    # Hits a build number gap. Should skip the analysis.
    analysis.status = analysis_status.SKIPPED
    analysis.result_status = result_status.NOT_FOUND_UNTRIAGED
    analysis.put()

    # Findit analysis doesn't start. At this point it doesn't matter which
    # step failed, so use 'unknown' for all the step related information.
    monitoring.OnWaterfallAnalysisStateChange(
        master_name=master_name,
        builder_name=builder_name,
        failure_type='unknown',
        canonical_step_name='unknown',
        isolate_target_name='unknown',
        status=analysis_status.STATUS_TO_DESCRIPTION[analysis_status.SKIPPED],
        analysis_type=analysis_approach_type.STATUS_TO_DESCRIPTION[
            analysis_approach_type.PRE_ANALYSIS])

    return {}, False

  if not build_info:
    logging.error('Failed to extract build info for build %s/%s/%d',
                  master_name, builder_name, build_number)
    analysis.status = analysis_status.ERROR
    analysis.result_status = result_status.NOT_FOUND_UNTRIAGED
    analysis.put()

    monitoring.OnWaterfallAnalysisStateChange(
        master_name=master_name,
        builder_name=builder_name,
        failure_type='unknown',
        canonical_step_name='unknown',
        isolate_target_name='unknown',
        status=analysis_status.STATUS_TO_DESCRIPTION[analysis_status.ERROR],
        analysis_type=analysis_approach_type.STATUS_TO_DESCRIPTION[
            analysis_approach_type.PRE_ANALYSIS])

    return {}, False

  build_failure_type = build_util.GetFailureType(build_info)
  failed = (
      build_info.result != buildbot.SUCCESS and bool(build_info.failed_steps))

  failure_info = {
      'failed': failed,
      'master_name': master_name,
      'builder_name': builder_name,
      'build_number': build_number,
      'chromium_revision': build_info.chromium_revision,
      'builds': {},
      'failed_steps': {},
      'failure_type': build_failure_type,
      'parent_mastername': build_info.parent_mastername,
      'parent_buildername': build_info.parent_buildername,
      'is_luci': build_info.is_luci,
      'buildbucket_bucket': build_info.buildbucket_bucket,
      'buildbucket_id': build_info.buildbucket_id,
  }

  if (not failed or not build_info.chromium_revision or
      build_failure_type not in _SUPPORTED_FAILURE_TYPE):
    # No real failure or lack of required information, so no need to start
    # an analysis.
    analysis.status = analysis_status.COMPLETED
    analysis.result_status = result_status.NOT_FOUND_UNTRIAGED
    analysis.put()

    monitoring.OnWaterfallAnalysisStateChange(
        master_name=master_name,
        builder_name=builder_name,
        failure_type='unknown',
        canonical_step_name='unknown',
        isolate_target_name='unknown',
        status=analysis_status.STATUS_TO_DESCRIPTION[analysis_status.COMPLETED],
        analysis_type=analysis_approach_type.STATUS_TO_DESCRIPTION[
            analysis_approach_type.PRE_ANALYSIS])

    return failure_info, False

  failure_info['builds'][build_info.build_number] = (
      _GetBlameListAndRevisionForBuild(build_info))

  failure_info['failed_steps'] = _CreateADictOfFailedSteps(build_info)

  analysis.not_passed_steps = build_info.not_passed_steps
  analysis.build_failure_type = build_failure_type
  analysis.build_start_time = (
      analysis.build_start_time or build_info.build_start_time)
  analysis.put()

  return failure_info, True


def GetLaterBuildsWithAnySameStepFailure(master_name,
                                         builder_name,
                                         build_number,
                                         failed_steps=None):
  """Gets successive failed builds with the same failure as the referred build.

    If failed_steps is provided, this function can drill down to step_level
    as well.

    The function will stop looking further and abandon all its findings if:
      - find a non-failed build (build ends in success or warning) or
      - find a build with non-overlapping failures.
  """
  latest_build_numbers = buildbot.GetRecentCompletedBuilds(
      master_name, builder_name, FinditHttpClient())
  builds_with_same_failed_steps = defaultdict(list)

  if not latest_build_numbers:
    # Failed to get later builds, cannot check their failures. Returns an empty
    # dict to skip actions on the culprit.
    # This should be rare, possible cause is builder rename.
    logging.error(
        'Failed to get latest build numbers for builder %s/%s since %d.',
        master_name, builder_name, build_number)
    return {}

  for newer_build_number in latest_build_numbers:
    if newer_build_number <= build_number:
      break

    # Checks all builds after current build.
    _, newer_build_info = build_util.GetBuildInfo(master_name, builder_name,
                                                  newer_build_number)
    if newer_build_info and newer_build_info.result in [
        buildbot.SUCCESS, buildbot.WARNINGS
    ]:
      return {}

    for failed_step in failed_steps or []:
      if failed_step in newer_build_info.failed_steps:
        builds_with_same_failed_steps[newer_build_number].append(failed_step)

    if not builds_with_same_failed_steps[newer_build_number]:
      # No same failed steps.
      return {}

  return builds_with_same_failed_steps


def GetGoodRevision(failure_info):
  """Gets the earliest passed revision for the failures.

  Uses the chromium_revision of the earliest last_pass of failures, ignore the
  failures with no last_pass.

  Args:
    failure_info(CompileFailureInfo, TestFailureInfo): Failure info.

  Returns:
    (str): chromium_revision of the earliest last_pass Findit found.
  """
  earliest_last_pass_build = failure_info.build_number
  for step_failure in failure_info.failed_steps.itervalues():
    if (step_failure.last_pass and
        step_failure.last_pass < earliest_last_pass_build):
      earliest_last_pass_build = step_failure.last_pass

  if (earliest_last_pass_build < failure_info.build_number and
      failure_info.builds.get(earliest_last_pass_build)):
    return failure_info.builds[earliest_last_pass_build].chromium_revision
  return None
