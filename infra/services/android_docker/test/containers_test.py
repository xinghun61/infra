# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable=unused-argument

import mock
import unittest

from infra.services.android_docker import containers
from infra.services.swarm_docker import containers as swarm_containers
from infra.services.swarm_docker.test.containers_test import (
    FakeContainer, FakeContainerBackend)


class FakeDevice(object):
  """Mocks a usb_device.Device"""
  def __init__(self, serial, physical_port):
    self.serial = serial
    self.physical_port = physical_port
    self.major = 0
    self.minor = 0
    self.bus = 0
    self.dev_file_path = ''
    self.battor = None


class FakeBattor(object):
  def __init__(self, tty_path, serial):
    self.tty_path = tty_path
    self.serial = serial
    self.major = 0
    self.minor = 0
    self.syspath = ''


class TestAndroidContainerDescriptor(unittest.TestCase):
  def setUp(self):
    self.desc = containers.AndroidContainerDescriptor(
        FakeDevice('serial123', 1))

  def test_name(self):
    self.assertEquals(self.desc.name, 'android_serial123')

  @mock.patch('socket.gethostname')
  def test_hostname_with_port(self, mock_gethostname):
    mock_gethostname.return_value = 'build123-a4'
    self.assertEquals(self.desc.hostname, 'build123-a4--device1')

  @mock.patch('socket.gethostname')
  def test_hostname_with_serial(self, mock_gethostname):
    mock_gethostname.return_value = 'build123-a4'
    self.desc.device.physical_port = None
    self.assertEquals(self.desc.hostname, 'build123-a4--serial123')

  def test_log_started_smoke(self):
    containers.AndroidContainerDescriptor(
        FakeDevice('serial123', 1)).log_started()

  def test_shutdown_file(self):
    self.assertEqual(self.desc.shutdown_file, '/b/serial123.shutdown.stamp')

  def test_lock_file(self):
    self.assertEqual(
        self.desc.lock_file, '/var/lock/android_docker.serial123.lock')

  def test_should_create_container(self):
    self.assertTrue(self.desc.should_create_container())
    self.desc.device.physical_port = None
    self.assertFalse(self.desc.should_create_container())


class TestAndroidDockerClient(unittest.TestCase):
  @mock.patch.object(swarm_containers.DockerClient, 'create_container')
  @mock.patch.object(containers.AndroidDockerClient, 'add_device')
  def test_create_container(self, mock_add_device, mock_create_container):
    fake_container = FakeContainer('android_serial3')
    mock_create_container.return_value = fake_container
    device = FakeDevice('serial3', 3)
    desc = containers.AndroidContainerDescriptor(device)
    client = containers.AndroidDockerClient()
    client.create_container(desc, 'image', 'swarm-url.com', {})
    mock_create_container.assert_called_once_with(
        desc, 'image', 'swarm-url.com', {})
    mock_add_device.assert_called_once_with(desc)

  @mock.patch.object(swarm_containers, '_DOCKER_VOLUMES', {})
  def test_get_volumes(self):
    client = containers.AndroidDockerClient()
    volumes = client._get_volumes('/b/android_serial3')
    self.assertEquals(volumes.get('/opt/infra-android'),
                      {'bind': '/opt/infra-android', 'mode': 'ro'})

  def test_get_env_no_cache(self):
    env = containers.AndroidDockerClient()._get_env('')
    self.assertEquals(env.get('ADB_LIBUSB'), '0')
    self.assertFalse('ISOLATED_CACHE_SIZE' in env)

  def test_get_env_with_cache(self):
    client = containers.AndroidDockerClient()
    client.cache_size = '1234567890'
    env = client._get_env('')
    self.assertEquals(env.get('ADB_LIBUSB'), '0')
    self.assertEquals(env.get('ISOLATED_CACHE_SIZE'), '1234567890')

