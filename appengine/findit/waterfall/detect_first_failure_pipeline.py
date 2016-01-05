# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json

from common.http_client_appengine import HttpClientAppengine as HttpClient
from model.wf_analysis import WfAnalysis
from model.wf_step import WfStep
from pipeline_wrapper import pipeline
from pipeline_wrapper import BasePipeline
from waterfall import buildbot
from waterfall import build_util
from waterfall import swarming_util
from waterfall import try_job_util


_MAX_BUILDS_TO_CHECK = 20


class DetectFirstFailurePipeline(BasePipeline):
  """A pipeline to detect first failure of each step.

  TODO(stgao): do test-level detection for gtest.
  """

  def _ExtractBuildInfo(self, master_name, builder_name, build_number):
    """Returns a BuildInfo instance for the specified build."""
    build = build_util.DownloadBuildData(
        master_name, builder_name, build_number)

    if build is None:  # pragma: no cover
      raise pipeline.Retry('Too many download from %s' % master_name)
    if not build.data:  # pragma: no cover
      return None

    build_info = buildbot.ExtractBuildInfo(
        master_name, builder_name, build_number, build.data)

    if not build.completed:
      build.start_time = build_info.build_start_time
      build.completed = build_info.completed
      build.result = build_info.result
      build.put()

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    if analysis and not analysis.build_start_time:
      analysis.build_start_time = build_info.build_start_time
      analysis.put()

    return build_info

  def _SaveBlamelistAndChromiumRevisionIntoDict(self, build_info, builds):
    """
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

  def _CreateADictOfFailedSteps(self, build_info):
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

  def _CheckForFirstKnownFailure(self, master_name, builder_name, build_number,
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
      # Extraction should stop when when we reach to the first build
      build_info = self._ExtractBuildInfo(master_name, builder_name, n)

      if not build_info:  # pragma: no cover
        # Failed to extract the build information, bail out.
        return

      self._SaveBlamelistAndChromiumRevisionIntoDict(build_info, builds)

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

  def _ConcatenateTestLog(self, string1, string2):
    """Concatenates the base64 encoded log.

    Tests if one string is a substring of another,
        if yes, returns the longer string,
        otherwise, returns the concatenation.

    Args:
      string1: base64-encoded string.
      string2: base64-encoded string.

    Returns:
      base64-encoded string.
    """
    str1 = base64.b64decode(string1)
    str2 = base64.b64decode(string2)
    if str2 in str1:
      return string1
    elif str1 in str2:
      return string2
    else:
      return base64.b64encode(str1 + str2)

  def _InitiateTestLevelFirstFailureAndSaveLog(
      self, json_data, step, failed_step=None):
    """Parses the json data and saves all the reliable failures to the step."""
    failed_test_log = {}
    if failed_step:
      failed_step['tests'] = {}

    for iteration in json_data.get('per_iteration_data'):
      for test_name in iteration.keys():
        is_reliable_failure = True

        if any(test['status'] == 'SUCCESS' for test in iteration[test_name]):
          # Ignore the test if any of the attempts were 'SUCCESS'.
          is_reliable_failure = False

        if is_reliable_failure:
          if failed_step:
            # Adds the test to failed_step.
            failed_step['tests'][test_name] = {
                'current_failure': failed_step['current_failure'],
                'first_failure': failed_step['current_failure'],
            }
            if failed_step.get('last_pass'):
              failed_step['tests'][test_name]['last_pass'] = (
                  failed_step['last_pass'])
          # Stores the output to the step's log_data later.
          failed_test_log[test_name] = ''
          for test in iteration[test_name]:
            failed_test_log[test_name] = self._ConcatenateTestLog(
              failed_test_log[test_name], test['output_snippet_base64'])

    step.log_data = json.dumps(failed_test_log) if failed_test_log else 'flaky'
    step.put()

    if failed_step and not failed_step['tests']:  # All flaky.
      del failed_step['tests']
      return False

    return True

  def _StartTestLevelCheckForFirstFailure(
      self, master_name, builder_name, build_number, step_name, failed_step,
      http_client):
    """Downloads test results and initiates first failure info at test level."""
    list_isolated_data = failed_step['list_isolated_data']
    result_log = swarming_util.RetrieveShardedTestResultsFromIsolatedServer(
        list_isolated_data, http_client)

    if (not result_log or not result_log.get('per_iteration_data') or
        result_log['per_iteration_data'] == 'invalid'):  # pragma: no cover
      return False

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    return self._InitiateTestLevelFirstFailureAndSaveLog(
        result_log, step, failed_step)

  def _GetSameStepFromBuild(
      self, master_name, builder_name, build_number, step_name,
      http_client):
    """Downloads swarming test results for a step from previous build."""
    step = WfStep.Get(
        master_name, builder_name, build_number, step_name)

    if step and step.isolated and step.log_data:
      # Test level log has been saved for this step.
      return step

    # Sends request to swarming server for isolated data.
    step_isolated_data = swarming_util.GetIsolatedDataForStep(
        master_name, builder_name, build_number, step_name,
        http_client)

    if not step_isolated_data:  # pragma: no cover
      return None

    result_log = swarming_util.RetrieveShardedTestResultsFromIsolatedServer(
        step_isolated_data, http_client)

    if (not result_log or not result_log.get('per_iteration_data') or
        result_log['per_iteration_data'] == 'invalid'):  # pragma: no cover
      return None

    step = WfStep.Create(
        master_name, builder_name, build_number, step_name)
    step.isolated = True
    self._InitiateTestLevelFirstFailureAndSaveLog(result_log, step)

    return step

  def _UpdateFirstFailureInfoForStep(self, current_build_number, failed_step):
    """Updates first_failure etc. for the step after the check for tests."""
    earliest_test_first_failure = current_build_number
    earliest_test_last_pass = current_build_number - 1
    for failed_test in failed_step['tests'].itervalues():
      # Iterates through all failed tests to prepare data for step level update.
      if not failed_test.get('last_pass'):
        # The test failed throughout checking range,
        # and there is no last_pass info for step.
        # last_pass not found.
        earliest_test_last_pass = -1
      earliest_test_first_failure = min(
          failed_test['first_failure'], earliest_test_first_failure)
      if (failed_test.get('last_pass') and
          failed_test['last_pass'] < earliest_test_last_pass):
        earliest_test_last_pass = failed_test['last_pass']

    # Updates Step level first failure info and last_pass info.
    failed_step['first_failure'] = max(
        earliest_test_first_failure, failed_step['first_failure'])

    if ((not failed_step.get('last_pass') and earliest_test_last_pass >= 0) or
        (failed_step.get('last_pass') and
        earliest_test_last_pass > failed_step['last_pass'])):
      failed_step['last_pass'] = earliest_test_last_pass

  def _UpdateFirstFailureOnTestLevel(
      self, master_name, builder_name, current_build_number, step_name,
      failed_step, http_client):
    """Iterates backwards through builds to get first failure at test level."""
    farthest_first_failure = failed_step['first_failure']
    if failed_step.get('last_pass'):
      farthest_first_failure = failed_step['last_pass'] + 1

    unfinished_tests = failed_step['tests'].keys()
    for build_number in range(
        current_build_number - 1, farthest_first_failure - 1, -1):
      step = self._GetSameStepFromBuild(
          master_name, builder_name, build_number, step_name,
          http_client)

      if not step:  # pragma: no cover
        raise pipeline.Retry(
            'Failed to get swarming test results for a previous build.')

      failed_test_log = (
          {} if step.log_data == 'flaky' else json.loads(step.log_data))
      test_checking_list = unfinished_tests[:]

      for test_name in test_checking_list:
        if failed_test_log.get(test_name):
          failed_step['tests'][test_name]['first_failure'] = build_number
        else:
          # Last pass for this test has been found.
          # TODO(chanli): Handle cases where the test is not run at all.
          failed_step['tests'][test_name]['last_pass'] = build_number
          unfinished_tests.remove(test_name)

      if not unfinished_tests:
        break

    self._UpdateFirstFailureInfoForStep(current_build_number, failed_step)

  def _UpdateFailureInfoBuilds(self, failed_steps, builds):
    """Deletes builds that are before the farthest last_pass."""
    build_numbers_in_builds = builds.keys()
    farthest_last_pass = -1
    for failed_step in failed_steps.itervalues():
      if not failed_step.get('last_pass'):
        return

      if (farthest_last_pass < 0 or
          farthest_last_pass > failed_step['last_pass']):
        farthest_last_pass = failed_step['last_pass']

    for build_number in build_numbers_in_builds:
      if int(build_number) < farthest_last_pass:
        del builds[build_number]

  def _CheckFirstKnownFailureForSwarmingTests(
      self, master_name, builder_name, build_number, failed_steps, builds):
    """Uses swarming test results to update first failure info at test level."""
    http_client = HttpClient()

    # Identifies swarming tests and saves isolated data to them.
    result = swarming_util.GetIsolatedDataForFailedBuild(
        master_name, builder_name, build_number, failed_steps,
        http_client)
    if not result:
      return

    for step_name, failed_step in failed_steps.iteritems():
      if not failed_step.get('list_isolated_data'):  # Non-swarming step.
        continue

      # Checks tests in one step and updates failed_step info if swarming.
      result = self._StartTestLevelCheckForFirstFailure(
          master_name, builder_name, build_number, step_name,
          failed_step, http_client)

      if result:  # pragma: no cover
        # Iterates backwards to get a more precise failed_steps info.
        self._UpdateFirstFailureOnTestLevel(
            master_name, builder_name, build_number, step_name,
            failed_step, http_client)

    self._UpdateFailureInfoBuilds(failed_steps, builds)


  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number):
    """
    Args:
      master_name (str): the master name of a build.
      builder_name (str): the builder name of a build.
      build_number (int): the build number of a build.

    Returns:
      A dict in the following form:
      {
        "master_name": "chromium.gpu",
        "builder_name": "GPU Linux Builder"
        "build_number": 25410,
        "failed": true,
        "failed_steps": {
          "compile": {
            "last_pass": 25408,
            "current_failure": 25410,
            "first_failure": 25409
          }
        },
        "builds": {
          "25408": {
            "chromium_revision": "474ab324d17d2cd198d3fb067cabc10a775a8df7"
            "blame_list": [
              "474ab324d17d2cd198d3fb067cabc10a775a8df7"
            ],
          },
          "25409": {
            "chromium_revision": "33c6f11de20c5b229e102c51237d96b2d2f1be04"
            "blame_list": [
              "9d5ebc5eb14fc4b3823f6cfd341da023f71f49dd",
              ...
            ],
          },
          "25410": {
            "chromium_revision": "4bffcd598dd89e0016208ce9312a1f477ff105d1"
            "blame_list": [
              "b98e0b320d39a323c81cc0542e6250349183a4df",
              ...
            ],
          }
        }
      }
    """
    build_info = self._ExtractBuildInfo(master_name, builder_name, build_number)

    if not build_info:  # pragma: no cover
      raise pipeline.Retry('Failed to extract build info.')

    failure_info = {
        'failed': True,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'chromium_revision': build_info.chromium_revision,
        'builds': {},
        'failed_steps': {},
    }

    if (build_info.result == buildbot.SUCCESS or
        not build_info.failed_steps):
      failure_info['failed'] = False
      return failure_info

    builds = dict()
    self._SaveBlamelistAndChromiumRevisionIntoDict(build_info, builds)

    failed_steps = self._CreateADictOfFailedSteps(build_info)

    # Checks first failed builds for each failed step.
    self._CheckForFirstKnownFailure(
        master_name, builder_name, build_number, failed_steps, builds)

    # Checks first failed builds for each failed test.
    self._CheckFirstKnownFailureForSwarmingTests(
        master_name, builder_name, build_number, failed_steps, builds)

    failure_info['builds'] = builds
    failure_info['failed_steps'] = failed_steps

    # Starts a new try_job if needed.
    failure_result_map = try_job_util.ScheduleTryJobIfNeeded(
        master_name, builder_name, build_number, failed_steps, builds)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.not_passed_steps = build_info.not_passed_steps
    analysis.failure_result_map = failure_result_map
    analysis.put()

    return failure_info
