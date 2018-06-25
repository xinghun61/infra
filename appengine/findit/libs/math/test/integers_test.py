# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.math.integers import constrain


class IntegersTest(unittest.TestCase):

  def testConstrainInsideRange(self):
    for i in range(100):
      v, constrained = constrain(i, 0, 99)
      self.assertFalse(constrained)
      self.assertEqual(i, v)

  def testConstrainOutsideRange(self):
    for min_limit, max_limit in [
        (-1000, -1),
        (-1000, 1000),
        (1, 1000),
        (0, 0),
    ]:
      self.assertEqual((min_limit, True),
                       constrain(min_limit - 1000, min_limit, max_limit))
      self.assertEqual((min_limit, True),
                       constrain(min_limit - 1, min_limit, max_limit))
      self.assertEqual((min_limit, False),
                       constrain(min_limit, min_limit, max_limit))
      self.assertEqual((max_limit, True),
                       constrain(max_limit + 1000, min_limit, max_limit))
      self.assertEqual((max_limit, True),
                       constrain(max_limit + 1, min_limit, max_limit))
      self.assertEqual((max_limit, False),
                       constrain(max_limit, min_limit, max_limit))

  def testConstrainBadLimits(self):
    with self.assertRaises(Exception):
      # Inverted min, max.
      _x = constrain(0, 1, -1)
