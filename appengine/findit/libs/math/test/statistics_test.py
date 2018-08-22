# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from libs.math import statistics
from waterfall.test.wf_testcase import WaterfallTestCase


class StatisticsTest(WaterfallTestCase):

  def testGetZFromAlpha(self):
    self.assertAlmostEqual(1.2815515655446004, statistics._GetZFromAlpha(0.1))
    self.assertAlmostEqual(1.2815515655446004, statistics._GetZFromAlpha(.12))

  def testWilsonScoreConfidenceInterval(self):
    interval = statistics.WilsonScoreConfidenceInterval(1.0, 100, 0.001)
    self.assertAlmostEqual(0.9128290627200445, interval.lower)
    self.assertAlmostEqual(1.0, interval.upper)
