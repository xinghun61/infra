# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import mock

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
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg==',
            'output_snippet': ''
        }],
        'Unittest1.Subtest2': [{
            'status': 'FAILURE',
            'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDo=',
            'output_snippet': 'a/b/u1s2.cc:1234:'
        }, {
            'status': 'CRASH',
            'output_snippet_base64': 'Y3Jhc2hsb2c=',
            'output_snippet': 'crashlog'
        }],
        'Unittest2.PRE_Subtest1': [{
            'status': 'FAILURE',
            'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMz==',
            'output_snippet': 'ERROR:x_test.cc:123'
        }, {
            'status': 'FAILURE',
            'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMz==',
            'output_snippet': 'ERROR:x_test.cc:123'
        }],
        'Unittest2.Subtest2': [{
            'status': 'SUCCESS',
            'output_snippet_base64': 'WyAgICAgICBPSyBdCg==',
            'output_snippet': ''
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
        }],
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

    expected_log = {
        'Unittest1.Subtest2': 'YS9iL3UxczIuY2M6MTIzNDoKY3Jhc2hsb2c=',
        'Unittest2.PRE_Subtest1': 'RVJST1I6eF90ZXN0LmNjOjEyMw=='
    }
    expected_tests = {
        'Unittest1.Subtest2': 'Unittest1.Subtest2',
        'Unittest2.PRE_Subtest1': 'Unittest2.Subtest1'
    }
    test_results_object = GtestTestResults(test_results)
    log, tests = test_results_object.GetFailedTestsInformation()
    self.assertEqual(expected_log, log)
    self.assertEqual(expected_tests, tests)

  def testGetFailedTestsInformationMultipleIterationsSuccess(self):
    test_results = {
        'disabled_tests': [],
        'global_tags': [],
        'all_tests': [
            'Unittest1.Subtest1', 'Unittest1.Subtest2', 'Unittest2.Subtest1',
            'Unittest2.Subtest2'
        ],
        'per_iteration_data': [
            {
                'Unittest1.Subtest2': [{
                    'status': 'SUCCESS',
                    'output_snippet_base64': 'success Unittest1.Subtest2'
                }]
            },
            {
                'Unittest1.Subtest2': [{
                    'status': 'FAILURE',
                    'output_snippet_base64': 'fail Unittest1.Subtest2'
                }, {
                    'status': 'FAILURE',
                    'output_snippet_base64': 'fail Unittest1.Subtest2'
                }]
            },
        ]
    }

    test_results_object = GtestTestResults(test_results)
    log, tests = test_results_object.GetFailedTestsInformation()
    self.assertEqual({}, log)
    self.assertEqual({}, tests)

  def testGetFailedTestsInformationMultipleIterationsFail(self):
    test_results = {
        'disabled_tests': [],
        'global_tags': [],
        'all_tests': [
            'Unittest1.Subtest1', 'Unittest1.Subtest2', 'Unittest2.Subtest1',
            'Unittest2.Subtest2'
        ],
        'per_iteration_data': [
            {
                'Unittest1.Subtest2': [{
                    'status': 'CRASH',
                    'output_snippet': 'crash Unittest1.Subtest2'
                }]
            },
            {
                'Unittest1.Subtest2': [{
                    'status': 'FAILURE',
                    'output_snippet': 'fail Unittest1.Subtest2'
                }, {
                    'status': 'FAILURE',
                    'output_snippet': 'fail Unittest1.Subtest2'
                }]
            },
        ]
    }

    test_results_object = GtestTestResults(test_results)
    log, tests = test_results_object.GetFailedTestsInformation()

    expected_log = {
        'Unittest1.Subtest2': ('ZmFpbCBVbml0dGVzdDEuU3VidGVzdDI'
                               'KY3Jhc2ggVW5pdHRlc3QxLlN1YnRlc3Qy')
    }
    self.assertEqual(expected_log, log)
    self.assertEqual({'Unittest1.Subtest2': 'Unittest1.Subtest2'}, tests)

  def testIsTestResultUseful(self):
    self.assertTrue(GtestTestResults(_SAMPLE_TEST_RESULTS).IsTestResultUseful())

  def testTaskHasNoUsefulResult(self):
    test_results_log = {'per_iteration_data': [{}]}
    self.assertFalse(GtestTestResults(test_results_log).IsTestResultUseful())

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

  def testGetClassifiedTestResultsNoResult(self):
    self.assertEqual({}, GtestTestResults(None).GetClassifiedTestResults())

  def testGetClassifiedTestResults(self):

    test_results = {
        'all_tests': [
            'Unittest1.Subtest1', 'Unittest1.Subtest2',
            'Unittest2.PRE_Subtest1', 'Unittest2.PRE_PRE_Subtest1',
            'Unittest2.Subtest1'
        ],
        'per_iteration_data': [{
            'Unittest1.Subtest1': [{
                'status': 'UNKNOWN',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }, {
                'status': 'SUCCESS',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }],
            'Unittest1.Subtest2': [{
                'status': 'FAILURE',
                'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDog'
            }, {
                'status': 'FAILURE',
                'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDog'
            }, {
                'status': 'SUCCESS',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }],
            'Unittest2.PRE_PRE_Subtest1': [{
                'status': 'SKIPPED',
                'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMz'
            }],
            'Unittest2.PRE_Subtest1': [{
                'status': 'FAILURE',
                'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMz'
            }, {
                'status': 'FAILURE',
                'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMz'
            }, {
                'status': 'SUCCESS',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }],
            'Unittest2.Subtest1': [{
                'status': 'SUCCESS',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }],
            'Unittest3.Subtest1': [{
                'status': 'NOTRUN',
                'output_snippet_base64': ''
            }]
        }]
    }
    expected_result = {
        'Unittest1.Subtest1': {
            'total_run': 2,
            'num_expected_results': 1,
            'num_unexpected_results': 1,
            'results': {
                'passes': {
                    'SUCCESS': 1
                },
                'failures': {},
                'skips': {},
                'unknowns': {
                    'UNKNOWN': 1
                },
                'notruns': {},
            }
        },
        'Unittest1.Subtest2': {
            'total_run': 3,
            'num_expected_results': 1,
            'num_unexpected_results': 2,
            'results': {
                'passes': {
                    'SUCCESS': 1
                },
                'failures': {
                    'FAILURE': 2
                },
                'skips': {},
                'unknowns': {},
                'notruns': {},
            }
        },
        'Unittest2.Subtest1': {
            'total_run': 4,
            'num_expected_results': 1,
            'num_unexpected_results': 3,
            'results': {
                'passes': {
                    'SUCCESS': 1,
                },
                'failures': {
                    'FAILURE': 2
                },
                'skips': {
                    'SKIPPED': 1
                },
                'unknowns': {},
                'notruns': {},
            }
        },
        'Unittest3.Subtest1': {
            'total_run': 1,
            'num_expected_results': 0,
            'num_unexpected_results': 1,
            'results': {
                'passes': {
                },
                'failures': {
                },
                'skips': {
                },
                'unknowns': {},
                'notruns': {
                  'NOTRUN': 1
                },
            }
        }
    }
    result = GtestTestResults(test_results).GetClassifiedTestResults()
    for test_name, expected_test_result in expected_result.iteritems():
      self.assertEqual(expected_test_result, result[test_name].ToDict())

  def testcontains_all_tests(self):
    self.assertTrue(GtestTestResults({}).contains_all_tests)
