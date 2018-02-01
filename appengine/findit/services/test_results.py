# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for test results related operations."""

from common.findit_http_client import FinditHttpClient
from services import gtest
from services.gtest import GtestResults
from waterfall import swarming_util


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
    output_json, _ = swarming_util.DownloadTestResults(isolated_data,
                                                       http_client)
    if not output_json:
      # TODO(lijeffrey): Report/handle error returned from _DownloadTestResults.
      return None
    shard_results.append(output_json)

  if not shard_results:
    return []

  if len(list_isolated_data) == 1:
    return shard_results[0]

  #TODO(crbug/806002): support other type of tests.
  test_result_object = _GetTestResultObject(shard_results[0])
  return (test_result_object.GetMergedTestResults(shard_results)
          if test_result_object else {
              'all_tests': [],
              'per_iteration_data': []
          })
