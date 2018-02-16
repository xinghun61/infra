# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable=unused-argument

import mock
import unittest

from infra.services.cros_docker import containers
from infra.services.swarm_docker import containers as swarm_containers
from infra.services.swarm_docker.test import containers_test


class TestAndroidContainerDescriptor(unittest.TestCase):
  def setUp(self):
    self.desc = containers.CrosContainerDescriptor('device123', 'some_ssh_path')

  def test_name(self):
    self.assertEquals(self.desc.name, 'cros_device123')

  @mock.patch('socket.gethostname')
  def test_hostname(self, mock_gethostname):
    mock_gethostname.return_value = 'build123-a4'
    self.assertEquals(self.desc.hostname, 'build123-a4--device123')

  def test_log_started_smoke(self):
    self.desc.log_started()

  def test_shutdown_file(self):
    self.assertEqual(self.desc.shutdown_file, '/b/device123.shutdown.stamp')

  def test_lock_file(self):
    self.assertEqual(
        self.desc.lock_file, '/var/lock/cros_docker.device123.lock')

  def test_should_create_container(self):
    self.assertTrue(self.desc.should_create_container())  # lol


class TestCrosDockerClient(unittest.TestCase):
  @mock.patch.object(swarm_containers.DockerClient, 'create_container')
  def test_create_container(self, mock_create_container):
    fake_container = containers_test.FakeContainer('cros_device123')
    mock_create_container.return_value = fake_container
    desc = containers.CrosContainerDescriptor('device123', 'some_ssh_path')
    client = containers.CrosDockerClient()
    client.create_container(desc, 'image', 'swarm-url.com', {})
    expected_env = {
        'SWARMING_BOT_CROS_HOSTNAME': 'device123',
        'CROS_SSH_ID_FILE_PATH': 'some_ssh_path',
    }
    mock_create_container.assert_called_once_with(
        desc, 'image', 'swarm-url.com', {}, additional_env=expected_env)
