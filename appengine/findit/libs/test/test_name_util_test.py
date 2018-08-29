# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs import test_name_util
from waterfall.test import wf_testcase


class TestNameUtilTest(wf_testcase.WaterfallTestCase):

  def testRemoveAllPrefixesFromGTestNameNoPrefix(self):
    test = 'abc_test'
    self.assertEqual(test, test_name_util.RemoveAllPrefixesFromGTestName(test))

  def testRemoveAllPrefixesFromGTestName(self):
    test = 'abc_test.PRE_PRE_test1'
    self.assertEqual('abc_test.test1',
                     test_name_util.RemoveAllPrefixesFromGTestName(test))

  def testRemoveValueParametersFromGTestName(self):
    test_name = 'A/ColorSpaceTest.testNullTransform/1'
    self.assertEqual('ColorSpaceTest.testNullTransform',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testValueParametersWithoutInstantiationName(self):
    test_name = 'ColorSpaceTest.testNullTransform/1'
    self.assertEqual('ColorSpaceTest.testNullTransform',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testRemoveTypeParametersFromGTestName(self):
    test_name = '1/GLES2DecoderPassthroughFixedCommandTest/4.InvalidCommand'
    self.assertEqual('GLES2DecoderPassthroughFixedCommandTest.InvalidCommand',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testTypeParametersWithoutInstantiationName(self):
    test_name = 'GLES2DecoderPassthroughFixedCommandTest/4.InvalidCommand'
    self.assertEqual('GLES2DecoderPassthroughFixedCommandTest.InvalidCommand',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testRemoveQueriesFromWebkitLayoutTests(self):
    test_name = 'external/wpt/editing/run/inserttext.html?2001-last'
    self.assertEqual(
        'external/wpt/editing/run/inserttext.html',
        test_name_util.RemoveSuffixFromWebkitLayoutTestName(test_name))

  def testRemoveVirtualLayersFromWebkitLayoutTestName(self):
    virtual_test_name = 'virtual/wpt/editing/run/inserttext.html'
    test_name = 'editing/run/inserttext.html'
    self.assertEqual(
        test_name,
        test_name_util.RemoveVirtualLayersFromWebkitLayoutTestName(
            virtual_test_name))
    self.assertEqual(
        test_name,
        test_name_util.RemoveVirtualLayersFromWebkitLayoutTestName(test_name))
