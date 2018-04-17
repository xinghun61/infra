# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import mock

from libs.test_results import gtest_test_results
from libs.test_results.gtest_test_results import GtestTestResults
from services import constants
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

_SAMPLE_TEST_RESULTS_CONSISTENT = {
    'disabled_tests': [],
    'global_tags': [],
    'all_tests': [
        'Unittest1.Subtest1', 'Unittest1.Subtest2', 'Unittest2.Subtest1',
        'Unittest2.Subtest2', 'Unittest3.Subtest1', 'Unittest3.Subtest2',
        'Unittest3.Subtest3'
    ],
    'per_iteration_data': [{
        'Unittest1.Subtest1': [{
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }],
        'Unittest1.Subtest2': [{
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDogRmFpbHVy'
                                     'ZQo='
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDogRmFpbHVy'
                                     'ZQo='
        }, {
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }],
        'Unittest2.Subtest1': [{
            'status': 'FAILURE',
            'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMzQKYS9iL'
                                     '3UyczEuY2M6NTY3OiBGYWlsdXJlCg=='
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'RVJST1I6WzJdOiAyNTk0NzM1MDAwIGJvZ'
                                     '28tbWljcm9zZWNvbmRzCg=='
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMzQKYS9iL'
                                     '3UyczEuY2M6NTY3OiBGYWlsdXJlCg=='
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMzQKYS9iL'
                                     '3UyczEuY2M6NTY3OiBGYWlsdXJlCg=='
        }],
        'Unittest2.Subtest2': [{
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }],
        'Unittest3.Subtest1': [{
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }],
        'Unittest3.Subtest2': [{
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJ'
                                     'lCg=='
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJ'
                                     'lCg=='
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJ'
                                     'lCg=='
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJ'
                                     'lCg=='
        }],
        'Unittest3.Subtest3': [{
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }]
    }]
}

_SAMPLE_TEST_RESULTS_FLAKE = {
    'disabled_tests': [],
    'global_tags': [],
    'all_tests': [
        'Unittest1.Subtest1', 'Unittest1.Subtest2', 'Unittest2.Subtest1',
        'Unittest2.Subtest2'
    ],
    'per_iteration_data': [{
        'Unittest1.Subtest1': [{
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }],
        'Unittest1.Subtest2': [{
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDogRmFpb'
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDogRmFpb'
        }, {
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }],
        'Unittest2.Subtest1': [{
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UyczEuY2M6NTY3OiBGYWlsdXJl'
        }, {
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }],
        'Unittest2.Subtest2': [{
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
        }]
    }]
}


