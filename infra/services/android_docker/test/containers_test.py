# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable=unused-argument

from datetime import datetime
import collections
import docker
import mock
import requests
import unittest

from infra.services.android_docker import containers


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


class FakeClient(object):
  """Mocks the client object returned from docker's client API.

  containers.DockerClient wraps it. Mocked here to verify wrapper class
  bheaves correctly.
  """
  def __init__(self):
    self.containers = None
    self.images = FakeImageList()
    self.creds = None
    self.responsive = True

  def login(self, **kwargs):
    self.creds = (kwargs['username'], kwargs['password'])

  def ping(self):
    if self.responsive:
      return True
    else:
      raise docker.errors.APIError('omg engine not running')


class FakeImageList(object):
  def __init__(self):
    self.images = []

  def get(self, image):
    if image not in self.images:
      raise docker.errors.ImageNotFound('omg no image')
    return True

  def pull(self, image):
    self.images.append(image)


class FakeContainer(object):
  """Used to mock containers.Container"""
  def __init__(self, name, uptime=None):
    self._container = FakeContainerBackend(name)
    self.name = name
    self.uptime = uptime
    self.swarming_bot_killed = False

  def get_container_uptime(self, now):  # pylint: disable=unused-argument
    return self.uptime

  def kill_swarming_bot(self):
    self.swarming_bot_killed = True


class FakeContainerBackend(object):
  """Mocks the container objects returned from docker's client API.

  containers.Container wraps each one. Mocked here to verify the wrapper class
  behaves correctly.
  """
  def __init__(self, name):
    self.name = name
    self.was_deleted = False
    self.was_started = False
    self.was_stopped = False
    self.is_paused = False
    self.exec_outputs = []
    self.exec_inputs = []
    self.attrs = {}

  def remove(self, **kwargs):
    self.was_deleted = True

  def start(self):
    self.was_started = True

  def pause(self):
    assert not self.is_paused
    self.is_paused = True

  def unpause(self):
    assert self.is_paused
    self.is_paused = False

  def stop(self, **kwargs):
    self.was_stopped = True

  def exec_run(self, cmd, **kwargs):
    self.exec_inputs.append(cmd)
    return self.exec_outputs.pop(0)


class FakeContainerList(object):
  """Mocks the container list objects returned from docker's client API."""
  def __init__(self, containers_list):
    self._list = containers_list

  def create(self, **kwargs):
    return FakeContainerBackend(kwargs['name'])

  def list(self, filters=None, **kwargs):  # pylint: disable=unused-argument
    if filters is None:
      filters = {}
    status = filters.get('status')
    if status == 'paused':
      return [c for c in self._list if c.is_paused]
    elif status == 'running':
      return [c for c in self._list if not c.is_paused]
    else:
      return self._list

  def get(self, name):
    for c in self._list:
      if c.name == name:
        return c
    raise docker.errors.NotFound('omg container missing')


class TestContainerDescriptor(unittest.TestCase):
  def setUp(self):
    self.desc = containers.ContainerDescriptor('7')

  def test_name(self):
    self.assertEquals(self.desc.name, '7')

  @mock.patch('socket.gethostname')
  def test_hostname(self, mock_gethostname):
    mock_gethostname.return_value = 'build123-a4'
    self.assertEquals(self.desc.hostname, 'build123-a4--7')

  def test_log_started_smoke(self):
    self.desc.log_started()

  def test_shutdown_file(self):
    self.assertEqual(self.desc.shutdown_file, '/b/7.shutdown.stamp')

  def test_lock_file(self):
    self.assertEqual(self.desc.lock_file, '/var/lock/swarm_docker.7.lock')

  def test_should_create_container(self):
    self.assertTrue(self.desc.should_create_container())


