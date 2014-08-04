# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
from infra.tools.builder_alerts import buildbot


class BuildbotTest(unittest.TestCase):
  def test_master_name_from_url(self):
    tests = [
      ('https://build.chromium.org/p/chromium.mac', 'chromium.mac'),
      ('https://build.chromium.org/p/tryserver.blink', 'tryserver.blink')
    ]
    for master_url, master_name in tests:
      self.assertEquals(buildbot.master_name_from_url(master_url), master_name)
