# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pipes
import socket
import time

from infra.services.swarm_docker import containers


CROS_SSH_ID_ENV_VAR = 'CROS_SSH_ID_FILE_PATH'
UNIVERSAL_CROS_HOSTNAME = 'variable_chromeos_device_hostname'


class CrosContainerDescriptor(containers.ContainerDescriptorBase):
  def __init__(self, device_hostname, ssh_id_path):
    super(CrosContainerDescriptor, self).__init__()
    self._device_hostname = device_hostname
    self._ssh_id_path = ssh_id_path

  @property
  def name(self):
    return 'cros_%s' % self._device_hostname

  @property
  def shutdown_file(self):
    return '/b/%s.shutdown.stamp' % self._device_hostname

  @property
  def lock_file(self):
    return '/var/lock/cros_docker.%s.lock' % self._device_hostname

  @property
  def hostname(self):
    this_host = socket.gethostname().split('.')[0]
    return '%s--%s' % (this_host, self._device_hostname)

  @property
  def device_hostname(self):
    return self._device_hostname

  @property
  def ssh_id_path(self):
    return self._ssh_id_path

  def log_started(self):
    logging.debug('Launched new container (%s) for device %s.',
                  self.name, self._device_hostname)


class CrosDockerClient(containers.DockerClient):
  def __init__(self):
    super(CrosDockerClient, self).__init__()

  def create_container(self, container_desc, image_name, swarming_url, labels,
                       additional_env=None):
    assert isinstance(container_desc, CrosContainerDescriptor)
    env = {
        CROS_SSH_ID_ENV_VAR: container_desc.ssh_id_path,
    }
    container = super(CrosDockerClient, self).create_container(
        container_desc, image_name, swarming_url, labels,
        additional_env=env)

    # Add an entry to /etc/hosts that points a universal hostname to the
    # cros device.
    ip = None
    try:
      ip = socket.gethostbyname(container_desc.device_hostname)
      logging.info('Fetched IPv4 of %s: %s', container_desc.device_hostname, ip)
    except socket.gaierror:
      logging.error(
          'Unable to get IPv4 of %s. Hosts file will remain unchanged.',
          container_desc.device_hostname)
    if ip:
      append_cmd = 'echo "%s %s" >> /etc/hosts' % (ip, UNIVERSAL_CROS_HOSTNAME)
      out = container.exec_run('/bin/bash -c %s' % pipes.quote(append_cmd))
      logging.info('Result from modifying hosts file: %s', out)

    return container
