# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from libs.test_results.gtest_test_results import GtestTestResults
from services.flake_failure import flake_test_results
from waterfall.test import wf_testcase

_GTEST_RESULT = GtestTestResults(None)


class FlakeTestResultsTest(wf_testcase.WaterfallTestCase):

  def testGetCountsFromSwarmingRerunInvalidResults(self):
    test_results = 'invalid'
    self.assertEqual(
        (None, None),
        flake_test_results.GetCountsFromSwarmingRerun(test_results))

  def testGetCountsFromSwarmingRerun(self):
    test_results = {
        'all_tests': [
            'Unittest1.Subtest1', 'Unittest1.PRE_PRE_Subtest1',
            'Unittest1.PRE_Subtest1'
        ],
        'per_iteration_data': [{
            'Unittest1.Subtest1': [{
                'status': 'SUCCESS',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }],
            'Unittest1.PRE_PRE_Subtest1': [{
                'status': 'FAILURE',
                'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDog'
            }, {
                'status': 'SUCCESS',
                'output_snippet_base64': 'YS9iL3UxczIuY2M6MTIzNDog'
            }, {
                'status': 'SUCCESS',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }],
            'Unittest1.PRE_Subtest1': [{
                'status': 'FAILURE',
                'output_snippet_base64': 'RVJST1I6eF90ZXN0LmNjOjEyMz'
            }, {
                'status': 'SUCCESS',
                'output_snippet_base64': 'WyAgICAgICBPSyBdCg=='
            }]
        }]
    }
    self.assertEqual(
        (3, 1), flake_test_results.GetCountsFromSwarmingRerun(test_results))

  def testGetCountsFromSwarmingRerunWebkitLayoutTest(self):
    test_results = {
        'seconds_since_epoch': 1522268603,
        'tests': {
            'bluetooth': {
                'requestDevice': {
                    'chooser': {
                        'new-scan-device-added.html': {
                            'expected': 'PASS',
                            'time': 1.1,
                            'actual': 'CRASH FAIL CRASH FAIL TEXT PASS PASS',
                            'has_stderr': True,
                            'is_unexpected': True
                        }
                    },
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
    self.assertEqual(
        (7, 2), flake_test_results.GetCountsFromSwarmingRerun(test_results))
