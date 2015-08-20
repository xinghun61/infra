# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra_libs.ts_mon import standard_metrics


class StandardMetricsTest(unittest.TestCase):

  def setUp(self):
    standard_metrics.up.reset()

  def test_up(self):
    standard_metrics.init()
    self.assertTrue(standard_metrics.up.get())
