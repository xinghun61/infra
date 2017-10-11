# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Logic related to examine builds and determine regression range."""

import logging

from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from libs import analysis_status
from model import result_status
from model.wf_analysis import WfAnalysis
from waterfall import build_util
from waterfall import buildbot

_MAX_BUILDS_TO_CHECK = 20
_SUPPORTED_FAILURE_TYPE = [failure_type.COMPILE, failure_type.TEST]


def _ExtractBuildInfo(master_name, builder_name, build_number):
  """Returns a BuildInfo instance for the specified build."""
  build = build_util.DownloadBuildData(master_name, builder_name, build_number)

  if build is None or not build.data:
    raise Exception('Failed to download build data for build %s/%s/%d',
                    master_name, builder_name, build_number)

  build_info = buildbot.ExtractBuildInfo(master_name, builder_name,
                                         build_number, build.data)

  if not build.completed:
    build.start_time = build_info.build_start_time
    build.completed = build_info.completed
    build.result = build_info.result
    build.put()

  return build_info


def _SaveBlamelistAndChromiumRevisionIntoDict(build_info, builds):
  """Saves blame list and chromium revision info for each build.

  Args:
    build_info (BuildInfo): a BuildInfo instance which contains blame list and
        chromium revision.
    builds (dict): to which the blame list and chromium revision is saved. It
        will be updated and looks like:
        {
          555 : {
            'chromium_revision': 'a_git_hash',
            'blame_list': ['git_hash1', 'git_hash2'],
          },
        }
  """
  builds[build_info.build_number] = {
      'chromium_revision': build_info.chromium_revision,
      'blame_list': build_info.blame_list
  }


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
      },
    }
  """
  failed_steps = dict()
  for step_name in build_info.failed_steps:
    failed_steps[step_name] = {
        'current_failure': build_info.build_number,
        'first_failure': build_info.build_number,
    }

  return failed_steps


def CheckForFirstKnownFailure(master_name, builder_name, build_number,
                              failed_steps, builds):
  """Checks for first known failures of the given failed steps.

  Args:
    master_name (str): master of the failed build.
    builder_name (str): builder of the failed build.
    build_number (int): builder number of the current failed build.
    failed_steps (dict): the failed steps of the current failed build. It will
        be updated with build numbers for 'first_failure' and 'last_pass' of
        each failed step.
    builds (dict): a dict to save blame list and chromium revision.
  """
  # Look back for first known failures.
  earliest_build_number = max(0, build_number - 1 - _MAX_BUILDS_TO_CHECK)
  for n in range(build_number - 1, earliest_build_number - 1, -1):
    # Extraction should stop when we reach to the first build.
    build_info = _ExtractBuildInfo(master_name, builder_name, n)
    if not build_info:
      # Failed to extract the build information, bail out.
      return

    _SaveBlamelistAndChromiumRevisionIntoDict(build_info, builds)

    if build_info.result == buildbot.SUCCESS:
      for step_name in failed_steps:
        if 'last_pass' not in failed_steps[step_name]:
          failed_steps[step_name]['last_pass'] = build_info.build_number

      # All steps passed, so stop looking back.
      return
    else:
      # If a step is not run due to some bot exception, we are not sure
      # whether the step could pass or not. So we only check failed/passed
      # steps here.

      for step_name in build_info.failed_steps:
        if (step_name in failed_steps and
            not 'last_pass' in failed_steps[step_name]):
          failed_steps[step_name]['first_failure'] = build_info.build_number

      for step_name in failed_steps:
        if (step_name in build_info.passed_steps and
            'last_pass' not in failed_steps[step_name]):
          failed_steps[step_name]['last_pass'] = build_info.build_number

      if all('last_pass' in step_info for step_info in failed_steps.values()):
        # All failed steps passed in this build cycle.
        return


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
  build_info = _ExtractBuildInfo(master_name, builder_name, build_number)
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  assert analysis

  if not build_info:
    logging.error('Failed to extract build info for build %s/%s/%d',
                  master_name, builder_name, build_number)
    analysis.status = analysis_status.ERROR
    analysis.result_status = result_status.NOT_FOUND_UNTRIAGED
    analysis.put()
    return {}, False

  build_failure_type = build_util.GetFailureType(build_info)
  failed = (build_info.result != buildbot.SUCCESS and
            bool(build_info.failed_steps))

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
  }

  if (not failed or not build_info.chromium_revision or
      build_failure_type not in _SUPPORTED_FAILURE_TYPE):
    # No real failure or lack of required information, so no need to start
    # an analysis.
    analysis.status = analysis_status.COMPLETED
    analysis.result_status = result_status.NOT_FOUND_UNTRIAGED
    analysis.put()
    return failure_info, False

  _SaveBlamelistAndChromiumRevisionIntoDict(build_info, failure_info['builds'])

  failure_info['failed_steps'] = _CreateADictOfFailedSteps(build_info)

  analysis.not_passed_steps = build_info.not_passed_steps
  analysis.build_failure_type = build_failure_type
  analysis.build_start_time = (analysis.build_start_time or
                               build_info.build_start_time)
  analysis.put()

  return failure_info, True


def AnyNewBuildSucceeded(master_name, builder_name, build_number):
  latest_build_numbers = buildbot.GetRecentCompletedBuilds(
      master_name, builder_name, FinditHttpClient())

  for newer_build_number in xrange(build_number + 1,
                                   latest_build_numbers[0] + 1):
    # Checks all builds after current build.
    newer_build_info = build_util.GetBuildInfo(master_name, builder_name,
                                               newer_build_number)
    if newer_build_info and newer_build_info.result in [
        buildbot.SUCCESS, buildbot.WARNINGS
    ]:
      return True

  return False
