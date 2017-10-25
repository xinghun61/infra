# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import docker
import logging
import os
import pwd
import requests
import socket
import time


_DOCKER_VOLUMES = {
    # The following four mounts are needed to add the host's chrome-bot user in
    # the container.
    '/home/chrome-bot': {'bind': '/home/chrome-bot', 'mode': 'rw'},
    '/etc/shadow': {'bind': '/etc/shadow', 'mode': 'ro'},
    '/etc/passwd': {'bind': '/etc/passwd', 'mode': 'ro'},
    '/etc/group': {'bind': '/etc/group', 'mode': 'ro'},
    # Needed by swarming bot to auth with server.
    '/var/lib/luci_machine_tokend': {
        'bind': '/var/lib/luci_machine_tokend',
        'mode': 'ro',
    },
    # Needed for authenticating with monitoring endpoints.
    '/creds/service_accounts': {
        'bind': '/creds/service_accounts',
        'mode': 'ro'
    },
    '/etc/chrome-infra/ts-mon.json': {
        'bind': '/etc/chrome-infra/ts-mon.json',
        'mode': 'ro'
    },
}

_SWARMING_URL_ENV_VAR = 'SWARM_URL'


class FrozenEngineError(Exception):
  """Raised when the docker engine is unresponsive."""


class FrozenContainerError(Exception):
  """Raised when a container is unresponsive."""


class ContainerDescriptorBase(object):
  @property
  def name(self):
    """Returns name to be used for the container."""
    raise NotImplementedError()

  @property
  def shutdown_file(self):
    """Returns the name of the file to drain the swarm bot in the container."""
    raise NotImplementedError()

  @property
  def lock_file(self):
    """Returns the name of the file to flock on when managing the container."""
    raise NotImplementedError()

  @property
  def hostname(self):
    """Returns hostname to be used for the container."""
    raise NotImplementedError()

  def log_started(self):
    """Logs a debug message that the container has been started."""
    raise NotImplementedError()

  def should_create_container(self):
    """Returns true if the container should be created for this descriptor."""
    raise NotImplementedError()


class ContainerDescriptor(ContainerDescriptorBase):
  def __init__(self, name):
    self._name = name

  @property
  def name(self):
    return self._name

  @property
  def shutdown_file(self):
    return '/b/%s.shutdown.stamp' % self._name

  @property
  def lock_file(self):
    return '/var/lock/swarm_docker.%s.lock' % self._name

  @property
  def hostname(self):
    this_host = socket.gethostname().split('.')[0]
    return '%s--%s' % (this_host, self._name)

  def log_started(self):
    logging.debug('Launched new container %s.', self._name)

  def should_create_container(self):
    return True


class DockerClient(object):
  def __init__(self):
    self._client = docker.from_env()
    self.logged_in = False

  def ping(self, retries=5):
    """Checks if the engine is responsive.

    Will sleep with in between retries with exponential backoff.
    Returns True if engine is responding, else False.
    """
    sleep_time = 1
    for i in xrange(retries):
      try:
        self._client.ping()
        return True
      except (docker.errors.APIError, requests.exceptions.ConnectionError):
        pass
      if i < retries - 1:
        time.sleep(sleep_time)
        sleep_time *= 2
    return False

  def login(self, registry_url, creds_path):
    if not os.path.exists(creds_path):
      raise OSError('Credential file (%s) not found.' % creds_path)

    # The container registry api requires the contents of the service account
    # to be passed in as the plaintext password. See
    # https://cloud.google.com/container-registry/docs/advanced-authentication
    with open(creds_path) as f:
      creds = f.read().strip()

    self._client.login(
        username='_json_key',  # Required to be '_json_key' by registry api.
        password=creds,
        registry=registry_url,
        reauth=True,
    )
    self.logged_in = True

  def pull(self, image):
    if not self.logged_in:
      raise Exception('Must login before pulling an image.')

    self._client.images.pull(image)

  def has_image(self, image):
    try:
      self._client.images.get(image)
      return True
    except docker.errors.ImageNotFound:
      return False

  def get_paused_containers(self):
    return [
        Container(c) for c in self._client.containers.list(
            filters={'status': 'paused'})
    ]

  def get_running_containers(self):
    return [
        Container(c) for c in self._client.containers.list(
            filters={'status': 'running'})
    ]

  def get_container(self, container_desc):
    try:
      return Container(self._client.containers.get(container_desc.name))
    except docker.errors.NotFound:
      logging.error('No running container %s.', container_desc.name)
      return None

  def stop_old_containers(self, running_containers, max_uptime):
    now = datetime.utcnow()
    frozen_containers = 0
    for container in running_containers:
      uptime = container.get_container_uptime(now)
      logging.debug(
          'Container %s has uptime of %s minutes.', container.name, str(uptime))
      if uptime is not None and uptime > max_uptime:
        try:
          container.kill_swarming_bot()
        except FrozenContainerError:
          frozen_containers += 1
    if running_containers and frozen_containers == len(running_containers):
      logging.error('All containers frozen. Docker engine most likely hosed.')
      raise FrozenEngineError()

  def delete_stopped_containers(self):
    for container in self._client.containers.list(filters={'status':'exited'}):
      logging.debug('Found stopped container %s. Removing it.', container.name)
      container.remove()

  def _get_volumes(self, container_workdir):
    volumes = _DOCKER_VOLUMES.copy()
    volumes[container_workdir] = '/b/'
    return volumes

  def _get_env(self, swarming_url):
    return {_SWARMING_URL_ENV_VAR: swarming_url + '/bot_code'}

  def create_container(self, container_desc, image_name, swarming_url, labels):
    container_workdir = '/b/%s' % container_desc.name
    pw = pwd.getpwnam('chrome-bot')
    uid, gid = pw.pw_uid, pw.pw_gid
    if not os.path.exists(container_workdir):
      os.mkdir(container_workdir)
      os.chown(container_workdir, uid, gid)
    else: # pragma: no cover
      # TODO(bpastene): Remove this once existing workdirs everywhere have been
      # chown'ed.
      os.chown(container_workdir, uid, gid)
    new_container = self._client.containers.create(
        image=image_name,
        hostname=container_desc.hostname,
        volumes=self._get_volumes(container_workdir),
        environment=self._get_env(swarming_url),
        name=container_desc.name,
        detach=True,  # Don't block until it exits.
        labels=labels,
    )
    new_container.start()
    container_desc.log_started()
    return new_container


