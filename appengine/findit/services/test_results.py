# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for test results related operations."""

from services import constants
from services import gtest
from services.gtest import GtestResults

_STEP_NAME_SEPARATOR = ' on '


# Currently Findit only supports gtest results, later when Findit starts to
# support other type of test results, returns the object with the fit test
# result format.
def _GetTestResultObject(test_results_json):
  if gtest.IsTestResultsInExpectedFormat(test_results_json):
    return GtestResults()
  return None


def IsTestEnabled(test_results_json, test_name):
  """Returns True if the test is enabled, False otherwise."""
  # TODO (crbug/806002): Support other test suites.
  test_result_object = _GetTestResultObject(test_results_json)
  return (test_result_object.IsTestEnabled(test_results_json, test_name)
          if test_result_object else False)


def GetTestLocation(test_results_json, test_name):
  """Gets test location in log for the test."""
  # TODO (crbug/806002): Support other test suites.
  test_result_object = _GetTestResultObject(test_results_json)
  return (test_result_object.GetTestLocation(test_results_json, test_name)
          if test_result_object else (None, 'Test result format not supported'))


def GetMergedTestResults(shard_results):
  """Merges results of all shards into one result.yu"""
  # TODO(crbug/806002): support other type of tests.
  test_result_object = _GetTestResultObject(shard_results[0])
  return (test_result_object.GetMergedTestResults(shard_results)
          if test_result_object else {
              'all_tests': [],
              'per_iteration_data': []
          })


def IsTestResultsValid(test_results_json):
  """Checks if the test result can be used for analysis."""
  return _GetTestResultObject(test_results_json) is not None


def GetFailedTestsInformation(test_results_json):
  """arses the json data to get all the reliable failures' information."""
  test_result_object = _GetTestResultObject(test_results_json)
  return test_result_object.GetFailedTestsInformation(
      test_results_json) if test_result_object else ({}, {})


def GetConsistentTestFailureLog(test_results_json):
  """Analyzes the archived test json results and extract reliable failures."""
  test_result_object = _GetTestResultObject(test_results_json)
  return (test_result_object.GetConsistentTestFailureLog(test_results_json)
          if test_result_object else constants.WRONG_FORMAT_LOG)


def IsTestResultUseful(test_results_json):
  """Checks if the log contains useful information."""
  test_result_object = _GetTestResultObject(test_results_json)
  return test_result_object.IsTestResultUseful(
      test_results_json) if test_result_object else False


def GetTestsRunStatuses(test_results_json):
  """Parses test results and gets accumulated test run statuses."""
  test_result_object = _GetTestResultObject(test_results_json)
  return test_result_object.GetTestsRunStatuses(
      test_results_json) if test_result_object else {}


def DoesTestExist(test_results_json, test_name):
  """Checks if the test exists in log."""
  test_result_object = _GetTestResultObject(test_results_json)
  return test_result_object.DoesTestExist(
      test_results_json, test_name) if test_result_object else False


def RemoveSuffixFromStepName(step_name):
  """Returns step name without suffix.

  Args:
    step_name: Raw step name. Example: 'net_unittests on Windows-10'.

  Returns:
    Step name without platform or the string ' on '. Example: 'net_unittests'.
  """
  return step_name.split(_STEP_NAME_SEPARATOR)[0]
