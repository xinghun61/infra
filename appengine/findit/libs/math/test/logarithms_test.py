# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import libs.math.logarithms as lmath

INFINITY = float('inf')


class LogarithmsTest(unittest.TestCase):

  def testLogZero(self):
    """Test that ``lmath.log(0)`` doesn't throw an exception."""
    self.assertEqual(-INFINITY, lmath.log(0.))

  def testLogsumexpEmpty(self):
    """The empty sum is zero, log of zero is negative infinity."""
    self.assertEqual(-INFINITY, lmath.logsumexp([]))

  def testLogsumexpInfinite(self):
    """If any summand is infinite, the whole thing is infinite."""
    self.assertEqual(INFINITY, lmath.logsumexp([INFINITY]))
    self.assertEqual(INFINITY, lmath.logsumexp([INFINITY, -INFINITY]))
    self.assertEqual(INFINITY, lmath.logsumexp([0, 1, 2, INFINITY, 9, 8, 7]))

  def testLogsumexpCommutative(self):
    """Check that ``log(x+y) == log(y+x)`` as it should."""
    # N.B., we must choose these two values carefully, to ensure we
    # don't trivially pass the test.
    xs = [0.1, 0.3]
    ys = xs[::-1]
    self.assertEqual(lmath.logsumexp(xs), lmath.logsumexp(ys))
