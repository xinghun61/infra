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

    self.assertGreater(system_metrics.cpu_count.get(), 0)

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

    interface_names = [fields[0][1]
                       for fields, _
                       in system_metrics.net_up.get_all()]
    self.assertGreater(len(interface_names), 0)

    # A network interface that should always be present.
    if sys.platform == 'win32':  # pragma: no cover
      self.assertTrue(
          any(x.startswith('Local Area Connection') for x in interface_names),
          interface_names)
    elif sys.platform == 'darwin':  # pragma: no cover
      self.assertTrue(
          any(x.startswith('en') for x in interface_names),
          interface_names)
    else:  # pragma: no cover
      self.assertIn('lo', interface_names)

    labels = {'interface': interface_names[0]}

    self.assertIsNotNone(system_metrics.net_up.get(labels))
    self.assertIsNotNone(system_metrics.net_down.get(labels))
    self.assertIsNotNone(system_metrics.net_err_up.get(labels))
    self.assertIsNotNone(system_metrics.net_err_down.get(labels))
    self.assertIsNotNone(system_metrics.net_drop_up.get(labels))
    self.assertIsNotNone(system_metrics.net_drop_down.get(labels))

  def test_proc_info(self):
    system_metrics.get_proc_info()

    self.assertGreater(system_metrics.proc_count.get(), 10)

    if os.name == 'posix':  # pragma: no cover
      self.assertGreater(
          system_metrics.load_average.get(fields={'minutes': 1}), 0)
      self.assertGreater(
          system_metrics.load_average.get(fields={'minutes': 5}), 0)
      self.assertGreater(
          system_metrics.load_average.get(fields={'minutes': 15}), 0)

  def test_get_unix_time(self):
    system_metrics.get_unix_time()
    self.assertTrue(
      1464000000000 < system_metrics.unix_time.get() < 9464000000000)

  # this first patch doesn't need to be an arg
  @mock.patch('sys.maxsize', 9223372036854775807)
  # NB: remaining patches must be in reverse order of arguments
  @mock.patch('platform.machine')
  @mock.patch('platform.mac_ver')
  @mock.patch('platform.system')
  def test_os_info_mac_10115_64_64(self,
                                   platform_system_mock,
                                   platform_mac_ver_mock,
                                   platform_machine_mock):
    platform_system_mock.return_value = 'Darwin'
    platform_mac_ver_mock.return_value = ('10.11.5', ('', '', ''), 'x86_64')
    platform_machine_mock.return_value = 'x86_64'

    system_metrics.get_os_info()

    platform_system_mock.assert_called_once_with()
    platform_mac_ver_mock.assert_called_once_with()
    platform_machine_mock.assert_called_once_with()

    self.assertEqual('mac', system_metrics.os_name.get(fields={'hostname': ''}))
    self.assertEqual('10.11.5',
                     system_metrics.os_version.get(fields={'hostname': ''}))
    self.assertEqual('x86_64', system_metrics.os_arch.get())
    self.assertEqual('64', system_metrics.python_arch.get())

  # this first patch doesn't need to be an arg
  @mock.patch('sys.maxsize', 9223372036854775807)
  # NB: remaining patches must be in reverse order of arguments
  @mock.patch('platform.machine')
  @mock.patch('platform.mac_ver')
  @mock.patch('platform.system')
  def test_os_info_empty_info(self,
                                   platform_system_mock,
                                   platform_mac_ver_mock,
                                   platform_machine_mock):
    # this test is to hit the 'impossible' else case for a system
    # this is to check that the fallback/error handling code behaves

    platform_system_mock.return_value = ''
    platform_mac_ver_mock.return_value = ('', ('', '', ''), '')
    platform_machine_mock.return_value = ''

    system_metrics.get_os_info()

    platform_system_mock.assert_called_once_with()
    platform_mac_ver_mock.assert_called_once_with()
    platform_machine_mock.assert_called_once_with()

    self.assertEqual('', system_metrics.os_name.get(fields={'hostname': ''}))
    self.assertEqual('', system_metrics.os_version.get(fields={'hostname': ''}))
    self.assertEqual('', system_metrics.os_arch.get())
    self.assertEqual('64', system_metrics.python_arch.get())

  # this first patch doesn't need to be an arg
  @mock.patch('sys.maxsize', 2147483647)
  # NB: remaining patches must be in reverse order of arguments
  @mock.patch('platform.machine')
  @mock.patch('platform.release')
  @mock.patch('platform.system')
  def test_os_info_clear(self,
                                   platform_system_mock,
                                   platform_release_mock,
                                   platform_machine_mock):
    platform_system_mock.return_value = 'Windows'
    platform_release_mock.return_value = '7'
    platform_machine_mock.return_value = 'x86'

    system_metrics.get_os_info()

    platform_system_mock.assert_called_once_with()
    platform_release_mock.assert_called_once_with()
    platform_machine_mock.assert_called_once_with()

    self.assertEqual('windows',
                     system_metrics.os_name.get(fields={'hostname': ''}))
    self.assertEqual('7',
                     system_metrics.os_version.get(fields={'hostname': ''}))
    self.assertEqual('x86', system_metrics.os_arch.get())
    self.assertEqual('32', system_metrics.python_arch.get())

    # test that clearing the metrics keeps them emtpy on subsequent runs
    system_metrics.clear_os_info()

    self.assertIsNone(system_metrics.os_name.get(fields={'hostname': ''}))
    self.assertIsNone(system_metrics.os_version.get(fields={'hostname': ''}))
    self.assertIsNone(system_metrics.os_arch.get())
    self.assertIsNone(system_metrics.python_arch.get())

  # this first patch doesn't need to be an arg
  @mock.patch('sys.maxsize', 2147483647)
  # NB: remaining patches must be in reverse order of arguments
  @mock.patch('platform.machine')
  @mock.patch('platform.release')
  @mock.patch('platform.system')
  def test_os_info_windows_7_32_32(self,
                                   platform_system_mock,
                                   platform_release_mock,
                                   platform_machine_mock):
    platform_system_mock.return_value = 'Windows'
    platform_release_mock.return_value = '7'
    platform_machine_mock.return_value = 'x86'

    system_metrics.get_os_info()

    platform_system_mock.assert_called_once_with()
    platform_release_mock.assert_called_once_with()
    platform_machine_mock.assert_called_once_with()

    self.assertEqual('windows',
                     system_metrics.os_name.get(fields={'hostname': ''}))
    self.assertEqual('7',
                     system_metrics.os_version.get(fields={'hostname': ''}))
    self.assertEqual('x86', system_metrics.os_arch.get())
    self.assertEqual('32', system_metrics.python_arch.get())

  # this first patch doesn't need to be an arg
  @mock.patch('sys.maxsize', 2147483647)
  # NB: remaining patches must be in reverse order of arguments
  @mock.patch('platform.machine')
  @mock.patch('platform.dist')
  @mock.patch('platform.system')
  def test_os_info_ubuntu_1404_32_32(self,
                                     platform_system_mock,
                                     platform_dist_mock,
                                     platform_machine_mock):
    platform_system_mock.return_value = 'Linux'
    platform_dist_mock.return_value = ('Ubuntu', '14.04', 'trusty')
    platform_machine_mock.return_value = 'i686'

    system_metrics.get_os_info()

    platform_system_mock.assert_called_once_with()
    platform_dist_mock.assert_called_once_with()
    platform_machine_mock.assert_called_once_with()

    self.assertEqual('ubuntu',
                     system_metrics.os_name.get(fields={'hostname': ''}))
    self.assertEqual('14.04',
                     system_metrics.os_version.get(fields={'hostname': ''}))
    self.assertEqual('i686', system_metrics.os_arch.get())
    self.assertEqual('32', system_metrics.python_arch.get())

  # this first patch doesn't need to be an arg
  @mock.patch('sys.maxsize', 2147483647)
  # NB: remaining patches must be in reverse order of arguments
  @mock.patch('platform.machine')
  @mock.patch('platform.dist')
  @mock.patch('platform.system')
  def test_os_info_ubuntu_1404_64_32(self,
                                     platform_system_mock,
                                     platform_dist_mock,
                                     platform_machine_mock):
    platform_system_mock.return_value = 'Linux'
    platform_dist_mock.return_value = ('Ubuntu', '14.04', 'trusty')
    platform_machine_mock.return_value = 'x86_64'

    system_metrics.get_os_info()

    platform_system_mock.assert_called_once_with()
    platform_dist_mock.assert_called_once_with()
    platform_machine_mock.assert_called_once_with()

    self.assertEqual('ubuntu',
                     system_metrics.os_name.get(fields={'hostname': ''}))
    self.assertEqual('14.04',
                     system_metrics.os_version.get(fields={'hostname': ''}))
    self.assertEqual('x86_64', system_metrics.os_arch.get())
    self.assertEqual('32', system_metrics.python_arch.get())

  # this first patch doesn't need to be an arg
  @mock.patch('sys.maxsize', 9223372036854775807)
  # NB: remaining patches must be in reverse order of arguments
  @mock.patch('platform.machine')
  @mock.patch('platform.dist')
  @mock.patch('platform.system')
  def test_os_info_ubuntu_1404_64_64(self,
                                     platform_system_mock,
                                     platform_dist_mock,
                                     platform_machine_mock):
    platform_system_mock.return_value = 'Linux'
    platform_dist_mock.return_value = ('Ubuntu', '14.04', 'trusty')
    platform_machine_mock.return_value = 'x86_64'

    system_metrics.get_os_info()

    platform_system_mock.assert_called_once_with()
    platform_dist_mock.assert_called_once_with()
    platform_machine_mock.assert_called_once_with()

    self.assertEqual('ubuntu',
                     system_metrics.os_name.get(fields={'hostname': ''}))
    self.assertEqual('14.04',
                     system_metrics.os_version.get(fields={'hostname': ''}))
    self.assertEqual('x86_64', system_metrics.os_arch.get())
    self.assertEqual('64', system_metrics.python_arch.get())


