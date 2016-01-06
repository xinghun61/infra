# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import os
import sys
import unittest

import mock

from infra.services.sysmon import system_metrics
from infra_libs import ts_mon


class SystemMetricsTest(unittest.TestCase):
  def setUp(self):
    ts_mon.reset_for_unittest()

  def assertBetween(self, lower, upper, value):
    self.assertGreaterEqual(value, lower)
    self.assertLessEqual(value, upper)

  def test_uptime(self):
    system_metrics.get_uptime()
    uptime = system_metrics.uptime.get()
    self.assertIsNotNone(uptime)
    self.assertGreater(uptime, 0)

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

  @mock.patch('psutil.disk_io_counters')
  def test_disk_counters(self, mock_counters):
    iostat = collections.namedtuple('iostat', ['read_bytes', 'write_bytes'])
    mock_counters.return_value = {'sda': iostat(123, 456)}

    system_metrics.get_disk_info()

    self.assertTrue(mock_counters.called)
    self.assertEqual(123, system_metrics.disk_read.get({'disk': 'sda'}))
    self.assertEqual(456, system_metrics.disk_write.get({'disk': 'sda'}))

  @mock.patch('psutil.disk_io_counters')
  def test_disk_counters_no_disks(self, mock_counters):
    mock_counters.side_effect = RuntimeError("couldn't find any physical disk")

    # Should swallow the exception.
    system_metrics.get_disk_info()

    self.assertTrue(mock_counters.called)
    self.assertIs(None, system_metrics.disk_read.get({'disk': 'sda'}))
    self.assertIs(None, system_metrics.disk_write.get({'disk': 'sda'}))

  @mock.patch('psutil.disk_io_counters')
  def test_disk_counters_other_exception(self, mock_counters):
    mock_counters.side_effect = RuntimeError('different message')

    with self.assertRaises(RuntimeError):
      system_metrics.get_disk_info()

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

    labels = {'interface': interface}

    self.assertIsNotNone(system_metrics.net_up.get(labels))
    self.assertIsNotNone(system_metrics.net_down.get(labels))
    self.assertIsNotNone(system_metrics.net_err_up.get(labels))
    self.assertIsNotNone(system_metrics.net_err_down.get(labels))
    self.assertIsNotNone(system_metrics.net_drop_up.get(labels))
    self.assertIsNotNone(system_metrics.net_drop_down.get(labels))

  def test_proc_info(self):
    system_metrics.get_proc_info()

    self.assertGreater(system_metrics.proc_count.get(), 10)
