# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
from datetime import datetime
import fcntl
import logging
import logging.handlers
import os
import socket
import subprocess
import sys
import time

from infra.services.android_docker import containers
from infra.services.android_docker import usb_device


_REGISTRY_URL = 'gcr.io'

# Location of file that will prevent this script from spawning new containers.
# Useful when draining a host in order to debug failures.
_SHUTDOWN_FILE = '/b/shutdown.stamp'


def get_host_uptime():
  """Returns host uptime in minutes."""
  with open('/proc/uptime') as f:
    uptime = float(f.readline().split()[0])
  return uptime / 60


def reboot_host():
  # Docker'ed android hosts should have /sbin/reboot as password-less sudo.
  cmd = ['sudo', '-n', '/sbin/reboot']
  try:
    subprocess.check_call(cmd)
  except subprocess.CalledProcessError:
    logging.exception('Unable to reboot host.')


def kill_adb():
  """Kills the adb daemon if it's up and running on the host.

  This is needed because the daemon keeps a handle open for each android
  device it sees, which prevents other processes from opening them.
  Consequently, if the daemon is up and running on the host, all containers
  are blocked from accessing their device; nor will they be able to see
  or kill the daemon process since it's outside their container.
  """
  try:
    out = subprocess.check_output(['pgrep', '--exact', 'adb'])
  except subprocess.CalledProcessError:
    logging.debug('No adb processes found.')
    return
  pids = out.split()
  # Only kill adb processes that are running outside of a container. Those
  # running inside a container are harmless.
  for pid in pids:
    # A process running in a container should have 'docker' show up in its
    # cgroup entry in procfs.
    try:
      with open('/proc/%s/cgroup' % pid) as f:
        cgroups = f.read()
    except IOError:
      logging.warning('Unable to read cgroup of process %s.', pid)
      continue
    if 'docker' not in cgroups:
      logging.warning(
          'Found adb process (%s) running outside of a container. Killing '
          'it...', pid)
      try:
        subprocess.check_call(['kill', pid])
      except subprocess.CalledProcessError:
        logging.exception('Unable to kill adb process %s', pid)


def add_device(docker_client, android_devices, args):
  # pylint: disable=unused-argument
  user_id = os.geteuid()
  if user_id != 0:
    logging.warning(
        'Current user (id: %d) is non-root. Subsequent cgroup '
        'modifications may fail.', user_id)
  for device in android_devices:
    container = docker_client.get_container(device)
    if container is not None and container.state == 'running':
      container.add_device(device)
    else:
      logging.error('Unable to add device %s: no running container.', device)


def launch(docker_client, android_devices, args):
  draining = os.path.exists(_SHUTDOWN_FILE)
  if draining:
    logging.info(
        'In draining state due to existence of %s. No new containers will be '
        'created.', _SHUTDOWN_FILE)
  running_containers = docker_client.get_running_containers()
  # Reboot the host if needed. Will attempt to kill all running containers
  # gracefully before triggering reboot.
  host_uptime = get_host_uptime()
  if host_uptime > args.max_host_uptime and not draining:
    logging.debug('Host uptime over max uptime (%d > %d)',
                  host_uptime, args.max_host_uptime)
    if len(running_containers) > 0:
      if host_uptime - args.max_host_uptime > 60:
        logging.warning(
            'Host uptime exceeds grace period of 60 min. Rebooting host now '
            'despite %d running containers.', len(running_containers))
        reboot_host()
      else:
        logging.debug(
            'Still %d containers running. Shutting them down first.',
            len(running_containers))
        for c in running_containers:
          c.kill_swarming_bot()
    else:
      logging.debug('No running containers. Rebooting host now.')
      reboot_host()
  else:  # Host uptime < max host uptime.
    # Fetch the image from the registry if it's not present locally.
    image_url = (_REGISTRY_URL + '/' + args.registry_project + '/' +
        args.image_name)
    if not docker_client.has_image(image_url):
      logging.debug('Local image missing. Fetching %s ...', image_url)
      docker_client.login(_REGISTRY_URL, args.credentials_file)
      docker_client.pull(image_url)
      logging.debug('Image %s fetched.', image_url)

    # Cleanup old containers that were stopped from a previous run.
    # TODO(bpastene): Maybe enable auto cleanup with the -rm option?
    docker_client.delete_stopped_containers()

    # Send SIGTERM to bots in containers that have been running for too long,
    # or all of them regardless of uptime if draining.
    if draining:
      for c in running_containers:
        c.kill_swarming_bot()
    else:
      docker_client.stop_old_containers(
          running_containers, args.max_container_uptime)

    # Create a container for each device that doesn't already have one.
    if not draining:
      needs_cgroup_update = docker_client.create_missing_containers(
          running_containers, android_devices, image_url, args.swarming_server)

      # For each device that was granted a new container, add it to the
      # container's cgroup.
      if len(needs_cgroup_update) > 0:
        add_device(docker_client, needs_cgroup_update, args)


