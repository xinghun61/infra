# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from infra.services.android_docker import __main__ as main
from infra.services.swarm_docker import containers
from infra.services.swarm_docker.test import containers_test

class MainTests(unittest.TestCase):
  def setUp(self):
    # 1000 GB disk
    self.disk = mock.MagicMock()
    self.disk.f_bsize = 4096
    self.disk.f_blocks = (1000 * 1024 * 1024 * 1024) / self.disk.f_bsize

    # 123.25 TB disk
    self.big_disk = mock.MagicMock()
    self.big_disk.f_bsize = 4096
    self.big_disk.f_blocks = 123.25 * 1024 * 1024 * 256

  @mock.patch('os.statvfs')
  def test_disk_partitioning_no_devices(self, mock_stat):
    mock_stat.return_value = self.disk
    devices = []

    cache_size = main.get_disk_partition_size('some_path', devices, .8)

    # 114 GB < (1000 GB * 0.8) / 7 < 115 GB
    self.assertGreater(cache_size, 114 * 1024 * 1024 * 1024)
    self.assertLess(cache_size, 115 * 1024 * 1024 * 1024)
    self.assertEqual(cache_size % self.disk.f_bsize, 0)

  @mock.patch('os.statvfs')
  def test_disk_partitioning_many_devices(self, mock_stat):
    mock_stat.return_value = self.disk
    devices = ['device%d' % i for i in range(1, 18)]

    cache_size = main.get_disk_partition_size('some_path', devices, .8)

    # 47 GB < (1000 GB * 0.8) / 17 < 48 GB
    self.assertGreater(cache_size, 47 * 1024 * 1024 * 1024)
    self.assertLess(cache_size, 48 * 1024 * 1024 * 1024)
    self.assertEqual(cache_size % self.disk.f_bsize, 0)

  @mock.patch('os.statvfs')
  def test_disk_partitioning_big_disk(self, mock_stat):
    mock_stat.return_value = self.big_disk
    devices = []

    cache_size = main.get_disk_partition_size('some_path', devices, .8)

    # 14 TB < (123.25 TB * 0.8) / 7 < 15 TB
    self.assertGreater(cache_size, 14 * 1024 * 1024 * 1024 * 1024)
    self.assertLess(cache_size, 15 * 1024 * 1024 * 1024 * 1024)
    self.assertEqual(cache_size % self.disk.f_bsize, 0)

  @mock.patch('os.statvfs')
  def test_disk_partitioning_10gb_fallback(self, mock_stat):
    mock_stat.return_value = self.disk
    devices = []

    cache_size = main.get_disk_partition_size('some_path', devices, .01)

    # (1000 GB * 0.001) / 7 < 10 GB, so 10 GB fallback should be returned
    self.assertEqual(cache_size, 10 * 1024 * 1024 * 1024)


class LaunchTests(unittest.TestCase):

  def setUp(self):
    self.c1_backend = containers_test.FakeContainerBackend('c1')
    self.c2_backend = containers_test.FakeContainerBackend('c2')
    self.c1 = containers.Container(self.c1_backend)
    self.c2 = containers.Container(self.c2_backend)

    self.fake_client = containers_test.FakeClient()
    self.fake_client.get_running_containers = mock.MagicMock(
        return_value=[self.c1, self.c2])
    self.fake_client.get_created_containers = mock.MagicMock(return_value=[])

  @mock.patch('infra.services.swarm_docker.main_helpers.launch_containers')
  def test_noop(self, mock_launch_containers):
    # All healthy containers should cause launch() to do nothing but go straight
    # to main_helpers.launch_containers().
    main.launch(self.fake_client, [], None)

    mock_launch_containers.ensure_called_once()

  @mock.patch('infra.services.swarm_docker.main_helpers.reboot_host')
  @mock.patch('infra.services.swarm_docker.main_helpers.launch_containers')
  @mock.patch('infra.services.swarm_docker.main_helpers.get_host_uptime')
  def test_no_devices_no_reboot(self, mock_get_uptime, mock_launch_containers,
                                mock_reboot):
    # No running containers, but a small host uptime.
    mock_get_uptime.return_value = 1
    self.fake_client.get_running_containers.return_value = []

    main.launch(self.fake_client, [], None)

    # main_helpers.launch_containers() should be called without a reboot.
    self.assertEqual(mock_launch_containers.call_count, 1)
    self.assertEqual(mock_reboot.call_count, 0)

  @mock.patch('infra.services.swarm_docker.main_helpers.reboot_host')
  @mock.patch('infra.services.swarm_docker.main_helpers.launch_containers')
  @mock.patch('infra.services.swarm_docker.main_helpers.get_host_uptime')
  def test_no_devices_with_reboot(self, mock_get_uptime, mock_launch_containers,
                                  mock_reboot):
    # No running containers, and a large host uptime.
    mock_args = mock.MagicMock()
    mock_args.canary = False
    mock_get_uptime.return_value = 999
    self.fake_client.get_running_containers.return_value = []

    main.launch(self.fake_client, [], mock_args)

    # A reboot should be called instead of main_helpers.launch_containers().
    self.assertEqual(mock_launch_containers.call_count, 0)
    self.assertEqual(mock_reboot.call_count, 1)
