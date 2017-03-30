# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from analysis import crash_analyzer


class AnalyzeCrashTest(unittest.TestCase):
  def testAnalyzeCrash(self):
    self.assertEqual(0, crash_analyzer.Analyze('a crash'))
