# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra.tools.antibody import compute_stats


class TestComputeStats(unittest.TestCase):
  def test_ratio_calculator(self):
    reg_num = [['2014-01', 1], ['2014-02', 3], ['2014-07', 5]]
    reg_den = [['2014-07', 10], ['2014-02', 6], ['2014-01', 9]]
    reg_ratio = compute_stats.ratio_calculator(reg_num, reg_den)
    self.assertEqual(reg_ratio,
                     [['2014-01', 0.111], ['2014-02', 0.5], ['2014-07', 0.5]])

    zero_num = [['2014-01', 1], ['2014-02', 0], ['2014-07', 5]]
    zero_den = [['2014-07', 10], ['2014-02', 0], ['2014-01', 0]]
    zero_ratio = compute_stats.ratio_calculator(zero_num, zero_den)
    self.assertEqual(zero_ratio,
                     [['2014-01', 0], ['2014-02', 0], ['2014-07', 0.5]])

    missing_num = [['2014-01', 1], ['2014-02', 3], ['2014-07', 5]]
    missing_den = [['2014-02', 3], ['2014-07', 10]]
    missing_ratio = compute_stats.ratio_calculator(missing_num, missing_den)
    self.assertEqual(missing_ratio,
                     [['2014-02', 1.0], ['2014-07', 0.5]])

    extra_num = [['2014-01', 1], ['2014-02', 3], ['2014-07', 5]]
    extra_den = [['2014-02', 3], ['2015-07', 5], ['2015-07', 5]]
    extra_ratio = compute_stats.ratio_calculator(extra_num, extra_den)
    self.assertEqual(extra_ratio, [['2014-02', 1.0]])

  def test_totaled_ratio_calculator(self):
    ratio = compute_stats.totaled_ratio_calculator(3, 7)
    self.assertEqual(ratio, 0.429)
    self.assertRaises(ZeroDivisionError,
        compute_stats.totaled_ratio_calculator, 5, 0)