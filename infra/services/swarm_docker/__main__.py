# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import os

from infra.services.swarm_docker import containers
from infra.services.swarm_docker import main_helpers


def main():
  parser = argparse.ArgumentParser(
      description='Ensures the specified number of containers are running. '
                  'Will send a kill signal to containers that exceed max '
                  'uptime.')
  parser.add_argument(
      '-v', '--verbose', action='store_true', help='Enable verbose logging.')
  parser.add_argument(
      '--num-containers', default=10, type=int,
      help='Number of containers to run.')
  main_helpers.add_launch_arguments(parser)
  args = parser.parse_args()

  log_prefix = '%d ' % os.getpid()
  main_helpers.configure_logging(
      'swarm_containers.log', log_prefix, args.verbose)

  docker_client = containers.DockerClient()
  if not docker_client.ping():
    logging.error('Docker engine unresponsive. Quitting early.')
    return 1

  container_descriptors = []
  for i in xrange(args.num_containers):
    container_descriptors.append(
        containers.ContainerDescriptor('docker%03d' % i))

  main_helpers.launch_containers(docker_client, container_descriptors, args)

  return 0


if __name__ == '__main__':
  main_helpers.main_wrapper(main)
