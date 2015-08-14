# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import unittest

from testing_support import auto_stub
from infra.libs.service_utils import daemon



class TestTimeout(auto_stub.TestCase):
  @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires linux')
  def setUp(self):  # pragma: no cover
    super(TestTimeout, self).setUp()

  def testAddTimeout(self):  # pragma: no cover
    self.assertEqual(
        ['timeout', '600', 'echo', 'hey'],
        daemon.add_timeout(['echo', 'hey'], 600))
