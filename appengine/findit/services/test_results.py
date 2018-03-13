# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for test results related operations."""

import json

from common.findit_http_client import FinditHttpClient
from services import constants
from services import gtest
from services import isolate
from services.gtest import GtestResults
from waterfall import swarming_util

_STEP_NAME_SEPARATOR = ' on '


# Currently Findit only supports gtest results, later when Findit starts to
# support other type of test results, returns the object with the fit test
# result format.
def _GetTestResultObject(test_results_log):
  if gtest.IsTestResultsInExpectedFormat(test_results_log):
    return GtestResults()
  return None


# TODO (crbug/805732): Separate logic for swarming, isolated and test_results.
def IsTestEnabled(test_name, task_id):
  """Returns True if the test is enabled, False otherwise."""
  # Get the isolated outputs from the test that was just run.
  isolate_output = swarming_util.GetIsolatedOutputForTask(
      task_id, FinditHttpClient())

  # TODO (crbug/806002): Support other test suites.
  test_result_object = _GetTestResultObject(isolate_output)
  return (test_result_object.IsTestEnabled(test_name, isolate_output)
          if test_result_object else False)


# TODO (crbug/805732): Separate logic for isolated and test_results.
def RetrieveShardedTestResultsFromIsolatedServer(list_isolated_data,
                                                 http_client):
  """Gets test results from isolated server and merge the results."""
  shard_results = []
  for isolated_data in list_isolated_data:
    file_content, _ = isolate.DownloadFileFromIsolatedServer(
        isolated_data, http_client, 'output.json')
    output_json = json.loads(file_content) if file_content else None
    if not output_json:
      return None
    shard_results.append(output_json)

  if not shard_results:
    return []

  if len(list_isolated_data) == 1:
    return shard_results[0]

  # TODO(crbug/806002): support other type of tests.
  test_result_object = _GetTestResultObject(shard_results[0])
  return (test_result_object.GetMergedTestResults(shard_results)
          if test_result_object else {
              'all_tests': [],
              'per_iteration_data': []
          })


def IsTestResultsValid(test_results_log):
  """Checks if the test result can be used for analysis."""
  return _GetTestResultObject(test_results_log) is not None


def GetFailedTestsInformation(test_results_log):
  """arses the json data to get all the reliable failures' information."""
  test_result_object = _GetTestResultObject(test_results_log)
  return test_result_object.GetFailedTestsInformation(
      test_results_log) if test_result_object else ({}, {})


def GetConsistentTestFailureLog(test_results_log):
  """Analyzes the archived test json results and extract reliable failures."""
  test_result_object = _GetTestResultObject(test_results_log)
  return (test_result_object.GetConsistentTestFailureLog(test_results_log)
          if test_result_object else constants.WRONG_FORMAT_LOG)


def IsTestResultUseful(test_results_log):
  """Checks if the log contains useful information."""
  test_result_object = _GetTestResultObject(test_results_log)
  return test_result_object.IsTestResultUseful(
      test_results_log) if test_result_object else False


def GetTestsRunStatuses(test_results_log):
  """Parses test results and gets accumulated test run statuses."""
  test_result_object = _GetTestResultObject(test_results_log)
  return test_result_object.GetTestsRunStatuses(
      test_results_log) if test_result_object else {}


def DoesTestExist(test_results_log, test_name):
  """Checks if the test exists in log."""
  test_result_object = _GetTestResultObject(test_results_log)
  return test_result_object.DoesTestExist(
      test_results_log, test_name) if test_result_object else False


def RemoveSuffixFromStepName(step_name):
  """Returns step name without suffix.

  Args:
    step_name: Raw step name. Example: 'net_unittests on Windows-10'.

  Returns:
    Step name without platform or the string ' on '. Example: 'net_unittests'.
  """
  return step_name.split(_STEP_NAME_SEPARATOR)[0]
