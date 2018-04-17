# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Logic related to examine builds and determine regression range."""

import json
import logging

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from libs.test_results import test_results_util
from model.wf_step import WfStep
from services import swarmed_test_util
from services import swarming
from services.parameters import FailedTest
from services.parameters import FailedTests
from services.parameters import IsolatedDataList

_NON_FAILURE_STATUSES = ['SUCCESS', 'SKIPPED', 'UNKNOWN']


def _InitiateTestLevelFirstFailureAndSaveLog(json_data, step, failed_step=None):
  """Parses the json data and saves all the reliable failures to the step."""

  test_results = test_results_util.GetTestResultObject(json_data)
  failed_test_log, reliable_failed_tests = (
      test_results.GetFailedTestsInformation()) if test_results else ({}, {})
  if failed_step:
    failed_step.tests = failed_step.tests or FailedTests.FromSerializable({})

    for test_name, base_test_name in reliable_failed_tests.iteritems():
      # Adds the test to failed_step.
      failed_test_info = {
          'current_failure': failed_step.current_failure,
          'first_failure': failed_step.current_failure,
          'base_test_name': base_test_name,
      }
      failed_step.tests[test_name] = FailedTest.FromSerializable(
          failed_test_info)

      if failed_step.last_pass:
        failed_step.tests[test_name].last_pass = failed_step.last_pass

  step.log_data = json.dumps(failed_test_log) if failed_test_log else 'flaky'
  step.put()

  if failed_step and not failed_step.tests:  # All flaky.
    failed_step.tests = None
    return False

  return True


def _StartTestLevelCheckForFirstFailure(master_name, builder_name, build_number,
                                        step_name, failed_step, http_client):
  """Downloads test results and initiates first failure info at test level."""
  list_isolated_data = failed_step.list_isolated_data
  list_isolated_data = (
      list_isolated_data.ToSerializable() if list_isolated_data else [])
  result_log = swarmed_test_util.RetrieveShardedTestResultsFromIsolatedServer(
      list_isolated_data, http_client)

  if not test_results_util.IsTestResultsValid(result_log):
    return False

  step = WfStep.Get(master_name, builder_name, build_number, step_name)

  return _InitiateTestLevelFirstFailureAndSaveLog(result_log, step, failed_step)


def _GetSameStepFromBuild(master_name, builder_name, build_number, step_name,
                          http_client):
  """Downloads swarming test results for a step from previous build."""
  step = WfStep.Get(master_name, builder_name, build_number, step_name)

  if step and step.isolated and step.log_data:
    # Test level log has been saved for this step.
    return step

  # Sends request to swarming server for isolated data.
  step_isolated_data = swarming.GetIsolatedDataForStep(
      master_name, builder_name, build_number, step_name, http_client)

  if not step_isolated_data:
    return None

  result_log = swarmed_test_util.RetrieveShardedTestResultsFromIsolatedServer(
      step_isolated_data, http_client)

  if not test_results_util.IsTestResultsValid(result_log):
    return None

  step = WfStep.Create(master_name, builder_name, build_number, step_name)
  step.isolated = True
  _InitiateTestLevelFirstFailureAndSaveLog(result_log, step)

  return step


def _UpdateFirstFailureInfoForStep(current_build_number, failed_step):
  """Updates first_failure etc. for the step after the check for tests."""
  earliest_test_first_failure = current_build_number
  earliest_test_last_pass = current_build_number - 1
  for failed_test in failed_step.tests.itervalues():
    # Iterates through all failed tests to prepare data for step level update.
    if not failed_test.last_pass:
      # The test failed throughout checking range,
      # and there is no last_pass info for step.
      # last_pass not found.
      earliest_test_last_pass = -1
    earliest_test_first_failure = min(failed_test.first_failure,
                                      earliest_test_first_failure)
    if (failed_test.last_pass and
        failed_test.last_pass < earliest_test_last_pass):
      earliest_test_last_pass = failed_test.last_pass

  # Updates Step level first failure info and last_pass info.
  failed_step.first_failure = max(earliest_test_first_failure,
                                  failed_step.first_failure)

  if ((not failed_step.last_pass and earliest_test_last_pass >= 0) or
      (failed_step.last_pass and
       earliest_test_last_pass > failed_step.last_pass)):
    failed_step.last_pass = earliest_test_last_pass


