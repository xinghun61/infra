# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.test_location import TestLocation
from services import gtest
from services import test_results
from services.gtest import GtestResults
from waterfall.test import wf_testcase

_GTEST_RESULTS = GtestResults()


class TestResultsTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(gtest, 'IsTestResultsInExpectedFormat', return_value=False)
  def testGetTestResultObjectNoMatch(self, _):
    self.assertIsNone(test_results._GetTestResultObject('log'))

  @mock.patch.object(gtest, 'IsTestResultsInExpectedFormat', return_value=True)
  def testGetTestResultObject(self, _):
    self.assertIsNotNone(test_results._GetTestResultObject('log'))

  @mock.patch.object(
      test_results, '_GetTestResultObject', return_value=_GTEST_RESULTS)
  def testIsTestEnabled(self, _):
    test_name = 'test'
    test_result_log = {'all_tests': ['test'], 'disabled_tests': []}
    self.assertTrue(test_results.IsTestEnabled(test_result_log, test_name))

  @mock.patch.object(
      test_results, '_GetTestResultObject', return_value=_GTEST_RESULTS)
  @mock.patch.object(
      _GTEST_RESULTS, 'GetTestLocation',
      return_value=(TestLocation(file='file', line=123), None))
  def testGetTestLocation(self, *_):
    result, error = test_results.GetTestLocation('test_result_log', 'test')
    self.assertEqual({
      'file': 'file',
      'line': 123
    }, result.ToSerializable())
    self.assertIsNone(error)

  @mock.patch.object(
      test_results, '_GetTestResultObject', return_value=_GTEST_RESULTS)
  @mock.patch.object(_GTEST_RESULTS, 'GetMergedTestResults', return_value={})
  def testGetMergedTestResults(self, *_):
    self.assertEqual({}, test_results.GetMergedTestResults([{}]))

  @mock.patch.object(
      test_results, '_GetTestResultObject', return_value=_GTEST_RESULTS)
  def testIsTestResultsValid(self, _):
    self.assertTrue(test_results.IsTestResultsValid('test_results_log'))

  def testGetFailedTestsInformation(self):
    self.assertEqual(({}, {}), test_results.GetFailedTestsInformation({}))

  @mock.patch.object(
      test_results, '_GetTestResultObject', return_value=_GTEST_RESULTS)
  @mock.patch.object(
      _GTEST_RESULTS, 'GetConsistentTestFailureLog', return_value='log')
  def testGetConsistentTestFailureLog(self, *_):
    self.assertEqual('log', test_results.GetConsistentTestFailureLog('log'))

  @mock.patch.object(
      test_results, '_GetTestResultObject', return_value=_GTEST_RESULTS)
  @mock.patch.object(_GTEST_RESULTS, 'IsTestResultUseful', return_value=True)
  def testIsTestResultUseful(self, *_):
    self.assertTrue(test_results.IsTestResultUseful('log'))

  @mock.patch.object(
      test_results, '_GetTestResultObject', return_value=_GTEST_RESULTS)
  @mock.patch.object(_GTEST_RESULTS, 'GetTestsRunStatuses', return_value={})
  def testGetTestsRunStatuses(self, *_):
    self.assertEqual({}, test_results.GetTestsRunStatuses(None))

  @mock.patch.object(
      test_results, '_GetTestResultObject', return_value=_GTEST_RESULTS)
  @mock.patch.object(_GTEST_RESULTS, 'DoesTestExist', return_value=True)
  def testDoesTestExist(self, *_):
    self.assertTrue(test_results.DoesTestExist('log', 't'))

  def testRemoveSuffixFromStepName(self):
    self.assertEqual(
        'a_tests', test_results.RemoveSuffixFromStepName('a_tests on Platform'))
    self.assertEqual(
        'a_tests',
        test_results.RemoveSuffixFromStepName('a_tests on Other-Platform'))
    self.assertEqual('a_tests',
                     test_results.RemoveSuffixFromStepName('a_tests'))