class TestDockerClient(unittest.TestCase):
  def setUp(self):
    self.fake_client = FakeClient()
    self.container_names = ['5', '6']
    self.fake_client.containers = FakeContainerList(
        [FakeContainerBackend(name) for name in self.container_names])

  @mock.patch('docker.from_env')
  @mock.patch('time.sleep')
  def test_ping_success(self, mock_sleep, mock_from_env):
    self.fake_client.responsive = True
    mock_from_env.return_value = self.fake_client
    mock_sleep.return_value = None

    client = containers.DockerClient()
    self.assertTrue(client.ping())

  @mock.patch('docker.from_env')
  @mock.patch('time.sleep')
  def test_ping_fail(self, mock_sleep, mock_from_env):
    self.fake_client.responsive = False
    mock_from_env.return_value = self.fake_client
    mock_sleep.return_value = None

    client = containers.DockerClient()
    self.assertFalse(client.ping(retries=5))
    mock_sleep.assert_has_calls(
        [mock.call(1), mock.call(2), mock.call(4), mock.call(8)])

  @mock.patch('docker.from_env')
  @mock.patch('os.path.exists')
  def test_login_no_creds(self, mock_path_exists, mock_from_env):
    mock_from_env.return_value = self.fake_client
    mock_path_exists.return_value = False

    client = containers.DockerClient()
    self.assertRaises(
        OSError, client.login, 'registry_url.com', '/path/to/creds')

  @mock.patch('docker.from_env')
  @mock.patch('os.path.exists')
  def test_login(self, mock_path_exists, mock_from_env):
    mock_from_env.return_value = self.fake_client
    mock_path_exists.return_value = True

    client = containers.DockerClient()
    with mock.patch('__builtin__.open', mock.mock_open(read_data='omg creds')):
      client.login('registry_url.com', '/path/to/creds')

    self.assertTrue(client.logged_in, True)
    self.assertEquals(self.fake_client.creds[1], 'omg creds')

  @mock.patch('docker.from_env')
  def test_has_image(self, mock_from_env):
    self.fake_client.images.images.append('image1')
    mock_from_env.return_value = self.fake_client

    client = containers.DockerClient()
    self.assertTrue(client.has_image('image1'))
    self.assertFalse(client.has_image('image99'))

  @mock.patch('docker.from_env')
  def test_pull(self, mock_from_env):
    mock_from_env.return_value = self.fake_client

    client = containers.DockerClient()
    client.logged_in = True
    client.pull('image1')
    self.assertTrue('image1' in self.fake_client.images.images)

  @mock.patch('docker.from_env')
  def test_pull_not_logged_in(self, mock_from_env):
    mock_from_env.return_value = self.fake_client

    client = containers.DockerClient()
    client.logged_in = False
    self.assertRaises(Exception, client.pull, 'image1')

  @mock.patch('docker.from_env')
  def test_get_running_containers(self, mock_from_env):
    mock_from_env.return_value = self.fake_client

    running_containers = containers.DockerClient().get_running_containers()
    self.assertEqual(
        set(c.name for c in running_containers), set(self.container_names))

  @mock.patch('docker.from_env')
  def test_get_paused_containers(self, mock_from_env):
    self.fake_client.containers.get('5').pause()
    mock_from_env.return_value = self.fake_client

    paused_containers = containers.DockerClient().get_paused_containers()
    self.assertEqual(len(paused_containers), 1)
    self.assertEqual(paused_containers[0].name, '5')

  @mock.patch('docker.from_env')
  def test_get_container(self, mock_from_env):
    mock_from_env.return_value = self.fake_client
    container = containers.DockerClient().get_container(
        containers.ContainerDescriptor('5'))
    self.assertEqual(container.name, '5')

  @mock.patch('docker.from_env')
  def test_get_missing_container(self, mock_from_env):
    mock_from_env.return_value = self.fake_client
    container = containers.DockerClient().get_container(
        containers.ContainerDescriptor('1'))
    self.assertEqual(container, None)

  @mock.patch('docker.from_env')
  def test_stop_old_containers(self, mock_from_env):
    young_container = FakeContainer('young_container', uptime=10)
    old_container = FakeContainer('old_container', uptime=999)
    mock_from_env.return_value = self.fake_client

    containers.DockerClient().stop_old_containers(
        [young_container, old_container], 100)
    self.assertFalse(young_container.swarming_bot_killed)
    self.assertTrue(old_container.swarming_bot_killed)

  @mock.patch('docker.from_env')
  def test_stop_frozen_containers(self, mock_from_env):
    def _raise_frozen_container(*args, **kwargs):
      raise containers.FrozenContainerError()
    frozen_container1 = FakeContainer('frozen_container1', uptime=999)
    frozen_container1.kill_swarming_bot = _raise_frozen_container
    frozen_container2 = FakeContainer('frozen_container2', uptime=999)
    frozen_container2.kill_swarming_bot = _raise_frozen_container
    mock_from_env.return_value = self.fake_client

    with self.assertRaises(containers.FrozenEngineError):
      containers.DockerClient().stop_old_containers(
          [frozen_container1, frozen_container2], 100)

  @mock.patch('docker.from_env')
  def test_delete_stopped_containers(self, mock_from_env):
    mock_from_env.return_value = self.fake_client

    containers.DockerClient().delete_stopped_containers()
    self.assertTrue(
        all(c.was_deleted for c in self.fake_client.containers.list()))

  @mock.patch('os.chown')
  @mock.patch('os.mkdir')
  @mock.patch('os.path.exists')
  @mock.patch('pwd.getpwnam')
  @mock.patch('docker.from_env')
  def test_create_container(self, mock_from_env, mock_getpwnam, mock_exists,
                            mock_mkdir, mock_chown):
    mock_getpwnam.return_value = collections.namedtuple(
        'pwnam', 'pw_uid, pw_gid')(1,2)
    mock_exists.return_value = False
    running_containers = [
        FakeContainer('android_serial1'),
        FakeContainer('android_serial2'),
    ]
    self.fake_client.containers = FakeContainerList(running_containers)
    mock_from_env.return_value = self.fake_client

    container = containers.DockerClient().create_container(
        containers.ContainerDescriptor('1'), 'image', 'swarm-url.com', {})
    self.assertEquals(container.name, '1')
    mock_chown.assert_called_with(mock_mkdir.call_args[0][0], 1, 2)