class TestAddDevice(unittest.TestCase):
  def setUp(self):
    self.container_backend = FakeContainerBackend('container1')
    self.container_backend.attrs = {
      'Id': 'abc123',
      'State': {'Status': 'running'},
    }
    self.client = containers.AndroidDockerClient()
    self.device = FakeDevice('serial1', 1)
    self.desc = containers.AndroidContainerDescriptor(self.device)
    mock.patch.object(
        self.client, 'get_container',
        return_value=swarm_containers.Container(self.container_backend)).start()
    self.mock_sleep = mock.patch('time.sleep', return_value=None).start()
    self.mock_path_exists = mock.patch(
        'os.path.exists', return_value=True).start()

  def tearDown(self):
    mock.patch.stopall()

  @mock.patch('os.open')
  @mock.patch('os.write')
  @mock.patch('os.close')
  def test_add_device(self, mock_close, mock_write, mock_open):
    self.container_backend.exec_outputs = ['', '']
    self.device.major = 111
    self.device.minor = 9
    self.device.bus = 1
    self.device.dev_file_path = '/dev/bus/usb/001/123'
    self.client.add_device(self.desc)

    self.assertTrue('abc123' in mock_open.call_args[0][0])
    # Ensure the device's major and minor numbers were written to the
    # cgroup file.
    self.assertEqual(mock_write.call_args[0][1], 'c 111:9 rwm')
    self.assertTrue(mock_close.called)
    self.assertFalse(self.container_backend.is_paused)

  @mock.patch('os.open')
  def test_add_device_missing_cgroup(self, mock_open):
    self.mock_path_exists.return_value = False
    self.container_backend.exec_outputs = ['']
    self.client.add_device(self.desc)

    self.assertFalse(mock_open.called)
    self.assertEquals(len(self.container_backend.exec_inputs), 1)
    self.assertFalse(self.container_backend.is_paused)

  @mock.patch('os.open')
  @mock.patch('os.write')
  @mock.patch('os.close')
  def test_add_device_os_open_error(self, mock_close, mock_write, mock_open):
    mock_open.side_effect = OSError('omg open error')
    self.container_backend.exec_outputs = ['']
    self.device.major = 111
    self.device.minor = 9
    self.client.add_device(self.desc)

    self.assertTrue('abc123' in mock_open.call_args[0][0])
    self.assertFalse(mock_write.called)
    self.assertFalse(mock_close.called)
    self.assertEquals(len(self.container_backend.exec_inputs), 1)
    self.assertFalse(self.container_backend.is_paused)

  @mock.patch('os.open')
  @mock.patch('os.write')
  @mock.patch('os.close')
  def test_add_device_os_write_error(self, mock_close,
                                     mock_write, mock_open):
    mock_write.side_effect = OSError('omg write error')
    self.container_backend.exec_outputs = ['']
    self.device.major = 111
    self.device.minor = 9
    self.client.add_device(self.desc)

    self.assertTrue('abc123' in mock_open.call_args[0][0])
    self.assertEquals(mock_write.call_args[0][1], 'c 111:9 rwm')
    self.assertTrue(mock_close.called)
    self.assertEquals(len(self.container_backend.exec_inputs), 1)
    self.assertFalse(self.container_backend.is_paused)

  @mock.patch('os.open')
  @mock.patch('os.write')
  @mock.patch('os.close')
  def test_add_device_with_battor(self, mock_close, mock_write, mock_open):
    self.container_backend.exec_outputs = ['', '', '']
    self.device.major = 111
    self.device.minor = 9
    self.device.bus = 1
    self.device.dev_file_path = '/dev/bus/usb/001/123'
    battor = FakeBattor('/dev/ttyBattor', 'battorSerial1')
    battor.major = 189
    battor.minor = 0
    battor.syspath = '/devices/usb/1/2/3/pci123/'
    self.device.battor = battor
    self.client.add_device(self.desc)

    self.assertTrue('abc123' in mock_open.call_args[0][0])
    # Ensure the device's major and minor numbers were written to the
    # cgroup file, followed by the battor's major and minor numbers.
    self.assertEqual(
        mock_write.call_args_list[0],
        mock.call(mock_open.return_value, 'c 111:9 rwm'))
    self.assertEqual(
        mock_write.call_args_list[1],
        mock.call(mock_open.return_value, 'c 189:0 rwm'))

    # Ensure the device's and battor's dev files were removed then created and
    # the battor's udevadm db entry was updated.
    self.assertEquals(self.container_backend.exec_inputs[0], 'rm -rf /dev/bus')
    self.assertEquals(
        self.container_backend.exec_inputs[1], 'rm /dev/ttyBattor')
    self.assertTrue(
        'mknod /dev/bus/usb/001/123' in self.container_backend.exec_inputs[2])
    self.assertTrue(
        'mknod /dev/ttyBattor' in self.container_backend.exec_inputs[2])
    self.assertTrue(
        'udevadm test /devices/usb/1/2/3/pci123/' in
        self.container_backend.exec_inputs[2])

    self.assertTrue(mock_close.called)
    self.assertFalse(self.container_backend.is_paused)

  def test_container_not_running(self):
    self.container_backend.attrs['State']['Status'] = 'paused'
    self.client.add_device(self.desc)
    self.assertFalse(self.mock_sleep.called)
