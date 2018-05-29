# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for webkit-layout-tests-related operations."""

import re

from libs.test_results.base_test_results import BaseTestResults
from libs.test_results.classified_test_results import ClassifiedTestResults

# PASSING_STATUSES, FAILING_STATUSES and SKIPPING_STATUSES are copied from
# https://chromium.googlesource.com/chromium/tools/build/+/80940a89cc82f08cca98eb220d9c4b39a6000451/scripts/slave/recipe_modules/test_utils/util.py
PASSING_STATUSES = (
    # PASS - The test ran as expected.
    'PASS',
    # REBASELINE, NEEDSREBASELINE, NEEDSMANUALREBASELINE - Layout test
    # specific. Considers all *BASELINE results non-failures.
    'REBASELINE',
    'NEEDSREBASELINE',
    'NEEDSMANUALREBASELINE',
)

FAILING_STATUSES = (
    # FAIL - The test did not run as expected.
    'FAIL',
    # CRASH - The test runner crashed during the test.
    'CRASH',
    # TIMEOUT - The test hung (did not complete) and was aborted.
    'TIMEOUT',
    # MISSING - Layout test specific. The test completed but we could not
    # find an expected baseline to compare against.
    'MISSING',
    # LEAK - Layout test specific. Memory leaks were detected during the
    # test execution.
    'LEAK',
    # TEXT, AUDIO, IMAGE, IMAGE+TEXT - Layout test specific, deprecated.
    # The test is expected to produce a failure for only some parts.
    # Normally you will see "FAIL" instead.
    'TEXT',
    'AUDIO',
    'IMAGE',
    'IMAGE+TEXT',
)

SKIPPING_STATUSES = (
    # SKIP - The test was not run.
    'SKIP',
    'WONTFIX')

# These statuses should not appear in actual results, rather they should only
# appear in expects.
NON_TEST_OUTCOME_EXPECTATIONS = ('REBASELINE', 'SKIP', 'SLOW', 'WONTFIX')

# TODO (crbug/835960): Use third_party/blink/web_tests instead when tests are
# moved.
_BASE_FILE_PATH = 'third_party/WebKit/LayoutTests'

_VIRTUAL_TEST_NAME_PATTERN = re.compile(r'^virtual/[^/]+/(.*)$')


