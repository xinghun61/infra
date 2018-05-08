# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs import floating_point_util
from waterfall.test import wf_testcase


class FloatingPointUtilTest(wf_testcase.WaterfallTestCase):

  def testAlmostEquals(self):
    self.assertTrue(floating_point_util.AlmostEquals(1.0, 1.0))
    self.assertTrue(floating_point_util.AlmostEquals(0, 0))
    self.assertTrue(floating_point_util.AlmostEquals(-1, -1))
    self.assertTrue(floating_point_util.AlmostEquals(0.9999999999, 1.0))
    self.assertTrue(floating_point_util.AlmostEquals(9999999, 10000000))
    self.assertTrue(floating_point_util.AlmostEquals(-9999999, -10000000))
    self.assertFalse(floating_point_util.AlmostEquals(0.999, 1.0))
    self.assertFalse(floating_point_util.AlmostEquals(999, 1000))
    self.assertFalse(floating_point_util.AlmostEquals(9999999, -10000000))