def main():
  parser = argparse.ArgumentParser(
      description='Manage docker containers that wrap an android device.')
  parser.add_argument(
      '-v', '--verbose', action='store_true', help='Enable verbose logging.')
  parser.add_argument(
      '--device', action='append', dest='devices', default=[],
      help='Serial number of device whose container is to be managed. Defaults '
      'to ALL local devices.')
  subparsers = parser.add_subparsers()

  add_subparser = subparsers.add_parser(
      'add_device', help='Give a container access to its device.'
  )
  add_subparser.set_defaults(func=add_device, name='add_device')

  launch_subparser = subparsers.add_parser(
      'launch',
      help='Ensures the specified devices have a running container. Will send '
           'a kill signal to containers that exceed max uptime.'
  )
  launch_subparser.set_defaults(func=launch, name='launch')
  launch_subparser.add_argument(
      '--max-container-uptime', type=int, default=60 * 4,
      help='Max uptime of a container, in minutes.')
  launch_subparser.add_argument(
      '--max-host-uptime', type=int, default=60 * 24,
      help='Max uptime of the host, in minutes.')
  launch_subparser.add_argument(
      '--image-name', default='android_docker:latest',
      help='Name of docker image to launch from.')
  launch_subparser.add_argument(
      '--swarming-server', default='https://chromium-swarm.appspot.com',
      help='URL of the swarming server to connect to.')
  launch_subparser.add_argument(
      '--registry-project', default='chromium-container-registry',
      help='Name of gcloud project id for the container registry.')
  launch_subparser.add_argument(
      '--credentials-file',
      default='/creds/service_accounts/'
              'service-account-container_registry_puller.json',
      help='Path to service account json file used to access the gcloud '
           'container registry.')
  args = parser.parse_args()

  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG if args.verbose else logging.WARNING)
  log_fmt = logging.Formatter(
      '%(asctime)s.%(msecs)03d %(levelname)s %(message)s',
      datefmt='%y%m%d %H:%M:%S')

  # Udev-triggered runs of this script run as root while the crons run as
  # non-root. Manually set umask to ensure the world can read/write to the log
  # files even if they're owned by root.
  os.umask(0o000)
  file_handler = logging.handlers.RotatingFileHandler(
      '/var/log/chrome-infra/android_containers.log',
      maxBytes=10 * 1024 * 1024, backupCount=5)
  file_handler.setFormatter(log_fmt)
  logger.addHandler(file_handler)
  stdout_handler = logging.StreamHandler(sys.stdout)
  logger.addHandler(stdout_handler)

  logging.debug('Killing any host-side ADB processes.')
  kill_adb()

  logging.debug('Running %s on devices: %s', args.name, args.devices or 'all')

  docker_client = containers.DockerClient()
  if not docker_client.ping():
    logging.error('Docker engine unresponsive. Quitting early.')
    return 1
  android_devices = usb_device.get_android_devices(args.devices)

  args.func(docker_client, android_devices, args)

  return 0


if __name__ == '__main__':
  if sys.platform != 'linux2':
    print 'Only supported on linux.'
    sys.exit(1)
  try:
    sys.exit(main())
  except Exception as e:
    logging.exception('Exception:')
    raise e
