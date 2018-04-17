# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is the base class for test results."""


class BaseTestResults(object):

  def __init__(self, test_results_json):
    self.test_results_json = test_results_json

  def GetConsistentTestFailureLog(self):
    """Analyzes the json test results and extract reliable failure logs."""
    raise NotImplementedError()

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

  def GetTestsRunStatuses(self):
    """Parses test results and gets accumulated test run statuses.

    Returns:
      tests_statuses (dict): A dict of different statuses for each test.
    """
    raise NotImplementedError()

  def GetTestLocation(self, test_name):
    """Gets test location for a specific test."""
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