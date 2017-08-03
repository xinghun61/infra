# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from common.waterfall import failure_type


class FailureTypeTest(unittest.TestCase):

  def testDescriptionForValidType(self):
    self.assertEqual(
        'compile',
        failure_type.GetDescriptionForFailureType(failure_type.COMPILE))

  def testDescriptionForInvalidType(self):
    self.assertIn('No description for',
                  failure_type.GetDescriptionForFailureType(0x666))

  def testFailureTypeForValidDescription(self):
    self.assertEqual(failure_type.COMPILE,
                     failure_type.GetFailureTypeForDescription('compile'))

  def testFailureTypeForInvalidDescription(self):
    with self.assertRaises(ValueError):
      failure_type.GetFailureTypeForDescription('This does not exist')