class TestContainer(unittest.TestCase):
  def setUp(self):
    self.container_backend = FakeContainerBackend('container1')
    self.container = containers.Container(self.container_backend)

  def test_get_labels(self):
    self.container_backend.attrs = {'Config': {'Labels': {'label1': 'val1'}}}
    self.assertEquals(self.container.labels, {'label1': 'val1'})

  def test_get_state(self):
    self.container_backend.attrs = {'State': {'Status': 'running'}}
    status = self.container.state
    self.assertEquals(status, 'running')

  def test_get_container_uptime(self):
    now = datetime.strptime(
        '2000-01-01T01:30:00.000000', '%Y-%m-%dT%H:%M:%S.%f')
    self.container_backend.attrs = {
        'State': {'StartedAt': '2000-01-01T00:00:00.0000000000'}
    }
    uptime = self.container.get_container_uptime(now)
    self.assertEquals(uptime, 90)

  def test_get_swarming_bot_pid(self):
    self.container_backend.exec_outputs = ['123']
    pid = self.container.get_swarming_bot_pid()
    self.assertEquals(pid, 123)

  def test_get_swarming_bot_pid_backend_error(self):
    self.container_backend.exec_outputs = ['rpc error: omg failure']
    pid = self.container.get_swarming_bot_pid()
    self.assertEquals(pid, None)

  def test_get_swarming_bot_pid_lsof_error(self):
    self.container_backend.exec_outputs = ['omg lsof failure']
    pid = self.container.get_swarming_bot_pid()
    self.assertEquals(pid, None)

  def test_get_swarming_bot_pid_404_error(self):
    def _raises_docker_not_found(*args, **kwargs):
      raise docker.errors.NotFound('404')
    self.container_backend.exec_run = _raises_docker_not_found
    pid = self.container.get_swarming_bot_pid()
    self.assertEquals(pid, None)

  def test_kill_swarming_bot(self):
    self.container_backend.exec_outputs = ['123', '']
    self.container.kill_swarming_bot()
    self.assertEquals(self.container_backend.exec_inputs[-1], 'kill -15 123')

  def test_kill_swarming_bot_error(self):
    self.container_backend.exec_outputs = ['omg failure']
    self.container.kill_swarming_bot()
    # Ensure nothing was killed when the bot's pid couldn't be found.
    self.assertFalse(
        any('kill -15' in cmd for cmd in self.container_backend.exec_inputs))
    self.assertTrue(self.container_backend.was_stopped)

  def test_kill_swarming_bot_cant_kill(self):
    def _raise_requests_timeout(**kwargs):
      raise requests.exceptions.ReadTimeout()
    self.container_backend.exec_outputs = ['omg failure']
    self.container_backend.stop = _raise_requests_timeout
    self.container.kill_swarming_bot()
    # Ensure nothing was killed when the bot's pid couldn't be found.
    self.assertFalse(
        any('kill -15' in cmd for cmd in self.container_backend.exec_inputs))
    self.assertFalse(self.container_backend.was_stopped)
    self.assertTrue(self.container_backend.was_deleted)

  def test_kill_swarming_bot_cant_remove(self):
    def _raise_requests_timeout(**kwargs):
      raise requests.exceptions.ReadTimeout()
    def _raise_docker_api_error(**kwargs):
      raise docker.errors.APIError('omg error')
    self.container_backend.exec_outputs = ['omg failure']
    self.container_backend.stop = _raise_requests_timeout
    self.container_backend.remove = _raise_docker_api_error
    with self.assertRaises(containers.FrozenContainerError):
      self.container.kill_swarming_bot()
    # Ensure nothing was killed when the bot's pid couldn't be found.
    self.assertFalse(
        any('kill -15' in cmd for cmd in self.container_backend.exec_inputs))
    self.assertFalse(self.container_backend.was_stopped)
    self.assertFalse(self.container_backend.was_deleted)

  def test_pause_unpause(self):
    self.container.pause()
    self.assertTrue(self.container_backend.is_paused)
    self.container.unpause()
    self.assertFalse(self.container_backend.is_paused)

  def test_exec_run(self):
    self.container_backend.exec_outputs = ['', '']
    self.container.exec_run('ls')
    self.container.exec_run('cd')
    self.assertEquals(self.container_backend.exec_inputs, ['ls', 'cd'])

  def test_attrs(self):
    self.container_backend.attrs = {'Id': '123'}
    self.assertEquals(self.container.attrs['Id'], '123')


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
  @mock.patch.object(containers.DockerClient, 'create_container')
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

  @mock.patch.object(containers, '_DOCKER_VOLUMES', {})
  def test_get_volumes(self):
    client = containers.AndroidDockerClient()
    volumes = client._get_volumes('/b/android_serial3')
    self.assertEquals(volumes.get('/opt/infra-android'),
                      {'bind': '/opt/infra-android', 'mode': 'ro'})

  def test_get_env(self):
    env = containers.AndroidDockerClient()._get_env('')
    self.assertEquals(env.get('ADB_LIBUSB'), '0')


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
        return_value=containers.Container(self.container_backend)).start()
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
