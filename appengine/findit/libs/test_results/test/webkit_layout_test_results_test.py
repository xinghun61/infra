# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs.test_results.webkit_layout_test_results import WebkitLayoutTestResults
from waterfall.test import wf_testcase

_SAMPLE_TEST_RESULTS = {
    'seconds_since_epoch': 1522268603,
    'tests': {
        'bluetooth': {
            'requestDevice': {
                'chooser': {
                    'new-scan-device-changed.html': {
                        'expected': 'PASS',
                        'actual': 'PASS',
                        'time': 0.1
                    },
                    'new-scan-device-added.html': {
                        'expected': 'PASS',
                        'time': 1.1,
                        'actual': 'CRASH FAIL',
                        'has_stderr': True,
                        'is_unexpected': True
                    },
                    'unknown-status-test.html': {
                        'expected': 'PASS',
                        'time': 1.1,
                        'actual': 'UNKNOWN',
                        'has_stderr': True,
                        'is_unexpected': True
                    }
                },
            }
        },
        'virtual': {
            'high-contrast-mode': {
                'paint': {
                    'high-contrast-mode': {
                        'image-filter-none': {
                            'gradient-noinvert.html': {
                                'expected': 'PASS FAIL',
                                'actual': 'TEXT',
                                'time': 0.3
                            }
                        },
                        'image-filter-all': {
                            'text-on-backgrounds.html': {
                                'expected': 'PASS',
                                'actual': 'PASS',
                                'has_stderr': True,
                                'time': 0.3
                            },
                            'invalid_result': []
                        }
                    }
                }
            },
            'spv2': {
                'fast': {
                    'css': {
                        'error-in-last-decl.html': {
                            'expected': 'SKIP',
                            'actual': 'SKIP',
                            'bugs': ['crbug.com/537409']
                        }
                    }
                }
            }
        }
    },
    'skipped': 1,
    'build_number': 'DUMMY_BUILD_NUMBER',
    'num_failures_by_type': {
        'SLOW': 0,
        'CRASH': 1,
        'MISSING': 0,
        'SKIP': 1,
        'IMAGE': 0,
        'LEAK': 0,
        'IMAGE+TEXT': 0,
        'FAIL': 0,
        'TEXT': 0,
        'TIMEOUT': 0,
        'PASS': 3,
        'REBASELINE': 0,
        'WONTFIX': 0,
        'AUDIO': 0,
        'NEEDSMANUALREBASELINE': 0
    },
    'interrupted': False,
    'path_delimiter': '/',
    'layout_tests_dir': '/b/s/w/ir/third_party/WebKit/LayoutTests',
    'flag_name': None,
    'version': 3,
    'chromium_revision': '',
    'num_passes': 3,
    'pixel_tests_enabled': True,
    'num_regressions': 1,
    'fixable': 0,
    'num_flaky': 0,
    'random_order_seed': 4,
    'builder_name': ''
}

_SAMPLE_FLATTEN_TEST_RESULTS = {
    'seconds_since_epoch': 1522268603,
    'tests': {
        'bluetooth/requestDevice/chooser/new-scan-device-changed.html': {
            'expected': 'PASS',
            'actual': 'PASS',
            'time': 0.1
        },
        'virtual/spv2/fast/css/error-in-last-decl.html': {
            'expected': 'SKIP',
            'actual': 'SKIP',
            'bugs': ['crbug.com/537409']
        },
        'virtual/high-contrast-mode/paint/high-contrast-mode/image-filter-none/'
        'gradient-noinvert.html': {
            'expected': 'PASS FAIL',
            'actual': 'TEXT',
            'time': 0.3
        },
        'bluetooth/requestDevice/chooser/new-scan-device-added.html': {
            'expected': 'PASS',
            'time': 1.1,
            'actual': 'CRASH FAIL',
            'has_stderr': True,
            'is_unexpected': True
        },
        'bluetooth/requestDevice/chooser/unknown-status-test.html': {
            'expected': 'PASS',
            'time': 1.1,
            'actual': 'UNKNOWN',
            'has_stderr': True,
            'is_unexpected': True
        },
        'virtual/high-contrast-mode/paint/high-contrast-mode/'
        'image-filter-all/text-on-backgrounds.html': {
            'expected': 'PASS',
            'actual': 'PASS',
            'has_stderr': True,
            'time': 0.3
        }
    },
    'skipped': 1,
    'num_regressions': 1,
    'num_failures_by_type': {
        'SLOW': 0,
        'CRASH': 1,
        'MISSING': 0,
        'SKIP': 1,
        'IMAGE': 0,
        'LEAK': 0,
        'IMAGE+TEXT': 0,
        'REBASELINE': 0,
        'TEXT': 0,
        'TIMEOUT': 0,
        'PASS': 3,
        'FAIL': 0,
        'NEEDSMANUALREBASELINE': 0,
        'AUDIO': 0,
        'WONTFIX': 0
    },
    'interrupted': False,
    'chromium_revision': '',
    'random_order_seed': 4,
    'layout_tests_dir': '/b/s/w/ir/third_party/WebKit/LayoutTests',
    'version': 3,
    'builder_name': '',
    'num_passes': 3,
    'pixel_tests_enabled': True,
    'build_number': 'DUMMY_BUILD_NUMBER',
    'fixable': 0,
    'num_flaky': 0,
    'path_delimiter': '/',
    'flag_name': None
}


class WebkitLayoutTestResultsTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(WebkitLayoutTestResultsTest, self).setUp()
    self.test_result = WebkitLayoutTestResults(_SAMPLE_TEST_RESULTS)

  def testGetTestLevelFailures(self):
    failed_test_log = self.test_result.GetConsistentTestFailureLog()
    self.assertEqual('', failed_test_log)

  def testDoesTestExist(self):
    existing_test_name = (
        'bluetooth/requestDevice/chooser/new-scan-device-added.html')
    nonexistent_test_name = 'bluetooth/chooser/new-scan-device-added.html'

    self.assertTrue(self.test_result.DoesTestExist(existing_test_name))
    self.assertFalse(self.test_result.DoesTestExist(nonexistent_test_name))

  def testIsTestEnabledWhenResultEmpty(self):
    test_name = 'test'
    self.assertFalse(WebkitLayoutTestResults(None).IsTestEnabled(test_name))

  def testIsTestEnabledWhenDisabled(self):
    test_name = 'virtual/spv2/fast/css/error-in-last-decl.html'
    self.assertFalse(self.test_result.IsTestEnabled(test_name))

  def testIsTestEnabledWhenEnabled(self):
    test_name = 'bluetooth/requestDevice/chooser/new-scan-device-added.html'
    self.assertTrue(self.test_result.IsTestEnabled(test_name))

  def testGetMergedTestResultsAddDifferentTypes(self):
    shard_results = [_SAMPLE_TEST_RESULTS, {'tests': {}, 'skipped': '0'}]
    with self.assertRaises(Exception):
      WebkitLayoutTestResults.GetMergedTestResults(shard_results)

  def testGetMergedTestResultsAddNonAddableTypes(self):
    shard_results = [{
        'tests': {},
        'skipped': '0'
    }, {
        'tests': {},
        'skipped': '0'
    }]
    with self.assertRaises(Exception):
      WebkitLayoutTestResults.GetMergedTestResults(shard_results)

  def testGetMergedTestResultsMatchingValuesUnmatched(self):
    shard_results = [{'path_delimiter': '.'}, {'path_delimiter': '/'}]
    with self.assertRaises(Exception):
      WebkitLayoutTestResults.GetMergedTestResults(shard_results)

  def testGetMergedTestResultsOneShard(self):
    self.assertEqual(
        _SAMPLE_FLATTEN_TEST_RESULTS,
        WebkitLayoutTestResults.GetMergedTestResults([_SAMPLE_TEST_RESULTS]))

  def testGetMergedTestResults(self):
    shard_results = [
        _SAMPLE_TEST_RESULTS, {
            'seconds_since_epoch': 1522268603,
            'tests': {
                'fast': {
                    'domurl': {
                        'urlsearchparams.html': {
                            'expected': 'PASS',
                            'actual': 'PASS'
                        },
                        'urlsearchparams-constructor.html': {
                            'expected': 'PASS',
                            'actual': 'PASS',
                            'time': 0.1
                        },
                        'urlsearchparams-iterable.html': {
                            'expected': 'PASS',
                            'actual': 'PASS'
                        },
                        'urlsearchparams-has.html': {
                            'expected': 'PASS',
                            'actual': 'PASS'
                        },
                        'urlsearchparams-delete.html': {
                            'expected': 'PASS',
                            'actual': 'PASS'
                        }
                    }
                }
            },
            'skipped': 0,
            'build_number': 'DUMMY_BUILD_NUMBER',
            'num_failures_by_type': {
                'SLOW': 0,
                'CRASH': 0,
                'MISSING': 0,
                'SKIP': 0,
                'IMAGE': 0,
                'LEAK': 0,
                'IMAGE+TEXT': 0,
                'FAIL': 0,
                'TEXT': 0,
                'TIMEOUT': 0,
                'PASS': 5,
                'REBASELINE': 0,
                'WONTFIX': 0,
                'AUDIO': 0,
                'NEEDSMANUALREBASELINE': 0
            },
            'interrupted': False,
            'path_delimiter': '/',
            'layout_tests_dir': '/b/s/w/ir/third_party/WebKit/LayoutTests',
            'flag_name': None,
            'version': 3,
            'chromium_revision': '',
            'num_passes': 5,
            'pixel_tests_enabled': True,
            'num_regressions': 0,
            'fixable': 0,
            'num_flaky': 0,
            'random_order_seed': 4,
            'builder_name': ''
        }
    ]
    expected_result = {
        'tests': {
            'bluetooth/requestDevice/chooser/new-scan-device-changed.html': {
                'expected': 'PASS',
                'actual': 'PASS',
                'time': 0.1
            },
            'virtual/spv2/fast/css/error-in-last-decl.html': {
                'expected': 'SKIP',
                'actual': 'SKIP',
                'bugs': ['crbug.com/537409']
            },
            'virtual/high-contrast-mode/paint/high-contrast-mode/'
            'image-filter-none/gradient-noinvert.html': {
                'expected': 'PASS FAIL',
                'actual': 'TEXT',
                'time': 0.3
            },
            'bluetooth/requestDevice/chooser/new-scan-device-added.html': {
                'expected': 'PASS',
                'time': 1.1,
                'actual': 'CRASH FAIL',
                'has_stderr': True,
                'is_unexpected': True
            },
            'bluetooth/requestDevice/chooser/unknown-status-test.html': {
                'expected': 'PASS',
                'time': 1.1,
                'actual': 'UNKNOWN',
                'has_stderr': True,
                'is_unexpected': True
            },
            'virtual/high-contrast-mode/paint/high-contrast-mode/'
            'image-filter-all/text-on-backgrounds.html': {
                'expected': 'PASS',
                'actual': 'PASS',
                'has_stderr': True,
                'time': 0.3
            },
            'fast/domurl/urlsearchparams.html': {
                'expected': 'PASS',
                'actual': 'PASS'
            },
            'fast/domurl/urlsearchparams-constructor.html': {
                'expected': 'PASS',
                'actual': 'PASS',
                'time': 0.1
            },
            'fast/domurl/urlsearchparams-iterable.html': {
                'expected': 'PASS',
                'actual': 'PASS'
            },
            'fast/domurl/urlsearchparams-has.html': {
                'expected': 'PASS',
                'actual': 'PASS'
            },
            'fast/domurl/urlsearchparams-delete.html': {
                'expected': 'PASS',
                'actual': 'PASS'
            }
        },
        'skipped': 1,
        'num_regressions': 1,
        'num_failures_by_type': {
            'SLOW': 0,
            'CRASH': 1,
            'MISSING': 0,
            'SKIP': 1,
            'IMAGE': 0,
            'LEAK': 0,
            'IMAGE+TEXT': 0,
            'REBASELINE': 0,
            'TEXT': 0,
            'TIMEOUT': 0,
            'PASS': 8,
            'FAIL': 0,
            'NEEDSMANUALREBASELINE': 0,
            'AUDIO': 0,
            'WONTFIX': 0
        },
        'interrupted': False,
        'chromium_revision': '',
        'builder_name': '',
        'num_passes': 8,
        'build_number': 'DUMMY_BUILD_NUMBER',
        'fixable': 0,
        'num_flaky': 0,
        'path_delimiter': '/',
    }

    self.assertEqual(
        expected_result,
        WebkitLayoutTestResults.GetMergedTestResults(shard_results))

  def testIsTestResultsInExpectedFormatMatch(self):
    self.assertTrue(
        WebkitLayoutTestResults.IsTestResultsInExpectedFormat(
            _SAMPLE_TEST_RESULTS))

  def testIsTestResultsInExpectedFormatNotMatch(self):
    self.assertFalse(
        WebkitLayoutTestResults.IsTestResultsInExpectedFormat('log'))

  def testGetFailedTestsInformationNone(self):
    self.assertEqual(({}, {}),
                     WebkitLayoutTestResults({}).GetFailedTestsInformation())

  def testGetFailedTestsInformation(self):
    log, tests = self.test_result.GetFailedTestsInformation()
    self.assertEqual({
        'bluetooth/requestDevice/chooser/new-scan-device-added.html': ''
    }, log)
    self.assertEqual({
        'bluetooth/requestDevice/chooser/new-scan-device-added.html': (
            'bluetooth/requestDevice/chooser/new-scan-device-added.html')
    }, tests)

  def testIsTestResultUseful(self):
    self.assertTrue(self.test_result.IsTestResultUseful())

  def testTaskHasNoUsefulResult(self):
    self.assertFalse(WebkitLayoutTestResults({}).IsTestResultUseful())

  def testGetClassifiedTestResultsLogEmpty(self):
    self.assertEqual({},
                     WebkitLayoutTestResults(None).GetClassifiedTestResults())

  def testGetClassifiedTestResults(self):
    expected_statuses = {
        'bluetooth/requestDevice/chooser/new-scan-device-changed.html': {
            'total_run': 1,
            'num_expected_results': 1,
            'num_unexpected_results': 0,
            'results': {
                'passes': {
                    'PASS': 1
                },
                'failures': {},
                'skips': {},
                'unknowns': {},
            }
        },
        'virtual/spv2/fast/css/error-in-last-decl.html': {
            'total_run': 1,
            'num_expected_results': 1,
            'num_unexpected_results': 0,
            'results': {
                'passes': {},
                'failures': {},
                'skips': {
                    'SKIP': 1
                },
                'unknowns': {},
            }
        },
        'virtual/high-contrast-mode/paint/high-contrast-mode/image-filter-none/'
        'gradient-noinvert.html': {
            'total_run': 1,
            'num_expected_results': 1,
            'num_unexpected_results': 0,
            'results': {
                'passes': {},
                'failures': {
                    'TEXT': 1
                },
                'skips': {},
                'unknowns': {},
            }
        },
        'bluetooth/requestDevice/chooser/new-scan-device-added.html': {
            'total_run': 2,
            'num_expected_results': 0,
            'num_unexpected_results': 2,
            'results': {
                'passes': {},
                'failures': {
                    'CRASH': 1,
                    'FAIL': 1
                },
                'skips': {},
                'unknowns': {},
            }
        },
        'bluetooth/requestDevice/chooser/unknown-status-test.html': {
            'total_run': 1,
            'num_expected_results': 0,
            'num_unexpected_results': 1,
            'results': {
                'passes': {},
                'failures': {},
                'skips': {},
                'unknowns': {
                    'UNKNOWN': 1
                },
            }
        },
        'virtual/high-contrast-mode/paint/high-contrast-mode/'
        'image-filter-all/text-on-backgrounds.html': {
            'total_run': 1,
            'num_expected_results': 1,
            'num_unexpected_results': 0,
            'results': {
                'passes': {
                    'PASS': 1
                },
                'failures': {},
                'skips': {},
                'unknowns': {},
            }
        }
    }
    result = self.test_result.GetClassifiedTestResults()
    for test_name, expected_test_result in expected_statuses.iteritems():
      self.assertEqual(expected_test_result, result[test_name].ToDict())

  def testGetTestLocationNoTestLocation(self):
    result, error = self.test_result.GetTestLocation('test')
    self.assertIsNone(result)
    self.assertEqual('test_location not found for test.', error)

  def testGetTestLocation(self):
    test_name = 'bluetooth/requestDevice/chooser/new-scan-device-changed.html'
    expected_test_location = {
        'line': None,
        'file': 'third_party/WebKit/LayoutTests/bluetooth/requestDevice/'
                'chooser/new-scan-device-changed.html',
    }
    result, error = self.test_result.GetTestLocation(test_name)
    self.assertEqual(expected_test_location, result)
    self.assertIsNone(error)

  def testGetTestLocationForVirtualTest(self):
    test_name = 'virtual/spv2/fast/css/error-in-last-decl.html'
    expected_test_location = {
        'line': None,
        'file': 'third_party/WebKit/LayoutTests/fast/css/'
                'error-in-last-decl.html',
    }
    result, error = self.test_result.GetTestLocation(test_name)
    self.assertEqual(expected_test_location, result)
    self.assertIsNone(error)

  def testFlattenTestResultsAlreadyFlattened(self):
    self.assertEqual(
        _SAMPLE_FLATTEN_TEST_RESULTS,
        WebkitLayoutTestResults.FlattenTestResults(
            _SAMPLE_FLATTEN_TEST_RESULTS))

  def testResultWasExpected(self):
    cases = [  # yapf: disable
        ('PASS', ['REBASELINE'], True), ('TEXT', ['NEEDSMANUALREBASELINE'],
                                         True), ('AUDIO', ['FAIL'], True),
        ('MISSING', ['REBASELINE', 'PASS'],
         True), ('SKIP', ['PASS'], True), ('FAIL', ['PASS'], False)
    ]

    for case in cases:
      self.assertEqual(
          case[2], WebkitLayoutTestResults.ResultWasExpected(case[0], case[1]))

  def testcontains_all_tests(self):
    self.assertTrue(WebkitLayoutTestResults({}).contains_all_tests)
    self.assertFalse(
        WebkitLayoutTestResults({}, partial_result=True).contains_all_tests)
