# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from testing_utils import testing

from libs.test_results.gtest_test_results import GtestTestResults
from libs.test_results import test_results_util


class TestResultsTest(testing.AppengineTestCase):

  @mock.patch.object(
      GtestTestResults, 'IsTestResultsInExpectedFormat', return_value=False)
  def testGetTestResultObjectNoMatch(self, _):
    self.assertIsNone(test_results_util.GetTestResultObject('log'))

  @mock.patch.object(
      GtestTestResults, 'IsTestResultsInExpectedFormat', return_value=True)
  def testGetTestResultObject(self, _):
    test_results = test_results_util.GetTestResultObject('log')
    self.assertTrue(isinstance(test_results, GtestTestResults))

  @mock.patch.object(
      test_results_util,
      'GetTestResultObject',
      return_value=GtestTestResults('test_results_log'))
  def testIsTestResultsValid(self, _):
    self.assertTrue(test_results_util.IsTestResultsValid('test_results_log'))

  def testRemoveSuffixFromStepName(self):
    self.assertEqual(
        'a_tests',
        test_results_util.RemoveSuffixFromStepName('a_tests on Platform'))
    self.assertEqual(
        'a_tests',
        test_results_util.RemoveSuffixFromStepName('a_tests on Other-Platform'))
    self.assertEqual('a_tests',
                     test_results_util.RemoveSuffixFromStepName('a_tests'))
