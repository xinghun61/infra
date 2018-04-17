# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for test results related operations."""

from libs.test_results.gtest_test_results import GtestTestResults

_STEP_NAME_SEPARATOR = ' on '

_TEST_RESULTS = [GtestTestResults]


def GetTestResultObject(test_results_json):
  for format_class in _TEST_RESULTS:
    if format_class.IsTestResultsInExpectedFormat(test_results_json):
      return format_class(test_results_json)
  return None


def IsTestResultsValid(test_results_json):
  """Checks if the test result can be used for analysis."""
  return GetTestResultObject(test_results_json) is not None


def RemoveSuffixFromStepName(step_name):
  """Returns step name without suffix.

  Args:
    step_name: Raw step name. Example: 'net_unittests on Windows-10'.

  Returns:
    Step name without platform or the string ' on '. Example: 'net_unittests'.
  """
  return step_name.split(_STEP_NAME_SEPARATOR)[0]