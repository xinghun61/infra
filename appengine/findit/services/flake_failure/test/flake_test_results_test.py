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
