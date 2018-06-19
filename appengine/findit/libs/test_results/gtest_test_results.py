# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for gtest-related operations.

It provides functions to:
  * normalize the test names
  * concatenate gtest logs
  * Remove platform from step name.
"""

import base64
import cStringIO

from libs.gtest_name_util import RemoveAllPrefixesFromTestName
from libs.test_results.base_test_results import BaseTestResults
from libs.test_results.classified_test_results import ClassifiedTestResults
from services import constants

# Invalid gtest result error codes.
# TODO(crbug.com/785463): Use enum for error codes.
RESULTS_INVALID = 10

# Statuses for gtest results.
# Other statuses will be considered as failures.
SUCCESS = 'SUCCESS'
SKIPPED = 'SKIPPED'
UNKNOWN = 'UNKNOWN'

_NON_FAILURE_STATUSES = [SUCCESS, SKIPPED, UNKNOWN]


class GtestTestResults(BaseTestResults):

  # TODO(crbug/805732): Get rid of repeated decode/encode operations.
  def ConcatenateTestLog(self, string1, string2):
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

  def GetConsistentTestFailureLog(self):
    """Analyzes the archived gtest json results and extract reliable failures.

    Returns:
      A string contains the names of reliable test failures and related
      log content.
      If test_results_json in gtest json result is 'invalid', we will return
      'invalid' as the result.
      If we find out that all the test failures in this step are flaky, we will
      return 'flaky' as result.
    """
    sio = cStringIO.StringIO()
    for iteration in self.test_results_json['per_iteration_data']:
      for test_name in iteration.keys():
        is_reliable_failure = True

        for test_run in iteration[test_name]:
          # We will ignore the test if some of the attempts were success.
          if test_run['status'] == SUCCESS:
            is_reliable_failure = False
            break

        if is_reliable_failure:  # all attempts failed
          for test_run in iteration[test_name]:
            sio.write(base64.b64decode(test_run['output_snippet_base64']))

    failed_test_log = sio.getvalue()
    sio.close()

    if not failed_test_log:
      return constants.FLAKY_FAILURE_LOG

    return failed_test_log

  def DoesTestExist(self, test_name):
    """Determines whether test_name is in test_results_json's 'all_tests' field.

    Args:
      test_name (str): The name of the test to check.

    Returns:
      True if the test exists according to test_results_json, False otherwise.
    """
    return test_name in (self.test_results_json.get('all_tests') or [])

  def IsTestEnabled(self, test_name):
    """Returns True if the test is enabled, False otherwise."""
    if not self.test_results_json:
      return False

    all_tests = self.test_results_json.get('all_tests', [])
    disabled_tests = self.test_results_json.get('disabled_tests', [])

    # Checks if one test was enabled by checking the test results.
    # If the disabled tests array is empty, we assume the test is enabled.
    return test_name in all_tests and test_name not in disabled_tests

  def GetFailedTestsInformation(self):
    """Parses the json data to get all the reliable failures' information."""
    failed_test_log = {}
    reliable_failed_tests = {}

    for iteration in (self.test_results_json.get('per_iteration_data') or []):
      for test_name in iteration.keys():

        if (any(test['status'] in _NON_FAILURE_STATUSES
                for test in iteration[test_name])):
          # Ignore the test if any of the attempts didn't fail.
          # If a test is skipped, that means it was not run at all.
          # Treats it as success since the status cannot be determined.
          continue

        # Stores the output to the step's log_data later.
        failed_test_log[test_name] = ''
        for test in iteration[test_name]:
          failed_test_log[test_name] = self.ConcatenateTestLog(
              failed_test_log[test_name], test.get('output_snippet_base64', ''))
        reliable_failed_tests[test_name] = RemoveAllPrefixesFromTestName(
            test_name)

    return failed_test_log, reliable_failed_tests

  def IsTestResultUseful(self):
    """Checks if the log contains useful information."""
    # If this task doesn't have result, per_iteration_data will look like
    # [{}, {}, ...]
    return self.test_results_json and any(
        self.test_results_json.get('per_iteration_data') or [])

  def GetTestLocation(self, test_name):
    """Gets test location for a specific test."""
    test_locations = self.test_results_json.get('test_locations')

    if not test_locations:
      error_str = 'test_locations not found.'
      return None, error_str

    test_location = test_locations.get(test_name)

    if not test_location:
      error_str = 'test_location not found for %s.' % test_name
      return None, error_str
    return test_location, None

  def GetClassifiedTestResults(self):
    """Parses gtest results, counts and classifies test results by:
      * status_group: passes/failures/skips/unknowns,
      * status: actual result status.

    Also counts number of expected and unexpected results for each test:
    for gtest results, assumes
      * SUCCESS is expected result for enabled tests, all the other statuses
        will be considered as unexpected.
      * SKIPPED is expected result for disabled tests, all the other statuses
        will be considered as unexpected.

    Returns:
      (ClassifiedTestResults) An object with information for each test:
      * total_run: total number of runs,
      * num_expected_results: total number of runs with expected results,
      * num_unexpected_results: total number of runs with unexpected results,
      * results: classified test results in 4 groups: passes, failures, skips
        and unknowns.
    """
    if not self.IsTestResultUseful():
      return {}

    def ClassifyOneResult(test_result, status, expected_status):
      upper_status = status.upper()
      if upper_status == expected_status:
        test_result.num_expected_results += 1
      else:
        test_result.num_unexpected_results += 1

      if upper_status == SUCCESS:
        test_result.results.passes[upper_status] += 1
      elif upper_status == SKIPPED:
        test_result.results.skips[upper_status] += 1
      elif upper_status == UNKNOWN:
        test_result.results.unknowns[upper_status] += 1
      else:
        test_result.results.failures[upper_status] += 1

    test_results = ClassifiedTestResults()
    for iteration in self.test_results_json['per_iteration_data']:
      for test_name, runs in iteration.iteritems():
        base_test_name = RemoveAllPrefixesFromTestName(test_name)
        expected_status = SUCCESS if self.IsTestEnabled(
            base_test_name) else SKIPPED

        if base_test_name == test_name:
          test_results[base_test_name].total_run += len(runs)
          for run in runs:
            ClassifyOneResult(test_results[base_test_name], run['status'],
                              expected_status)
        else:
          # Test name is in the format (PRE_)+test, consolidates such results
          # into base tests' results. Failure of PRE_tests will stop base tests
          # from running, so count failures of PRE_ tests into failures of base
          # tests. But successful PRE_tests are prerequisites for base test to
          # run, so ignore successful PRE_tests runs to prevent double counting.
          for run in runs:
            if run['status'] != SUCCESS:
              test_results[base_test_name].total_run += 1
              ClassifyOneResult(test_results[base_test_name], run['status'],
                                expected_status)

    return test_results

  @staticmethod
  def GetMergedTestResults(shard_results):
    """Merges the shards into one.

    Args:
      shard_results (list): A list of dicts with individual shard results.

    Returns:
      A dict with the following form:
      {
        'all_tests':[
          'AllForms/FormStructureBrowserTest.DataDrivenHeuristics/0',
          'AllForms/FormStructureBrowserTest.DataDrivenHeuristics/1',
          'AllForms/FormStructureBrowserTest.DataDrivenHeuristics/10',
          ...
        ]
        'per_iteration_data':[
          {
            'AllForms/FormStructureBrowserTest.DataDrivenHeuristics/109': [
              {
                'elapsed_time_ms': 4719,
                'losless_snippet': true,
                'output_snippet': '[ RUN      ] run outputs\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFsbEZvcm1zL0Zvcm1T'
                'status': 'SUCCESS'
              }
            ],
          },
          ...
        ]
      }
    """
    if len(shard_results) == 1:
      return shard_results[0]

    def MergeListsOfDicts(merged, shard):
      """Merges the ith dict in shard onto the ith dict of merged."""
      min_len = min(len(merged), len(shard))
      for i in xrange(min_len):
        # Updates merged with data in shard.
        merged[i].update(shard[i])
      for k in xrange(min_len, len(shard)):
        # If shard has a longer length, appends the rest data in shard.
        merged.append(shard[k])

    merged_results = {'all_tests': set(), 'per_iteration_data': []}
    for shard_result in shard_results:
      merged_results['all_tests'].update(shard_result.get('all_tests', []))
      MergeListsOfDicts(merged_results['per_iteration_data'],
                        shard_result.get('per_iteration_data', []))
    merged_results['all_tests'] = sorted(merged_results['all_tests'])
    return merged_results

  @staticmethod
  def IsTestResultsInExpectedFormat(test_results_json):
    """Checks if the log can be parsed by gtest.

    Args:
      test_results_json (dict): It should be in below format:
      {
          'all_tests': ['test1',
                        'test2',
                        ...],
          'per_iteration_data': [
              {
                  'test1': [
                    {
                        'status': 'SUCCESS',
                        'output_snippet': 'output',
                        ...
                    }
                  ],
                  'test2': [
                      {},
                      {},
                      ...
                  ]
              }
          ]
      }

    """
    return (isinstance(test_results_json, dict) and
            isinstance(test_results_json.get('all_tests'), list) and
            isinstance(test_results_json.get('per_iteration_data'), list) and
            all(
                isinstance(i, dict)
                for i in test_results_json.get('per_iteration_data')))
