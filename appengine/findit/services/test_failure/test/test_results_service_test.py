# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import mock

from libs.test_results.gtest_test_results import GtestTestResults
from libs.test_results.webkit_layout_test_results import WebkitLayoutTestResults
from services.test_failure import test_results_service
from waterfall.test import wf_testcase

_GTEST_RESULT = GtestTestResults({})


class TestResultsUtilTest(wf_testcase.WaterfallTestCase):

  def testGetFailedTestsInformationFromTestResult(self):
    test_results_json = {
        'seconds_since_epoch': 1522268603,
        'tests': {
            'bluetooth/requestDevice/chooser/new-scan-device-changed.html': {
                'expected': 'PASS',
                'actual': 'FAIL',
                'time': 0.1
            },
            'virtual/spv2/fast/css/error-in-last-decl.html': {
                'expected': 'PASS',
                'actual': 'FAIL',
                'bugs': ['crbug.com/537409']
            },
            'virtual/high-contrast-mode/paint/high-contrast-mode/image-filter'
            '-none/gradient-noinvert.html': {
                'expected': 'PASS',
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
                'actual': 'FAIL',
                'has_stderr': True,
                'is_unexpected': True
            },
            'virtual/high-contrast-mode/paint/high-contrast-mode/'
            'image-filter-all/text-on-backgrounds.html': {
                'expected': 'PASS',
                'actual': 'FAIL',
                'has_stderr': True,
                'time': 0.3
            }
        },
    }
    test_results = WebkitLayoutTestResults(test_results_json)

    expected_failed_test_log = {
        'bluetooth/requestDevice/chooser/new-scan-device-changed.html': (
            base64.b64encode('third_party/WebKit/LayoutTests/bluetooth/request'
                             'Device/chooser/new-scan-device-changed.html')),
        'virtual/spv2/fast/css/error-in-last-decl.html': base64.b64encode(
            'third_party/WebKit/LayoutTests/fast/css/error-in-last-decl.html'
        ),
        'virtual/high-contrast-mode/paint/high-contrast-mode/image-filter-none/'
        'gradient-noinvert.html':
            base64.b64encode(
                'third_party/WebKit/LayoutTests/paint/high-contrast-mode/'
                'image-filter-none/gradient-noinvert.html'),
        'bluetooth/requestDevice/chooser/new-scan-device-added.html': (
            base64.b64encode('third_party/WebKit/LayoutTests/bluetooth/request'
                             'Device/chooser/new-scan-device-added.html')),
        'bluetooth/requestDevice/chooser/unknown-status-test.html': (
            base64.b64encode('third_party/WebKit/LayoutTests/bluetooth/request'
                             'Device/chooser/unknown-status-test.html')),
        'virtual/high-contrast-mode/paint/high-contrast-mode/'
        'image-filter-all/text-on-backgrounds.html':
            base64.b64encode(
                'third_party/WebKit/LayoutTests/paint/high-contrast-mode/'
                'image-filter-all/text-on-backgrounds.html')
    }

    self.assertEqual(
        expected_failed_test_log,
        test_results_service.GetFailedTestsInformationFromTestResult(
            test_results)[0])

  @mock.patch.object(_GTEST_RESULT, 'GetFailedTestsInformation')
  @mock.patch.object(_GTEST_RESULT, 'GetTestLocation')
  def testUseTestLocationAsTestFailureLogAllWithLog(self, mock_tl, mock_i):
    failed_test_log = {'test1': 'somelog', 'test2': 'somelog'}
    reliable_failed_tests = {'test1': 'test1', 'test2': 'test2'}
    mock_i.return_value = (failed_test_log, reliable_failed_tests)
    expected_test_results = {'test1': 'somelog', 'test2': 'somelog'}
    self.assertEqual(
        expected_test_results,
        test_results_service.GetFailedTestsInformationFromTestResult(
            _GTEST_RESULT)[0])
    self.assertFalse(mock_tl.called)
