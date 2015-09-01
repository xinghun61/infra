# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import os
import sys
import time
import unittest

from infra.services.sysmon import system_metrics


class SystemMetricsTest(unittest.TestCase):
  def setUp(self):
    system_metrics.reset_metrics_for_unittest()

  def assertBetween(self, lower, upper, value):
    self.assertGreaterEqual(value, lower)
    self.assertLessEqual(value, upper)

  def test_cpu_info(self):
    system_metrics.get_cpu_info()

    user = system_metrics.cpu_time.get({'mode': 'user'})
    system = system_metrics.cpu_time.get({'mode': 'system'})
    idle = system_metrics.cpu_time.get({'mode': 'idle'})

    self.assertIsNotNone(user)
    self.assertIsNotNone(system)
    self.assertIsNotNone(idle)
    self.assertBetween(0, 100, user)
    self.assertBetween(0, 100, system)
    self.assertBetween(0, 100, idle)

  def test_disk_info(self):
    system_metrics.get_disk_info()

    # A disk mountpoint that should always be present.
    path = 'C:\\' if sys.platform == 'win32' else '/'

    free = system_metrics.disk_free.get({'path': path})
    total = system_metrics.disk_total.get({'path': path})

    self.assertIsNotNone(free)
    self.assertIsNotNone(total)
    self.assertLessEqual(free, total)

    if os.name == 'posix':  # pragma: no cover
      inodes_free = system_metrics.inodes_free.get({'path': '/'})
      inodes_total = system_metrics.inodes_total.get({'path': '/'})

      self.assertIsNotNone(inodes_free)
      self.assertIsNotNone(inodes_total)
      self.assertLessEqual(inodes_free, inodes_total)

  def test_disk_info_removable(self):
    path = '/does/not/exist'

    system_metrics.get_disk_info(mountpoints=[path])

    self.assertIs(None, system_metrics.disk_free.get({'path': path}))
    self.assertIs(None, system_metrics.disk_total.get({'path': path}))

  def test_mem_info(self):
    system_metrics.get_mem_info()

    free = system_metrics.mem_free.get()
    total = system_metrics.mem_total.get()

    self.assertIsNotNone(free)
    self.assertIsNotNone(total)
    self.assertLessEqual(free, total)

  def test_net_info(self):
    system_metrics.get_net_info()

    # A network interface that should always be present.
    if sys.platform == 'win32':  # pragma: no cover
      interface = 'Local Area Connection'
    elif sys.platform == 'darwin':  # pragma: no cover
      interface = 'en0'
    else:  # pragma: no cover
      interface = 'lo'

    up = system_metrics.net_up.get({'interface': interface})
    down = system_metrics.net_down.get({'interface': interface})

    self.assertIsNotNone(up)
    self.assertIsNotNone(down)

  def test_proc_info(self):
    system_metrics.get_proc_info()

    self.assertGreater(system_metrics.proc_count.get(), 10)
