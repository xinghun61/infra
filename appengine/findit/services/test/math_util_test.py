# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.float_range import FloatRange
from services import math_util
from waterfall.test.wf_testcase import WaterfallTestCase


class MathUtilTest(WaterfallTestCase):

  def testCalculateOverlapInIntervals(self):
    self.assertAlmostEqual(
        1.0,  # Both intervals cover the same point.
        math_util.CalculateOverlapInIntervals(
            FloatRange(lower=0.0, upper=0.0), FloatRange(lower=0.0, upper=0.0)))
    self.assertAlmostEqual(
        0.0,  # Interval 2 is far to the right of interval 1.
        math_util.CalculateOverlapInIntervals(
            FloatRange(lower=0.0, upper=0.0), FloatRange(lower=0.1, upper=0.9)))
    self.assertAlmostEqual(
        0.0,  # Interval 2 is far to the left of interval 1.
        math_util.CalculateOverlapInIntervals(
            FloatRange(lower=1.0, upper=2.0), FloatRange(lower=0.1, upper=0.9)))
    self.assertAlmostEqual(
        1.0,  # Intervals just touch.
        math_util.CalculateOverlapInIntervals(
            FloatRange(lower=0.0, upper=1.0), FloatRange(lower=0.0, upper=0.0)))
    self.assertAlmostEqual(
        1.0,  # Interval 1 spans interval 2.
        math_util.CalculateOverlapInIntervals(
            FloatRange(lower=0.0, upper=1.0), FloatRange(lower=0.4, upper=0.5)))
    self.assertAlmostEqual(
        1.0,  # Interval 2 spans interval 1.
        math_util.CalculateOverlapInIntervals(
            FloatRange(lower=0.0, upper=1.0), FloatRange(lower=0.0, upper=2.0)))
    self.assertAlmostEqual(
        0.8,  # Interval 1 overlaps 80% of interval 2.
        math_util.CalculateOverlapInIntervals(
            FloatRange(lower=0.9, upper=0.99), FloatRange(
                lower=0.95, upper=1.0)))
    self.assertAlmostEqual(
        0.8,  # Interval 2 overlaps 80% of interval 1.
        math_util.CalculateOverlapInIntervals(
            FloatRange(lower=0.95, upper=1.0), FloatRange(
                lower=0.9, upper=0.99)))
