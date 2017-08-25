# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
from services import gtest
from waterfall.test import wf_testcase


class GtestTest(wf_testcase.WaterfallTestCase):

  def testRemoveAllPrefixesNoPrefix(self):
    test = 'abc_test'
    self.assertEqual(test, gtest.RemoveAllPrefixes(test))

  def testRemoveAllPrefixes(self):
    test = 'abc_test.PRE_PRE_test1'
    self.assertEqual('abc_test.test1', gtest.RemoveAllPrefixes(test))

  def testConcatenateTestLogOneStringContainsAnother(self):
    string1 = base64.b64encode('This string should contain string2.')
    string2 = base64.b64encode('string2.')
    self.assertEqual(string1, gtest.ConcatenateTestLog(string1, string2))
    self.assertEqual(string1, gtest.ConcatenateTestLog(string2, string1))

  def testConcatenateTestLog(self):
    string1 = base64.b64encode('string1.')
    string2 = base64.b64encode('string2.')
    self.assertEqual(
        base64.b64encode('string1.string2.'),
        gtest.ConcatenateTestLog(string1, string2))
