# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is the base class for test results."""


class BaseTestResults(object):

  def __init__(self, test_results_json, partial_result=False):
    self.test_results_json = test_results_json
    # If the test result is for a single shard of a multi-shards task.
    self.partial_result = partial_result

  def DoesTestExist(self, test_name):
    """Determines if a test exists in test results."""
    raise NotImplementedError()

  def IsTestEnabled(self, test_name):
    """Returns True if the test is enabled, False otherwise."""
    raise NotImplementedError()

  def GetFailedTestsInformation(self):
    """Parses the json data to get all the reliable failures' information."""
    raise NotImplementedError()

  def IsTestResultUseful(self):
    """Checks if the log contains useful information."""
    raise NotImplementedError()

  def GetTestLocation(self, test_name):
    """Gets test location for a specific test."""
    raise NotImplementedError()

  def GetClassifiedTestResults(self):
    """Parses test results, counts and classifies test results by:
      * status_group: passes/failures/skips/unknowns,
      * status: actual result status.

    Also counts number of expected and unexpected results for each test.
      All tests are expected to pass by default. However, some tests sometimes
      have different expected result(s) for some reason, for example flakiness,
      and such result statuses are usually specified in an expectation file or
      an equivalent.
      If the result status of a test run is the same as specified in the
      expectation file, it is deemed as expected; otherwise, it is deemed as
      unexpected.
      For example, if a WebKit layout test has expected result statuses
      ['PASS', 'FAIL'], then an actual run status 'FAIL' is expected,
      whereas 'TIMEOUT' is unexpected.

    Returns:
      (ClassifiedTestResults) An object with information for each test:
      * total_run: total number of runs,
      * num_expected_results: total number of runs with expected results,
      * num_unexpected_results: total number of runs with unexpected results,
      * results: classified test results in 4 groups: passes, failures, skips
        and unknowns.
    """
    raise NotImplementedError()

  @property
  def contains_all_tests(self):
    """Returns True if test results contains all tests, False otherwise.

    For gtest, each shard contains all_tests so it should always be True;
    For webkit_layout_tests, this should be True only if the test result is a
      full result of a task (meaning it should not be result of a single shard
      from a multi-shards task), False otherwise.
    """
    raise NotImplementedError()

  @staticmethod
  def GetMergedTestResults(shard_results):
    """Merges the shards into one.

    Args:
      shard_results (list): A list of dicts with individual shard results.

    Returns:
      A merged dict containing test results from all shards.
    """
    raise NotImplementedError()

  @staticmethod
  def IsTestResultsInExpectedFormat(test_results_json):
    """Checks if the test results is in the expected format of the test result
     type."""
    raise NotImplementedError()
