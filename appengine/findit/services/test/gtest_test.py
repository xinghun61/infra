# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import os

from services import gtest
from waterfall.test import wf_testcase


class GtestTest(wf_testcase.WaterfallTestCase):

  def _GetGtestResultLog(self, master_name, builder_name, build_number,
                         step_name):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data', '%s_%s_%d_%s.json' %
        (master_name, builder_name, build_number, step_name))
    with open(file_name, 'r') as f:
      return f.read()

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

  def testGetTestLevelFailures(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'

    expected_failure_log = ('ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'ERROR:[2]: 2594735000 bogo-microseconds\n'
                            'ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n'
                            'a/b/u3s2.cc:110: Failure\n')

    step_log = self._GetGtestResultLog(master_name, builder_name, build_number,
                                       step_name)

    failed_test_log = gtest.GetConsistentTestFailureLog(json.loads(step_log))
    self.assertEqual(expected_failure_log, failed_test_log)

  def testGetTestLevelFailuresFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 'abc_test'

    step_log = self._GetGtestResultLog(master_name, builder_name, build_number,
                                       step_name)

    failed_test_log = gtest.GetConsistentTestFailureLog(json.loads(step_log))
    self.assertEqual(gtest.FLAKY_FAILURE_LOG, failed_test_log)

  def testGetConsistentTestFailureLogWrongFormat(self):
    step_log = {
        'tests': {
            'svg': {
                'text': {
                    'test1': {
                        'expected': 'PASS',
                        'actual': 'PASS'
                    }
                }
            }
        }
    }

    failed_test_log = gtest.GetConsistentTestFailureLog(step_log)
    self.assertEqual(gtest.WRONG_FORMAT_LOG, failed_test_log)