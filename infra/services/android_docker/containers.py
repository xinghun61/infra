# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
from datetime import datetime
import fcntl
import docker
import logging
import logging.handlers
import pipes
import pwd
import os
import requests
import socket
import subprocess
import sys
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
    # Needed for access to device watchdog.
    '/opt/infra-android': {'bind': '/opt/infra-android', 'mode': 'ro'},
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
_DOCKER_CGROUP = '/sys/fs/cgroup/devices/docker'

_SWARMING_URL_ENV_VAR = 'SWARM_URL'


def get_container_name(device):
  """Maps a device to its container name."""
  return 'android_%s' % device.serial


def get_container_hostname(device):
  """Maps a device to its container hostname."""
  this_host = socket.gethostname().split('.')[0]
  if device.physical_port is not None:
    return '%s--device%d' % (this_host, device.physical_port)
  else:
    return '%s--%s' % (this_host, device.serial)


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

  def get_container(self, device):
    container_name = get_container_name(device)
    try:
      return Container(self._client.containers.get(container_name))
    except docker.errors.NotFound:
      logging.error('No running container for device %s.', device)
      return None

  def stop_old_containers(self, running_containers, max_uptime):
    now = datetime.utcnow()
    for container in running_containers:
      uptime = container.get_container_uptime(now)
      logging.debug(
          'Container %s has uptime of %d minutes.', container.name, uptime)
      if uptime is not None and uptime > max_uptime:
        container.kill_swarming_bot()

  def delete_stopped_containers(self):
    for container in self._client.containers.list(filters={'status':'exited'}):
      logging.debug('Found stopped container %s. Removing it.', container.name)
      container.remove()

  def create_container(self, device, image_name, swarming_url):
    """Creates a container for an android device."""
    container_name = get_container_name(device)
    container_hostname = get_container_hostname(device)
    container_workdir = '/b/%s' % container_name
    pw = pwd.getpwnam('chrome-bot')
    uid, gid = pw.pw_uid, pw.pw_gid
    if not os.path.exists(container_workdir):
      os.mkdir(container_workdir)
      os.chown(container_workdir, uid, gid)
    else: # pragma: no cover
      # TODO(bpastene): Remove this once existing workdirs everywhere have been
      # chown'ed.
      os.chown(container_workdir, uid, gid)
    volumes = _DOCKER_VOLUMES.copy()
    volumes[container_workdir] = '/b/'
    new_container = self._client.containers.create(
        image=image_name,
        hostname=container_hostname,
        volumes=volumes,
        environment={
            _SWARMING_URL_ENV_VAR: swarming_url + '/bot_code',
            # When using libusb, adb lists devices it doesn't have access
            # to. Avoid the ambiguity by disabling libusb mode.
            'ADB_LIBUSB': '0',
        },
        name=container_name,
        detach=True,  # Don't block until it exits.
    )
    new_container.start()
    logging.debug('Launched new container (%s) for device %s.',
                  new_container.name, device)
    return new_container


