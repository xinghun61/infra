# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import contextlib
from datetime import datetime
import fcntl
import logging
import logging.handlers
import os
import socket
import subprocess
import sys
import time
import threading

from infra.libs.service_utils import daemon
from infra.services.android_docker import containers
from infra.services.android_docker import usb_device


_REGISTRY_URL = 'gcr.io'

# Location of file that will prevent this script from spawning new containers.
# Useful when draining a host in order to debug failures. _BOT_SHUTDOWN_FILE
# drains the entire bot while _DEVICE_SHUTDOWN_FILE drains only a specific
# device.
_BOT_SHUTDOWN_FILE = '/b/shutdown.stamp'
_DEVICE_SHUTDOWN_FILE = '/b/%(device_id)s.shutdown.stamp'

# Time to wait for swarming bots to gracefully shutdown before triggering a
# host reboot. It should be at least as long as the longest expected task
# run time.
_REBOOT_GRACE_PERIOD_MIN = 240

_DEVICE_LOCK_FILE = '/var/lock/android_docker.%(device_id)s.lock'
_USB_BUS_LOCK_FILE = '/var/lock/android_docker.usb_bus.lock'


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


class FlockTimeoutError(Exception):
  pass


@contextlib.contextmanager
def flock(lock_file, retries=20, sleep_duration=3):
  logging.debug('Acquiring file lock on %s...', lock_file)
  i = 0
  while True:
    try:
      with daemon.flock(lock_file):
        logging.debug('Lock acquired on %s.', lock_file)
        try:
          yield
        finally:
          logging.debug('Releasing lock on %s.', lock_file)
      break
    except daemon.LockAlreadyLocked:
      if i == retries - 1:
        raise FlockTimeoutError()
      else:
        logging.debug('Lock on %s busy; sleeping for %d seconds.',
                      lock_file, sleep_duration)
        i += 1
        time.sleep(sleep_duration)


def add_device(docker_client, device, args):
  # pylint: disable=unused-argument
  container = docker_client.get_container(device)
  if container is not None and container.state == 'running':
    container.add_device(device)
  else:
    logging.error('Unable to add device %s: no running container.', device)


def launch(docker_client, android_devices, args):
  draining_host = os.path.exists(_BOT_SHUTDOWN_FILE)
  draining_devices = [
      d for d in android_devices if os.path.exists(
          _DEVICE_SHUTDOWN_FILE % {'device_id': d.serial})
  ]
  if draining_host:
    logging.info(
        'In draining state due to existence of %s. No new containers will be '
        'created.', _BOT_SHUTDOWN_FILE)
  elif draining_devices:
    logging.info(
        'Draining devices %s due to existence of files: %s. They will not be '
        'granted new containers.', draining_devices,
        [_DEVICE_SHUTDOWN_FILE % {'device_id': d.serial}
            for d in draining_devices])

  running_containers = docker_client.get_running_containers()
  # Reboot the host if needed. Will attempt to kill all running containers
  # gracefully before triggering reboot.
  host_uptime = get_host_uptime()
  if host_uptime > args.max_host_uptime and not draining_host:
    logging.debug('Host uptime over max uptime (%d > %d)',
                  host_uptime, args.max_host_uptime)
    if len(running_containers) > 0:
      if host_uptime - args.max_host_uptime > _REBOOT_GRACE_PERIOD_MIN:
        logging.warning(
            'Host uptime exceeds grace period of %d min. Rebooting host now '
            'despite %d running containers.', _REBOOT_GRACE_PERIOD_MIN,
            len(running_containers))
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
    # or all of them regardless of uptime if draining. This stays outside the
    # per-device flock below due to the fact that a container's device might
    # go missing, so we need to examine *all* containers here.
    if draining_host:
      for c in running_containers:
        c.kill_swarming_bot()
    else:
      for d in draining_devices:
        c = docker_client.get_container(d)
        if c is not None:
          c.kill_swarming_bot()
      docker_client.stop_old_containers(
          running_containers, args.max_container_uptime)

    # Create a container for each device that doesn't already have one.
    if not draining_host:
      def _create_container(d):
        try:
          with flock(_DEVICE_LOCK_FILE % {'device_id': d.serial}):
            c = docker_client.get_container(d)
            if c is None:
              docker_client.create_container(d, image_url, args.swarming_server)
              add_device(docker_client, d, args)
            elif c.state == 'paused':
              # Occasionally a container gets stuck in the paused state. Since
              # the logic here is thread safe, this shouldn't happen, so
              # explicitly unpause them before continuing.
              # TODO(bpastene): Find out how/why.
              logging.warning('Unpausing container %s.', c.name)
              c.unpause()
            else:
              logging.debug('Nothing to do for container %s.', c.name)
        except FlockTimeoutError:
          logging.error('Timed out while waiting for lock on device %s.', d)

      threads = []
      for d in android_devices:
        if d.physical_port is None:
          logging.warning(
              'Unable to assign physical port num to %s. No container will be '
              'created.', d.serial)
        elif d not in draining_devices:
          # Split this into threads so a blocking container doesn't block the
          # others (and also for speed!)
          t = threading.Thread(target=_create_container, args=(d,))
          threads.append(t)
          t.start()
      for t in threads:
        t.join()


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

  log_prefix = '%d %s-%s' % (
      os.getpid(), args.name, ','.join(args.devices) if args.devices else 'all')
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG if args.verbose else logging.WARNING)
  log_fmt = logging.Formatter(
      '%(asctime)s.%(msecs)03d %(levelname)s ' + log_prefix + ' %(message)s' ,
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

  # Quiet some noisy modules.
  cmd_helper_logger = logging.getLogger('devil.utils.cmd_helper')
  cmd_helper_logger.setLevel(logging.ERROR)
  urllib3_logger = logging.getLogger('requests.packages.urllib3.connectionpool')
  urllib3_logger.setLevel(logging.WARNING)

  if not os.path.exists(_BOT_SHUTDOWN_FILE):
    logging.debug('Killing any host-side ADB processes.')
    kill_adb()

  docker_client = containers.DockerClient()
  if not docker_client.ping():
    logging.error('Docker engine unresponsive. Quitting early.')
    return 1

  user_id = os.geteuid()
  if user_id != 0:
    logging.warning(
        'Current user (id: %d) is non-root. Subsequent cgroup '
        'modifications may fail.', user_id)

  # Devices can drop in and out several times in a second, so wrap all
  # proceeding container interactions in a mutex (via a flock) to prevent
  # multiple processes from stepping on each other.
  # Lock on usb bus interaction seperately.
  try:
    with flock(_USB_BUS_LOCK_FILE):
      android_devices = usb_device.get_android_devices(args.devices)
  except FlockTimeoutError:
    logging.error('Unable to acquire usb bus lock in time.')
    return 1

  # Lock on each device individually so multiple devices can be worked on
  # simultaneously.
  if args.devices:
    def _process_device(d):
      try:
        with flock(_DEVICE_LOCK_FILE % {'device_id': d.serial}):
          args.func(docker_client, d, args)
      except FlockTimeoutError:
        logging.error('Unable to acquire device lock on %s in time.', d)
    threads = []
    for d in android_devices:
      t = threading.Thread(target=_process_device, args=(d,))
      threads.append(t)
      t.start()
    for t in threads:
      t.join()
  else:
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
