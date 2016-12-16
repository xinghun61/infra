# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from crash.loglinear import feature
import libs.math.logarithms as lmath

_MAXIMUM = 50.


class ChangelistFeatureTest(unittest.TestCase):

  def testLinearlyScaledIsZero(self):
    """Test that ``LinearlyScaled`` takes 0 to 1."""
    self.assertEqual(1., feature.LinearlyScaled(0., _MAXIMUM))

  def testLinearlyScaledMiddling(self):
    """Test that ``LinearlyScaled`` takes middling values to middling values."""
    self.assertEqual((_MAXIMUM - 42.) / _MAXIMUM,
        feature.LinearlyScaled(42., _MAXIMUM))

  def testLinearlyScaledIsOverMax(self):
    """Test that ``LinearlyScaled`` takes values over the max to 0."""
    self.assertEqual(0., feature.LinearlyScaled(42., 10.))

  def testLogLinearlyScaledIsZero(self):
    """Test that ``LogLinearlyScaled`` takes log(0) to log(1)."""
    self.assertEqual(lmath.LOG_ONE, feature.LogLinearlyScaled(0., _MAXIMUM))

  def testLogLinearlyScaledMiddling(self):
    """Test that ``LogLinearlyScaled`` works on middling values."""
    self.assertEqual(
        lmath.log((_MAXIMUM - 42.) / _MAXIMUM),
        feature.LogLinearlyScaled(42., _MAXIMUM))

  def testLogLinearlyScaledIsOverMax(self):
    """Test that ``LogLinearlyScaled`` takes values over the max to log(0)."""
    self.assertEqual(lmath.LOG_ZERO, feature.LogLinearlyScaled(42., 10.))
