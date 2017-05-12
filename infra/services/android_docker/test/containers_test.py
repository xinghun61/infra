# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import docker
import mock
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
    self.is_paused = False
    self.exec_outputs = []
    self.exec_inputs = []
    self.attrs = {}

  def remove(self):
    self.was_deleted = True

  def start(self):
    self.was_started = True

  def pause(self):
    assert not self.is_paused
    self.is_paused = True

  def unpause(self):
    assert self.is_paused
    self.is_paused = False

  def exec_run(self, cmd):
    self.exec_inputs.append(cmd)
    return self.exec_outputs.pop(0)


class FakeContainerList(object):
  """Mocks the container list objects returned from docker's client API."""
  def __init__(self, containers_list):
    self._list = containers_list

  def create(self, **kwargs):
    return FakeContainerBackend(kwargs['name'])

  def list(self, **kwargs):  # pylint: disable=unused-argument
    return self._list

  def get(self, name):
    for c in self._list:
      if c.name == name:
        return c
    raise docker.errors.NotFound('omg container missing')


class TestGetNames(unittest.TestCase):
  def setUp(self):
    self.device = FakeDevice('serial123', 1)

  def test_container_name(self):
    container_name = containers.get_container_name(self.device)
    self.assertEqual(container_name, 'android_serial123')

  @mock.patch('socket.gethostname')
  def test_container_hostname_with_port(self, mock_gethostname):
    mock_gethostname.return_value = 'build123-a4'
    container_hostname = containers.get_container_hostname(self.device)
    self.assertEqual(container_hostname, 'build123-a4--device1')

  @mock.patch('socket.gethostname')
  def test_container_hostname_with_serial(self, mock_gethostname):
    mock_gethostname.return_value = 'build123-a4'
    self.device.physical_port = None
    container_hostname = containers.get_container_hostname(self.device)
    self.assertEqual(container_hostname, 'build123-a4--serial123')


class TestDockerClient(unittest.TestCase):
  def setUp(self):
    self.fake_client = FakeClient()
    self.container_names = ['android_serial1', 'android_serial2']
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
  def test_get_container(self, mock_from_env):
    mock_from_env.return_value = self.fake_client
    fake_device = FakeDevice('serial2', 2)

    container = containers.DockerClient().get_container(fake_device)
    self.assertEqual(container.name, 'android_serial2')

  @mock.patch('docker.from_env')
  def test_get_missing_container(self, mock_from_env):
    mock_from_env.return_value = self.fake_client
    fake_device = FakeDevice('missing_device', 1)

    container = containers.DockerClient().get_container(fake_device)
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
  def test_delete_stopped_containers(self, mock_from_env):
    mock_from_env.return_value = self.fake_client

    containers.DockerClient().delete_stopped_containers()
    self.assertTrue(
        all(c.was_deleted for c in self.fake_client.containers.list()))

  @mock.patch('docker.from_env')
  def test_create_missing_containers(self, mock_from_env):
    running_containers = [
        FakeContainer('android_serial1'),
        FakeContainer('android_serial2'),
    ]
    devices = [
        FakeDevice('serial1', 1),
        FakeDevice('serial2', 2),
        FakeDevice('serial3', 3),
    ]
    self.fake_client.containers = FakeContainerList(running_containers)
    mock_from_env.return_value = self.fake_client

    needs_cgroup_update = containers.DockerClient().create_missing_containers(
        running_containers, devices, 'image', 'swarm-url.com')
    # Ensure serial3 needs to be rebooted. This indicates that a new container
    # was created for it.
    self.assertEquals([d.serial for d in needs_cgroup_update], ['serial3'])


class TestContainer(unittest.TestCase):
  def setUp(self):
    self.container_backend = FakeContainerBackend('container1')
    self.container = containers.Container(self.container_backend)

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

  @mock.patch('time.sleep')
  @mock.patch('os.open')
  @mock.patch('os.write')
  @mock.patch('os.close')
  @mock.patch('os.path.exists')
  def test_add_device(self, mock_path_exists, mock_close, mock_write, mock_open,
                      mock_sleep):
    mock_sleep.return_value = None
    mock_path_exists.return_value = True
    self.container_backend.attrs = {'Id': 'abc123'}
    self.container_backend.exec_outputs = ['', '']
    device = FakeDevice('serial1', 1)
    device.major = 111
    device.minor = 9
    device.bus = 1
    device.dev_file_path = '/dev/bus/usb/001/123'
    self.container.add_device(device)

    self.assertTrue('abc123' in mock_open.call_args[0][0])
    # Ensure the device's major and minor numbers were written to the
    # cgroup file.
    self.assertEqual(mock_write.call_args[0][1], 'c 111:9 rwm')
    self.assertTrue(mock_close.called)
    self.assertFalse(self.container_backend.is_paused)

  @mock.patch('time.sleep')
  @mock.patch('os.open')
  @mock.patch('os.path.exists')
  def test_add_device_missing_cgroup(self, mock_path_exists, mock_open,
                                     mock_sleep):
    mock_sleep.return_value = None
    mock_path_exists.return_value = False
    self.container_backend.attrs = {'Id': 'abc123'}
    self.container_backend.exec_outputs = ['']
    device = FakeDevice('serial1', 1)

    self.container.add_device(device)

    self.assertFalse(mock_open.called)
    self.assertEquals(len(self.container_backend.exec_inputs), 1)
    self.assertFalse(self.container_backend.is_paused)

  @mock.patch('time.sleep')
  @mock.patch('os.open')
  @mock.patch('os.write')
  @mock.patch('os.close')
  @mock.patch('os.path.exists')
  def test_add_device_os_open_error(self, mock_path_exists, mock_close,
                                    mock_write, mock_open, mock_sleep):
    mock_sleep.return_value = None
    mock_path_exists.return_value = True
    mock_open.side_effect = OSError('omg open error')
    self.container_backend.attrs = {'Id': 'abc123'}
    self.container_backend.exec_outputs = ['']
    device = FakeDevice('serial1', 1)
    device.major = 111
    device.minor = 9
    self.container.add_device(device)

    self.assertTrue('abc123' in mock_open.call_args[0][0])
    self.assertFalse(mock_write.called)
    self.assertFalse(mock_close.called)
    self.assertEquals(len(self.container_backend.exec_inputs), 1)
    self.assertFalse(self.container_backend.is_paused)

  @mock.patch('time.sleep')
  @mock.patch('os.open')
  @mock.patch('os.write')
  @mock.patch('os.close')
  @mock.patch('os.path.exists')
  def test_add_device_os_write_error(self, mock_path_exists, mock_close,
                                     mock_write, mock_open, mock_sleep):
    mock_sleep.return_value = None
    mock_path_exists.return_value = True
    mock_write.side_effect = OSError('omg write error')
    self.container_backend.attrs = {'Id': 'abc123'}
    self.container_backend.exec_outputs = ['']
    device = FakeDevice('serial1', 1)
    device.major = 111
    device.minor = 9
    self.container.add_device(device)

    self.assertTrue('abc123' in mock_open.call_args[0][0])
    self.assertEquals(mock_write.call_args[0][1], 'c 111:9 rwm')
    self.assertTrue(mock_close.called)
    self.assertEquals(len(self.container_backend.exec_inputs), 1)
    self.assertFalse(self.container_backend.is_paused)