class WebkitLayoutTestResults(BaseTestResults):

  def __init__(self, raw_test_results_json):
    super(WebkitLayoutTestResults, self).__init__(raw_test_results_json)
    self.test_results_json = WebkitLayoutTestResults.FlattenTestResults(
        raw_test_results_json)

  def GetConsistentTestFailureLog(self):
    """Returns an empty string.

    There is no log for test failures in output.json.
    TODO (crbug/806002): Get test failure log from other logs.
    """
    return ''

  def DoesTestExist(self, test_name):
    """Checks if can find the test name in test_results if result is valid.

    Returns:
      True if test_results_json is valid and the test exists in
      test_results_json, False otherwise.
    """
    return bool(
        self.test_results_json and
        (self.test_results_json.get('tests') or {}).get(test_name))

  def IsTestEnabled(self, test_name):
    """Returns True if the test is enabled, False otherwise.

    A test can be skipped by setting the expected result to SKIP or WONTFIX.
    But the actual result for a skipped test will only be SKIP but not WONTFIX.
    """
    if not self.DoesTestExist(test_name):
      return False

    test_result = self.test_results_json['tests'][test_name]
    return bool(
        test_result and
        not any(s in test_result['expected'] for s in SKIPPING_STATUSES))

  def GetFailedTestsInformation(self):
    """Parses the json data to get all reliable failures' information.

    Currently this method will only get:
    - failed tests in a test step on waterfall from output.json, not include
      flakes (tests that eventually passed during retry).

    TODO(crbug/836994): parse other test results to get failed tests info.

    Returns:
      failed_test_log: Logs for failed tests, currently only related test file.
      reliable_failed_tests: reliable failed tests, and the base name for each
        test - For webkit_layout_test base name should be the same as test name.
    """
    if not self.test_results_json or not self.test_results_json.get('tests'):
      return {}, {}

    reliable_failed_tests = {}
    for test_name, test_result in self.test_results_json['tests'].iteritems():
      if test_result.get('actual'):  # pragma: no branch.
        actuals = test_result['actual'].split(' ')
        expects = test_result['expected'].split(' ')
        if all(
            result in FAILING_STATUSES and
            not self.ResultWasExpected(result, expects)
            for result in set(actuals)):  # pragma: no branch.
          # A relibale failure is found when all test results are failing
          # statuses.
          # For the case where test failed with different statuses, we still
          # treat it as a reliable failure to be consistent with other tools.
          reliable_failed_tests[test_name] = test_name

    return {}, reliable_failed_tests

  def IsTestResultUseful(self):
    """Checks if the log contains useful information."""
    return bool(
        self.test_results_json and
        self.test_results_json.get('num_failures_by_type') and
        self.test_results_json.get('tests') and all(
            isinstance(i, dict) and i.get('actual') and i.get('expected')
            for i in self.test_results_json['tests'].itervalues()))

  def GetTestLocation(self, test_name):
    """Gets test location for a specific test.

    Test file path is constructed from test_name based on some heuristic rule:
     1. For test_name in the format like 'virtual/a/bb/ccc.html', file path
       should be: 'third_party/WebKit/LayoutTests/bb/ccc.html'
     2. For other test names, file path should like
      'third_party/WebKit/LayoutTests/%s' % test_name

    # TODO(crbug/806002): Handle below cases.
    There are other cases which has NOT been covered:
    1. Baseline files: for example, for a test a/bb/ccc.html, it's
      possible to find a file like
      'third_party/WebKit/LayoutTests/a/bb/ccc_expected.txt'. Such files should
      also be considered to add to test locations, but not covered right now.
    2. Derived tests: for example, for a file named external/wpt/foo.any.js,
      there will be two tests generated from it, external/wpt/foo.window.html
      and external/wpt/foo.worker.html.

    There will be no line number info for webkit_layout_tests because typically
    a file is a test.

    Note: Since the test location is gotten from heuristic, it will not be as
    reliable as gtest (which is from test results log): file might not exist.

    Returns:
      (dict, str): A dict containing test location info and error string if any.
    """
    if not self.DoesTestExist(test_name):
      return None, 'test_location not found for %s.' % test_name

    match = _VIRTUAL_TEST_NAME_PATTERN.match(test_name)
    if match:
      test_name = match.group(1)
    return {
        'line': None,
        'file': '%s/%s' % (_BASE_FILE_PATH, test_name),
    }, None

  def GetClassifiedTestResults(self):
    """Parses webkit_layout_test results, counts and classifies test results by:
      * status_group: passes/failures/skips/unknowns,
      * status: actual result status.

    Also counts number of expected and unexpected results for each test:
      if the status is included in expects or can be considered as expected, it
      is expected; otherwise it's unexpected.

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

    test_results = ClassifiedTestResults()
    for test_name, test_result in self.test_results_json['tests'].iteritems():
      actuals = test_result['actual'].split(' ')
      expects = test_result['expected'].split(' ')

      test_results[test_name].total_run = len(actuals)

      for actual in actuals:
        if self.ResultWasExpected(actual, expects):
          test_results[test_name].num_expected_results += 1
        else:
          test_results[test_name].num_unexpected_results += 1

        if actual in PASSING_STATUSES:
          test_results[test_name].results.passes[actual] += 1
        elif actual in FAILING_STATUSES:
          test_results[test_name].results.failures[actual] += 1
        elif actual in SKIPPING_STATUSES:
          test_results[test_name].results.skips[actual] += 1
        else:
          test_results[test_name].results.unknowns[actual] += 1
    return test_results

  @staticmethod
  def IsTestResultsInExpectedFormat(test_results_json):
    """Checks if the log can be parsed by this parser.

    Args:
      test_results_json (dict): It should be in one of below formats:
     {
      "tests": {
        "mojom_tests": {
          "parse": {
            "ast_unittest": {
              "ASTTest": {
                "testNodeBase": {
                  "expected": "PASS",
                  "actual": "PASS",
                  "artifacts": {
                    "screenshot": ["screenshots/page.png"],
                  }
                }
              }
            }
          }
        }
      },
      "interrupted": false,
      "path_delimiter": ".",
      "version": 3,
      "seconds_since_epoch": 1406662283.764424,
      "num_failures_by_type": {
        "FAIL": 0,
        "PASS": 1
      },
      "artifact_types": {
        "screenshot": "image/png"
      }
    }
    Or
    {
      "tests": {
        "mojom_tests/parse/ast_unittest/ASTTest/testNodeBase": {
          "expected": "PASS",
          "actual": "PASS",
          "artifacts": {
            "screenshot": ["screenshots/page.png"],
          }
        }
      },
      "interrupted": false,
      "path_delimiter": ".",
      "version": 3,
      "seconds_since_epoch": 1406662283.764424,
      "num_failures_by_type": {
        "FAIL": 0,
        "PASS": 1
      },
      "artifact_types": {
        "screenshot": "image/png"
      }
    }

    """
    if (not isinstance(test_results_json, dict) or
        not isinstance(test_results_json.get('tests'), dict)):
      return False

    flattened = WebkitLayoutTestResults.FlattenTestResults(test_results_json)
    return all(
        isinstance(i, dict) and i.get('actual') and i.get('expected')
        for i in flattened['tests'].itervalues())

  @staticmethod
  def _GetPathDelimiter(test_results_json):
    """Gets path delimiter, default to '/'."""
    return test_results_json.get('path_delimiter') or '/'

  @staticmethod
  def FlattenTestResults(test_results_json):
    """Flatten test_results_json['tests'] from a trie to a one level dict
      and generate new format test_results_json."""
    if not test_results_json or not test_results_json.get('tests'):
      return test_results_json

    sample_key = test_results_json['tests'].keys()[0]
    path_delimiter = WebkitLayoutTestResults._GetPathDelimiter(
        test_results_json)
    if path_delimiter in sample_key:
      # This should not happen in raw data, assuming the test results log is
      # already flattened.
      return test_results_json

    # Checks if the sub_test_results_json is a leaf node.
    # Checks if can find actual and expected keys in dict since they are
    # required fields in per-test results.
    def is_a_leaf(sub_test_results_json):
      return (sub_test_results_json.get('actual') and
              sub_test_results_json.get('expected'))

    flattened = {}

    def flatten(tests, parent_key=''):
      for k, v in tests.items():
        new_key = parent_key + path_delimiter + k if parent_key else k
        if isinstance(v, dict):
          if not is_a_leaf(v):
            flatten(v, new_key)
          else:
            flattened[new_key] = v

    new_results = {}
    for k, v in test_results_json.iteritems():
      if k == 'tests':
        flatten(v)
        new_results[k] = flattened
      else:
        new_results[k] = v
    return new_results

  @staticmethod
  def GetMergedTestResults(shard_results):
    """Merges the shards into one and returns the flatten version.

    Args:
      shard_results (list): A list of dicts with individual shard results.

    Returns:
      A dict with
       - all tests in shards
       - constants across all shards
       - accumulated values for some keys
    """

    if len(shard_results) == 1:
      return WebkitLayoutTestResults.FlattenTestResults(shard_results[0])

    def MergeAddable(key, merged_value, shard_value):
      if (merged_value and type(merged_value) != type(shard_value)):
        raise Exception('Different value types for key %s when merging '
                        'json test results.' % key)

      if isinstance(shard_value, int):
        merged_value = shard_value + (merged_value or 0)
      elif isinstance(shard_value, dict):
        merged_value = merged_value or {}
        for sub_key, sub_value in shard_value.iteritems():
          merged_value[sub_key] = MergeAddable(
              sub_key, merged_value.get(sub_key), sub_value)
      else:
        raise Exception('Value for key %s is not addable.' % key)

      return merged_value

    merged_results = {}

    def MergeShards(shard_result):
      matching = [
          'builder_name', 'build_number', 'chromium_revision', 'path_delimiter'
      ]

      addable = [
          'fixable', 'num_flaky', 'num_passes', 'num_regressions', 'skipped',
          'skips', 'num_failures_by_type'
      ]

      for key, value in shard_result.iteritems():
        if key == 'interrupted':
          # If any shard is interrupted, mark the whole thing as interrupted.
          merged_results[key] = value or merged_results.get(key, False)
        elif key in matching:
          # These keys are constants which should be the same across all shards.
          if key in merged_results and merged_results[key] != value:
            raise Exception('Different values for key %s when merging '
                            'json test results: %s vs %s.' %
                            (key, merged_results.get(key), value))
          merged_results[key] = value
        elif key in addable:
          # These keys are accumulated sums we want to add together.
          merged_results[key] = MergeAddable(key, merged_results.get(key),
                                             value)
        elif key == 'tests':
          merged_results[key] = merged_results.get(key) or {}
          merged_results[key].update(value)

    for shard_result in shard_results:
      MergeShards(WebkitLayoutTestResults.FlattenTestResults(shard_result))

    return merged_results

  @staticmethod
  def ResultWasExpected(result, expected_results):
    """Returns whether the result can be treated as an expected result.

    Reference: https://chromium.googlesource.com/chromium/src/+/519d9521d16d9d3af3036daf4d1d5f4398f4396a/third_party/blink/tools/blinkpy/web_tests/models/test_expectations.py#970
    Args:
        result: actual result of a test execution
        expected_results: list of results listed in test_expectations
    """
    if not set(expected_results) - set(NON_TEST_OUTCOME_EXPECTATIONS):
      expected_results = set(['PASS'])

    if result in expected_results:
      return True
    if result in ('PASS', 'TEXT', 'IMAGE', 'IMAGE+TEXT', 'AUDIO',
                  'MISSING') and 'NEEDSMANUALREBASELINE' in expected_results:
      return True
    if result in ('TEXT', 'IMAGE', 'IMAGE+TEXT',
                  'AUDIO') and 'FAIL' in expected_results:
      return True
    if result == 'MISSING' and 'REBASELINE' in expected_results:
      return True
    if result == 'SKIP':
      return True
    return False