def _UpdateFirstFailureOnTestLevel(master_name, builder_name,
                                   current_build_number, step_name, failed_step,
                                   build_numbers, http_client):
  """Iterates backwards through builds to get first failure at test level.

  Args:
    master_name(str): Name of the master of the failed build.
    builder_name(str): Name of the builder of the failed build.
    current_build_number(int): Number of the failed build.
    step_name(str): Name of one failed step the function is analyzing.
    failed_step(TestFailedStep): Known information about the failed step.
    build_numbers(list): A list of build numbers in backward order.
    http_client(FinditHttpClient): Http_client to send request.
  Returns:
    Updated failed_step with test level failure info.
  """
  farthest_first_failure = failed_step.first_failure
  if failed_step.last_pass:
    farthest_first_failure = failed_step.last_pass + 1

  unfinished_tests = failed_step.tests.keys()
  for build_number in build_numbers:
    if (build_number >= current_build_number or
        build_number < farthest_first_failure):
      continue
    # Checks back until farthest_first_failure or build 1, don't use build 0
    # since there might be some abnormalities in build 0.
    step = _GetSameStepFromBuild(master_name, builder_name, build_number,
                                 step_name, http_client)

    if not step or not step.log_data:
      raise Exception(
          'Failed to get swarming test results for build %s/%s/%d.' %
          (master_name, builder_name, build_number))

    if step.log_data.lower() == 'flaky':
      failed_test_log = {}
    else:
      try:
        failed_test_log = json.loads(step.log_data)
      except ValueError:
        logging.error('log_data %s of step %s/%s/%d/%s is not json loadable.' %
                      (step.log_data, master_name, builder_name, build_number,
                       step_name))
        continue
    test_checking_list = unfinished_tests[:]

    for test_name in test_checking_list:
      if failed_test_log.get(test_name):
        failed_step.tests[test_name].first_failure = build_number
      else:
        # Last pass for this test has been found.
        # TODO(chanli): Handle cases where the test is not run at all.
        failed_step.tests[test_name].last_pass = build_number
        unfinished_tests.remove(test_name)

    if not unfinished_tests:
      break
  _UpdateFirstFailureInfoForStep(current_build_number, failed_step)


def _UpdateFailureInfoBuilds(failed_steps, builds):
  """Deletes builds that are before the farthest last_pass."""
  build_numbers_in_builds = builds.keys()
  latest_last_pass = -1
  for failed_step in failed_steps.itervalues():
    if not failed_step.last_pass:
      return

    if (latest_last_pass < 0 or latest_last_pass > failed_step.last_pass):
      latest_last_pass = failed_step.last_pass

  for build_number in build_numbers_in_builds:
    if build_number < latest_last_pass:
      del builds[build_number]


def UpdateSwarmingSteps(master_name, builder_name, build_number, failed_steps,
                        http_client):
  """Updates swarming steps based on swarming task data.

  Searches each failed step_name to identify swarming/non-swarming steps and
  updates failed swarming steps for isolated data.
  Also creates and saves swarming steps in datastore.
  """
  build_isolated_data = swarming.GetIsolatedDataForFailedStepsInABuild(
      master_name, builder_name, build_number, failed_steps, http_client)

  if not build_isolated_data:
    return False

  new_steps = []
  for step_name in build_isolated_data:
    failed_steps[step_name].list_isolated_data = (
        IsolatedDataList.FromSerializable(build_isolated_data[step_name]))

    # Create WfStep object for all the failed steps.
    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.isolated = True
    new_steps.append(step)

  ndb.put_multi(new_steps)
  return True


def CheckFirstKnownFailureForSwarmingTests(master_name, builder_name,
                                           build_number, failure_info):
  """Uses swarming test results to update first failure info at test level."""
  http_client = FinditHttpClient()

  failed_steps = failure_info.failed_steps

  # Identifies swarming tests and saves isolated data to them.
  updated = UpdateSwarmingSteps(master_name, builder_name, build_number,
                                failed_steps, http_client)
  if not updated:
    return

  for step_name, failed_step in failed_steps.iteritems():
    if not failed_step.list_isolated_data:  # Non-swarming step.
      continue  # pragma: no cover.
    # Checks tests in one step and updates failed_step info if swarming.
    result = _StartTestLevelCheckForFirstFailure(master_name, builder_name,
                                                 build_number, step_name,
                                                 failed_step, http_client)

    if result:  # pragma: no branch
      failed_builds = sorted(failure_info.builds.keys(), reverse=True)
      # Iterates backwards to get a more precise failed_steps info.
      _UpdateFirstFailureOnTestLevel(master_name, builder_name, build_number,
                                     step_name, failed_step, failed_builds,
                                     http_client)

  _UpdateFailureInfoBuilds(failed_steps, failure_info.builds)


def AnyTestHasFirstTimeFailure(tests, build_number):
  for test_failure in tests.itervalues():
    if test_failure['first_failure'] == build_number:
      return True
  return False
