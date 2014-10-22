#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from appengine_module.testing_utils import testing
from appengine_module.test_results.model.testname import TestName

class TestNameTest(testing.AppengineTestCase):

  def testTestNameRoundTrip(self):
    self.assertFalse(TestName.hasTestName('foo'))
    self.assertRaises(AssertionError, TestName.getTestName, 123)
    k = TestName.getKey('bar')
    self.assertTrue(k)
    self.assertEqual(TestName.getAllKeys('bar'), [k])
    self.assertEquals(TestName.getTestName(k), 'bar')


if __name__ == '__main__':
  unittest.main()
