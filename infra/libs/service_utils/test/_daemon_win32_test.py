# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import unittest

from infra.libs.service_utils import daemon


class TestFlock(unittest.TestCase):  # pragma: no cover
  @unittest.skipIf(sys.platform != 'win32', 'Requires windows')
  def setUp(self):
    super(TestFlock, self).setUp()

  def testAlreadyLocked(self):
    with daemon.flock('foo'):
      # Locking foo again should fail.
      with self.assertRaises(daemon.LockAlreadyLocked):
        with daemon.flock('foo'):
          pass

      # Locking another file should succeed.
      with daemon.flock('bar'):
        pass

    # Locking foo now it's been unlocked should succeed.
    with daemon.flock('foo'):
      pass
