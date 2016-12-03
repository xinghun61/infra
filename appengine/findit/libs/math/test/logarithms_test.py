# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.math.logarithms import logsumexp


INFINITY = float('inf')


class LogarithmsTest(unittest.TestCase):

  def testLogsumexpEmpty(self):
    """The empty sum is zero, log of zero is negative infinity."""
    self.assertEqual(-INFINITY, logsumexp([]))

  def testLogsumexpInfinite(self):
    """If any summand is infinite, the whole thing is infinite."""
    self.assertEqual(INFINITY, logsumexp([INFINITY]))
    self.assertEqual(INFINITY, logsumexp([INFINITY, -INFINITY]))
    self.assertEqual(INFINITY, logsumexp([0, 1, 2, INFINITY, 9, 8, 7]))

  def testLogsumexpCommutative(self):
    """Check that ``log(x+y) == log(y+x)`` as it should."""
    # N.B., we must choose these two values carefully, to ensure we
    # don't trivially pass the test.
    xs = [0.1, 0.3]
    ys = xs[::-1]
    self.assertEqual(logsumexp(xs), logsumexp(ys))
