# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import logging
import os
import sys

from infra.services.cros_docker import containers
from infra.services.cros_docker import host
from infra.services.swarm_docker import main_helpers


def main():
  parser = argparse.ArgumentParser(
      description='Manage docker containers that wrap a ChromeOS device.')
  parser.add_argument(
      '-v', '--verbose', action='store_true', help='Enable verbose logging.')
  parser.add_argument(
      'path_to_device_list',
      help='Path to json file containing list of CrOS device hostnames. Each '
           'device will be granted a container.')

  main_helpers.add_launch_arguments(parser)
  args = parser.parse_args()

  log_prefix = '%d' % os.getpid()
  main_helpers.configure_logging(
      'cros_containers.log', log_prefix, args.verbose)

  docker_client = containers.CrosDockerClient()
  if not docker_client.ping():
    logging.error('Docker engine unresponsive. Quitting early.')
    return 1

  if host.should_write_ssh_config():
    host.write_ssh_config()

  devices = host.read_device_list(args.path_to_device_list)
  container_descriptors = [
      containers.CrosContainerDescriptor(
          d, host.SSH_IDENTITY_FILE_PATH) for d in devices]
  main_helpers.launch_containers(docker_client, container_descriptors, args)

  return 0


if __name__ == '__main__':
  with main_helpers.main_wrapper():
    sys.exit(main())