class Container(object):
  def __init__(self, container):
    self._container = container
    self.name = container.name

  @property
  def labels(self):
    return self._container.attrs.get('Config', {}).get('Labels', {})

  @property
  def state(self):
    return self._container.attrs.get('State', {}).get('Status', 'unknown')

  @property
  def attrs(self):
    return self._container.attrs

  def exec_run(self, cmd):
    return self._container.exec_run(cmd)

  def get_container_uptime(self, now):
    """Returns the containers uptime in minutes."""
    # Docker returns start time in format "%Y-%m-%dT%H:%M:%S.%f\d\d\dZ", so chop
    # off the last 4 digits to convert from nanoseconds to micoseconds
    start_time_string = self._container.attrs['State']['StartedAt'][:-4]
    start_time = datetime.strptime(start_time_string, '%Y-%m-%dT%H:%M:%S.%f')
    return ((now - start_time).total_seconds())/60

  def get_swarming_bot_pid(self):
    try:
      output = self._container.exec_run(
          'su chrome-bot -c "lsof -t /b/swarming/swarming.lck"').strip()
    except docker.errors.NotFound:
      logging.error('Docker engine returned 404 for container %s', self.name)
      return None
    if 'rpc error:' in output:
      logging.error(
          'Unable to get bot pid of %s: %s', self._container.name, output)
      return None
    try:
      return int(output)
    except ValueError:
      logging.error(
          'Unable to get bot pid of %s. Output of lsof: "%s"',
          self._container.name, output)
      return None

  def kill_swarming_bot(self):
    pid = self.get_swarming_bot_pid()
    if pid is not None:
      # The swarming bot process will capture this signal and shut itself
      # down at the next opportunity. Once the process exits, its container
      # will exit as well.
      try:
        self._container.exec_run('kill -15 %d' % pid)
      except docker.errors.APIError:  # pragma: no cover
        logging.exception('Unable to send SIGTERM to swarming bot.')
      else:
        logging.info('Sent SIGTERM to swarming bot of %s.', self.name)
    else:
      logging.warning('Unknown bot pid. Stopping container.')
      try:
        self.stop()
      except requests.exceptions.ReadTimeout:
        logging.error('Timeout when stopping %s, force removing...', self.name)
        try:
          self.remove(force=True)
        except docker.errors.APIError:
          logging.exception(
              'Unable to remove %s. The docker engine is most likely stuck '
              'and will need a reboot.', self.name)
          raise FrozenContainerError()

  def pause(self):
    self._container.pause()

  def unpause(self):
    self._container.unpause()

  def stop(self, timeout=10):
    self._container.stop(timeout=timeout)

  def remove(self, force=False):
    self._container.remove(force=force)
