# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pipes
import socket
import time

from infra.services.swarm_docker import containers


_DOCKER_CGROUP = '/sys/fs/cgroup/devices/docker'


class AndroidContainerDescriptor(containers.ContainerDescriptorBase):
  def __init__(self, device):
    super(AndroidContainerDescriptor, self).__init__()
    self._device = device

  @property
  def name(self):
    return 'android_%s' % self._device.serial

  @property
  def shutdown_file(self):
    return '/b/%s.shutdown.stamp' % self._device.serial

  @property
  def lock_file(self):
    return '/var/lock/android_docker.%s.lock' % self._device.serial

  @property
  def hostname(self):
    this_host = socket.gethostname().split('.')[0]
    if self._device.physical_port is not None:
      return '%s--device%d' % (this_host, self._device.physical_port)
    else:
      return '%s--%s' % (this_host, self._device.serial)

  @property
  def device(self):
    return self._device

  def log_started(self):
    logging.debug('Launched new container (%s) for device %s.',
                  self.name, self.device)

  def should_create_container(self):
    if self._device.physical_port is None:
      logging.warning(
          'Unable to assign physical port num to %s. No container will be '
          'created.', self._device.serial)
      return False
    return True


class AndroidDockerClient(containers.DockerClient):
  def __init__(self):
    super(AndroidDockerClient, self).__init__()
    self.cache_size = None

  def _get_volumes(self, container_workdir):
    volumes = super(AndroidDockerClient, self)._get_volumes(container_workdir)
    volumes = volumes.copy()
    # Needed for access to device watchdog.
    volumes['/opt/infra-android'] = {'bind': '/opt/infra-android', 'mode': 'ro'}
    return volumes

  def _get_env(self, swarming_url):
    env = super(AndroidDockerClient, self)._get_env(swarming_url)
    env['ADB_LIBUSB'] = '0'
    if self.cache_size:
      env['ISOLATED_CACHE_SIZE'] = self.cache_size
    return env

  @staticmethod
  def _make_dev_file_cmd(path, major, minor):
    cmd = ('mknod %(path)s c %(major)d %(minor)d && '
           'chgrp chrome-bot %(path)s && '
           'chmod 664 %(path)s') % {
        'major': major,
        'minor': minor,
        'path': path,
    }
    return cmd

  def create_container(self, container_desc, image_name, swarming_url, labels):
    assert isinstance(container_desc, AndroidContainerDescriptor)
    super(AndroidDockerClient, self).create_container(
        container_desc, image_name, swarming_url, labels)
    self.add_device(container_desc)

  def add_device(self, container_desc, sleep_time=1.0):
    assert isinstance(container_desc, AndroidContainerDescriptor)
    container = self.get_container(container_desc)
    device = container_desc.device
    if container is None or container.state != 'running':
      logging.error('Unable to add device %s: no running container.', device)
      return

    # Remove the old dev file from the container and wait one second to
    # help ensure any wait-for-device threads inside notice its absence.
    container.exec_run('rm -rf /dev/bus')
    if device.battor is not None:
      container.exec_run('rm %s' % device.battor.tty_path)
    time.sleep(sleep_time)

    # Pause the container while modifications to its cgroup are made. This
    # isn't strictly necessary, but it helps avoid race-conditions.
    container.pause()

    try:
      # Give the container permission to access the device.
      container_id = container.attrs['Id']
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
      container.unpause()

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
      battor_mknod_cmd = AndroidDockerClient._make_dev_file_cmd(
          device.battor.tty_path, device.battor.major, device.battor.minor)
      battor_cmd = ('%(make_dev_file_cmd)s && '
                    'udevadm test %(syspath)s') % {
          'make_dev_file_cmd': battor_mknod_cmd,
          'syspath': device.battor.syspath,
      }

    device_mknod_cmd = AndroidDockerClient._make_dev_file_cmd(
        device.dev_file_path, device.major, device.minor)
    add_device_cmd = ('mkdir -p /dev/bus/usb/%(bus)03d && '
                      '%(make_dev_file_cmd)s && '
                      '%(battor_cmd)s') % {
        'bus': device.bus,
        'battor_cmd': battor_cmd,
        'make_dev_file_cmd': device_mknod_cmd,
    }
    container.exec_run('/bin/bash -c %s' % pipes.quote(add_device_cmd))

    logging.debug('Successfully gave container %s access to device %s. '
                  '(major,minor): (%d,%d) at %s.', container.name, device,
                  device.major, device.minor, device.dev_file_path)
    if device.battor is not None:
      logging.debug(
          'Also gave container %s access to battor %s. (major,minor): (%d,%d) '
          'at %s.', container.name, device.battor.serial,
          device.battor.major, device.battor.minor, device.battor.tty_path)
