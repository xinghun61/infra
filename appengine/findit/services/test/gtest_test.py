# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock
import os

from services import gtest
from services import constants
from services.gtest import GtestResults
from waterfall.test import wf_testcase

_SAMPLE_TEST_RESULTS = {
    'all_tests': [
        'Unittest1.Subtest1', 'Unittest1.Subtest2', 'Unittest2.PRE_Subtest1',
        'Unittest2.Subtest2'
    ],
    'per_iteration_data': [{
        'Unittest1.Subtest1': [{
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }],
        'Unittest1.Subtest2': [{
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDog'
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDog'
        }],
        'Unittest2.PRE_Subtest1': [{
            'status': 'FAILURE',
            'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMz'
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMz'
        }],
        'Unittest2.Subtest2': [{
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }]
    }]
}


class GtestTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(GtestTest, self).setUp()
    self.gtest_results = GtestResults()

  def _GetGtestResultLog(self, master_name, builder_name, build_number,
                         step_name):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data', '%s_%s_%d_%s.json' %
        (master_name, builder_name, build_number, step_name))
    with open(file_name, 'r') as f:
      return f.read()

  def testRemoveAllPrefixesNoPrefix(self):
    test = 'abc_test'
    self.assertEqual(test, self.gtest_results.RemoveAllPrefixes(test))

  def testRemoveAllPrefixes(self):
    test = 'abc_test.PRE_PRE_test1'
    self.assertEqual('abc_test.test1',
                     self.gtest_results.RemoveAllPrefixes(test))

  def testConcatenateTestLogOneStringContainsAnother(self):
    string1 = base64.b64encode('This string should contain string2.')
    string2 = base64.b64encode('string2.')
    self.assertEqual(string1,
                     self.gtest_results.ConcatenateTestLog(string1, string2))
    self.assertEqual(string1,
                     self.gtest_results.ConcatenateTestLog(string2, string1))

  def testConcatenateTestLog(self):
    string1 = base64.b64encode('string1.')
    string2 = base64.b64encode('string2.')
    self.assertEqual(
        base64.b64encode('string1.string2.'),
        self.gtest_results.ConcatenateTestLog(string1, string2))

  def testGetTestLevelFailures(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'

    expected_failure_log = ('ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'ERROR:[2]: 2594735000 bogo-microseconds\n'
                            'ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n')

    step_log = self._GetGtestResultLog(master_name, builder_name, build_number,
                                       step_name)

    failed_test_log = self.gtest_results.GetConsistentTestFailureLog(
        json.loads(step_log))
    self.assertEqual(expected_failure_log, failed_test_log)

  def testGetTestLevelFailuresFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 'abc_test'

    step_log = self._GetGtestResultLog(master_name, builder_name, build_number,
                                       step_name)

    failed_test_log = self.gtest_results.GetConsistentTestFailureLog(
        json.loads(step_log))
    self.assertEqual(constants.FLAKY_FAILURE_LOG, failed_test_log)

  def testDoesTestExist(self):
    existing_test_name = 'test'
    nonexistent_test_name = 'nonexistent_test'
    gtest_result = {
        'per_iteration_data': [{}, {}],
        'all_tests': [existing_test_name]
    }
    self.assertTrue(
        self.gtest_results.DoesTestExist(gtest_result, existing_test_name))
    self.assertFalse(
        self.gtest_results.DoesTestExist(gtest_result, nonexistent_test_name))

  def testIsTestEnabledWhenResultEmpty(self):
    test_name = 'test'
    self.assertFalse(self.gtest_results.IsTestEnabled(test_name, None))

  def testIsTestEnabledWhenDisabled(self):
    test_name = 'test'

    isolate_output = {
        'all_tests': ['a_test', 'test'],
        'disabled_tests': [test_name]
    }
    self.assertFalse(
        self.gtest_results.IsTestEnabled(test_name, isolate_output))

  def testIsTestEnabledWhenNotInAllTests(self):
    test_name = 'test'
    isolate_output = {'all_tests': [], 'disabled_tests': [test_name]}
    self.assertFalse(
        self.gtest_results.IsTestEnabled(test_name, isolate_output))

  def testIsTestEnabledWhenEnabled(self):
    test_name = 'test'
    isolate_output = {'all_tests': ['test'], 'disabled_tests': []}
    self.assertTrue(self.gtest_results.IsTestEnabled(test_name, isolate_output))

  def testGetMergedTestResults(self):
    shard_results = [{
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test1': [{
                'output_snippet': '[ RUN ] test1.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }, {
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test2': [{
                'output_snippet': '[ RUN ] test2.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }]
    expected_result = {
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test1': [{
                'output_snippet': '[ RUN ] test1.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }],
            'test2': [{
                'output_snippet': '[ RUN ] test2.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }

    self.assertEqual(expected_result,
                     self.gtest_results.GetMergedTestResults(shard_results))

  def testIsTestResultsInExpectedFormat(self):
    self.assertEqual({}, self.gtest_results.GetTestsRunStatuses(None))

  def testIsTestResultsInExpectedFormatMatch(self):
    log = {
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test1': [{
                'output_snippet': '[ RUN ] test1.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }],
            'test2': [{
                'output_snippet': '[ RUN ] test2.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }
    self.assertTrue(gtest.IsTestResultsInExpectedFormat(log))

  def testIsTestResultsInExpectedFormatNotMatch(self):
    self.assertFalse(gtest.IsTestResultsInExpectedFormat('log'))

  def testGetFailedTestsInformation(self):
    test_results = _SAMPLE_TEST_RESULTS

    side_effect = [
        'YS9iL3UxczIuY2M6MTIzNDog', 'YS9iL3UxczIuY2M6MTIzNDog',
        'RVJST1I6eF90ZXN0LmNjOjEyMz', 'RVJST1I6eF90ZXN0LmNjOjEyMz'
    ]

    expected_log = {
        'Unittest1.Subtest2': 'YS9iL3UxczIuY2M6MTIzNDog',
        'Unittest2.PRE_Subtest1': 'RVJST1I6eF90ZXN0LmNjOjEyMz'
    }
    expected_tests = {
        'Unittest1.Subtest2': 'Unittest1.Subtest2',
        'Unittest2.PRE_Subtest1': 'Unittest2.Subtest1'
    }
    with mock.patch.object(
        self.gtest_results, 'ConcatenateTestLog', side_effect=side_effect):
      log, tests = self.gtest_results.GetFailedTestsInformation(test_results)
      self.assertEqual(expected_log, log)
      self.assertEqual(expected_tests, tests)

  def testIsTestResultUseful(self):
    test_results_log = _SAMPLE_TEST_RESULTS
    self.assertTrue(self.gtest_results.IsTestResultUseful(test_results_log))

  def testTaskHasNoUsefulResult(self):
    test_results_log = {'per_iteration_data': [{}]}
    self.assertFalse(self.gtest_results.IsTestResultUseful(test_results_log))

  def testGetTestsRunStatuses(self):
    expected_statuses = {
        'Unittest1.Subtest1': {
            'SUCCESS': 1,
            'total_run': 1
        },
        'Unittest1.Subtest2': {
            'FAILURE': 2,
            'total_run': 2
        },
        'Unittest2.PRE_Subtest1': {
            'FAILURE': 2,
            'total_run': 2
        },
        'Unittest2.Subtest2': {
            'SUCCESS': 1,
            'total_run': 1
        }
    }
    self.assertEqual(
        expected_statuses,
        self.gtest_results.GetTestsRunStatuses(_SAMPLE_TEST_RESULTS))