class Container(object):
  def __init__(self, container):
    self._container = container
    self.name = container.name

  @property
  def state(self):
    return self._container.attrs.get('State', {}).get('Status', 'unknown')

  def get_container_uptime(self, now):
    """Returns the containers uptime in minutes."""
    # Docker returns start time in format "%Y-%m-%dT%H:%M:%S.%f\d\d\dZ", so chop
    # off the last 4 digits to convert from nanoseconds to micoseconds
    start_time_string = self._container.attrs['State']['StartedAt'][:-4]
    start_time = datetime.strptime(start_time_string, '%Y-%m-%dT%H:%M:%S.%f')
    return ((now - start_time).total_seconds())/60

  def get_swarming_bot_pid(self):
    output = self._container.exec_run(
        'su chrome-bot -c "lsof -t /b/swarming/swarming.lck"').strip()
    if 'rpc error:' in output:
      logging.error(
          'Unable to get bot pid of %s: %s', self._container.name, output)
      return None
    try:
      return int(output)
    except ValueError:
      logging.exception(
          'Unable to get bot pid of %s: %s', self._container.name, output)
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

  def _make_dev_file_cmd(self, path, major, minor):
    cmd = ('mknod %(path)s c %(major)d %(minor)d && '
           'chgrp chrome-bot %(path)s && '
           'chmod 664 %(path)s') % {
        'major': major,
        'minor': minor,
        'path': path,
    }
    return cmd

  def pause(self):
    self._container.pause()

  def unpause(self):
    self._container.unpause()

  def add_device(self, device, sleep_time=1.0):
    # Remove the old dev file from the container and wait one second to
    # help ensure any wait-for-device threads inside notice its absence.
    self._container.exec_run('rm -rf /dev/bus')
    if device.battor is not None:
      self._container.exec_run('rm %s' % device.battor.tty_path)
    time.sleep(sleep_time)

    # Pause the container while modifications to its cgroup are made. This
    # isn't strictly necessary, but it helps avoid race-conditions.
    self.pause()

    try:
      # Give the container permission to access the device.
      container_id = self._container.attrs['Id']
      path_to_cgroup = os.path.join(
          _DOCKER_CGROUP, container_id, 'devices.allow')
      if not os.path.exists(path_to_cgroup):
        logging.error(
            'cgroup file %s does not exist for device %s.',
            device, path_to_cgroup)
        return
      try:
        cgroup_fd = os.open(path_to_cgroup, os.O_WRONLY)
      except OSError:
        logging.exception(
            'Unable to open cgroup file %s for device %s.',
            path_to_cgroup, device)
        return
      try:
        os.write(cgroup_fd, 'c %d:%d rwm' % (device.major, device.minor))
        if device.battor is not None:
          os.write(cgroup_fd,
                   'c %d:%d rwm' % (device.battor.major, device.battor.minor))
      except OSError:
        logging.exception(
            'Unable to write to cgroup %s of %s\'s container.',
            path_to_cgroup, device)
        return
      finally:
        os.close(cgroup_fd)

      # Sleep one more second to ensure the container's cgroup picks up the
      # changes that were just made.
      time.sleep(sleep_time)
    finally:
      self.unpause()

    # In-line these mutliple commands to help avoid a race condition in adb
    # that gets in a stuck state when polling for devices half-way through.
    battor_cmd = "true"  # No-op default command.
    if device.battor is not None:
      # The following command creates the battor's dev file in the container.
      # It also updates the device's entry in the udev database by simulating
      # the ADD udev event for the device via the udevadm tool, populating all
      # of its ID_* fields. This is needed because udev events of devices
      # aren't propagated into the containers, and some tests scan for devices
      # by looking up various udev properties (e.g. chromium's src/device/serial
      # library.)
      battor_mknod_cmd = self._make_dev_file_cmd(
          device.battor.tty_path, device.battor.major, device.battor.minor)
      battor_cmd = ('%(make_dev_file_cmd)s && '
                    'udevadm test %(syspath)s') % {
          'make_dev_file_cmd': battor_mknod_cmd,
          'syspath': device.battor.syspath,
      }

    device_mknod_cmd = self._make_dev_file_cmd(
        device.dev_file_path, device.major, device.minor)
    add_device_cmd = ('mkdir -p /dev/bus/usb/%(bus)03d && '
                      '%(make_dev_file_cmd)s && '
                      '%(battor_cmd)s') % {
        'bus': device.bus,
        'battor_cmd': battor_cmd,
        'make_dev_file_cmd': device_mknod_cmd,
    }
    self._container.exec_run('/bin/bash -c %s' % pipes.quote(add_device_cmd))

    logging.debug('Successfully gave container %s access to device %s. '
                  '(major,minor): (%d,%d) at %s.', self._container.name, device,
                  device.major, device.minor, device.dev_file_path)
    if device.battor is not None:
      logging.debug(
          'Also gave container %s access to battor %s. (major,minor): (%d,%d) '
          'at %s.', self._container.name, device.battor.serial,
          device.battor.major, device.battor.minor, device.battor.tty_path)
