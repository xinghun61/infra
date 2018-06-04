# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs import gtest_name_util
from waterfall.test import wf_testcase


class GtestNameUtilTest(wf_testcase.WaterfallTestCase):

  def testRemoveAllPrefixesFromTestNameNoPrefix(self):
    test = 'abc_test'
    self.assertEqual(test, gtest_name_util.RemoveAllPrefixesFromTestName(test))

  def testRemoveAllPrefixesFromTestName(self):
    test = 'abc_test.PRE_PRE_test1'
    self.assertEqual('abc_test.test1',
                     gtest_name_util.RemoveAllPrefixesFromTestName(test))

  def testRemoveValueParametersFromTestName(self):
    test_name = 'A/ColorSpaceTest.testNullTransform/1'
    self.assertEqual('ColorSpaceTest.testNullTransform',
                     gtest_name_util.RemoveParametersFromTestName(test_name))

  def testRemoveTypeParametersFromTestName(self):
    test_name = '1/GLES2DecoderPassthroughFixedCommandTest/4.InvalidCommand'
    self.assertEqual('GLES2DecoderPassthroughFixedCommandTest.InvalidCommand',
                     gtest_name_util.RemoveParametersFromTestName(test_name))

  def testRemoveParametersFromTestNameNonOp(self):
    gtest_name = 'AMPPageLoadMetricsObserverTest.NonAMPPage'
    self.assertEqual(gtest_name,
                     gtest_name_util.RemoveParametersFromTestName(gtest_name))
    webkit_layout_test_name = (
        'webaudio/internals/scriptprocessornode-detached-no-crash.html')
    self.assertEqual(
        webkit_layout_test_name,
        gtest_name_util.RemoveParametersFromTestName(webkit_layout_test_name))