class GtestTestResultsTest(wf_testcase.WaterfallTestCase):

  def testRemoveAllPrefixesFromTestNameNoPrefix(self):
    test = 'abc_test'
    self.assertEqual(test,
                     gtest_test_results._RemoveAllPrefixesFromTestName(test))

  def testRemoveAllPrefixesFromTestName(self):
    test = 'abc_test.PRE_PRE_test1'
    self.assertEqual('abc_test.test1',
                     gtest_test_results._RemoveAllPrefixesFromTestName(test))

  def testConcatenateTestLogOneStringContainsAnother(self):
    string1 = base64.b64encode('This string should contain string2.')
    string2 = base64.b64encode('string2.')
    self.assertEqual(string1,
                     GtestTestResults(None).ConcatenateTestLog(
                         string1, string2))
    self.assertEqual(string1,
                     GtestTestResults(None).ConcatenateTestLog(
                         string2, string1))

  def testConcatenateTestLog(self):
    string1 = base64.b64encode('string1.')
    string2 = base64.b64encode('string2.')
    self.assertEqual(
        base64.b64encode('string1.string2.'),
        GtestTestResults(None).ConcatenateTestLog(string1, string2))

  def testGetTestLevelFailures(self):
    expected_failure_log = ('ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'ERROR:[2]: 2594735000 bogo-microseconds\n'
                            'ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n')

    failed_test_log = GtestTestResults(
        _SAMPLE_TEST_RESULTS_CONSISTENT).GetConsistentTestFailureLog()
    self.assertEqual(expected_failure_log, failed_test_log)

  def testGetTestLevelFailuresFlaky(self):
    failed_test_log = GtestTestResults(
        _SAMPLE_TEST_RESULTS_FLAKE).GetConsistentTestFailureLog()
    self.assertEqual(constants.FLAKY_FAILURE_LOG, failed_test_log)

  def testDoesTestExist(self):
    existing_test_name = 'test'
    nonexistent_test_name = 'nonexistent_test'
    gtest_result = {
        'per_iteration_data': [{}, {}],
        'all_tests': [existing_test_name]
    }
    self.assertTrue(
        GtestTestResults(gtest_result).DoesTestExist(existing_test_name))
    self.assertFalse(
        GtestTestResults(gtest_result).DoesTestExist(nonexistent_test_name))

  def testIsTestEnabledWhenResultEmpty(self):
    test_name = 'test'
    self.assertFalse(GtestTestResults(None).IsTestEnabled(test_name))

  def testIsTestEnabledWhenDisabled(self):
    test_name = 'test'

    isolate_output = {
        'all_tests': ['a_test', 'test'],
        'disabled_tests': [test_name]
    }
    self.assertFalse(GtestTestResults(isolate_output).IsTestEnabled(test_name))

  def testIsTestEnabledWhenNotInAllTests(self):
    test_name = 'test'
    isolate_output = {'all_tests': [], 'disabled_tests': [test_name]}
    self.assertFalse(GtestTestResults(isolate_output).IsTestEnabled(test_name))

  def testIsTestEnabledWhenEnabled(self):
    test_name = 'test'
    isolate_output = {'all_tests': ['test'], 'disabled_tests': []}
    self.assertTrue(GtestTestResults(isolate_output).IsTestEnabled(test_name))

  def testGetMergedTestResultsOneShard(self):
    shard_results = [{
        'all_tests': ['test1', 'test2'],
        'per_iteration_data': [{
            'test1': [{
                'output_snippet': '[ RUN ] test1.\\r\\n',
                'output_snippet_base64': 'WyBSVU4gICAgICBdIEFjY291bnRUcm',
                'status': 'SUCCESS'
            }]
        }]
    }]
    self.assertEqual(shard_results[0],
                     GtestTestResults.GetMergedTestResults(shard_results))

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
                     GtestTestResults.GetMergedTestResults(shard_results))

  def testIsTestResultsInExpectedFormat(self):
    self.assertEqual({}, GtestTestResults(None).GetTestsRunStatuses())

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
    self.assertTrue(GtestTestResults.IsTestResultsInExpectedFormat(log))

  def testIsTestResultsInExpectedFormatNotMatch(self):
    self.assertFalse(GtestTestResults.IsTestResultsInExpectedFormat('log'))

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
    test_results_object = GtestTestResults(test_results)
    with mock.patch.object(
        test_results_object, 'ConcatenateTestLog', side_effect=side_effect):
      log, tests = test_results_object.GetFailedTestsInformation()
      self.assertEqual(expected_log, log)
      self.assertEqual(expected_tests, tests)

  def testIsTestResultUseful(self):
    self.assertTrue(GtestTestResults(_SAMPLE_TEST_RESULTS).IsTestResultUseful())

  def testTaskHasNoUsefulResult(self):
    test_results_log = {'per_iteration_data': [{}]}
    self.assertFalse(GtestTestResults(test_results_log).IsTestResultUseful())

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
        GtestTestResults(_SAMPLE_TEST_RESULTS).GetTestsRunStatuses())

  def testGetTestLocationNoTestLocations(self):
    result, error = GtestTestResults({}).GetTestLocation('test')
    self.assertIsNone(result)
    self.assertEqual('test_locations not found.', error)

  def testGetTestLocationNoTestLocation(self):
    result, error = GtestTestResults({
        'test_locations': {
            'test': {}
        }
    }).GetTestLocation('test')
    self.assertIsNone(result)
    self.assertEqual('test_location not found for test.', error)

  def testGetTestLocation(self):
    test_name = 'test'
    expected_test_location = {
        'line': 123,
        'file': '/path/to/test_file.cc',
    }
    test_results_log = {'test_locations': {test_name: expected_test_location,}}
    result, error = GtestTestResults(test_results_log).GetTestLocation('test')
    self.assertEqual(expected_test_location, result)
    self.assertIsNone(error)
