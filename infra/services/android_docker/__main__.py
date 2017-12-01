# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import os
import subprocess
import threading

from infra.services.android_docker import containers
from infra.services.android_docker import usb_device
from infra.services.swarm_docker import main_helpers


_USB_BUS_LOCK_FILE = '/var/lock/android_docker.usb_bus.lock'


def get_disk_partition_size(path, android_devices, usage_ratio=0.8):
  """Gets the size on disk a container will be granted for its isolate cache.

  Args:
    path: Path to a file or dir on the same filesystem as the caches. The path
          will be stat'ed to get that filesystem's info.
    android_devices: List of devices connected.
    usage_ratio: What percentage of the disk to use.
  Returns:
    Size in bytes of the isolate cache each swarming bot will use.
  """
  # Fetch the usage stats of the filesystem that the caches will be located.
  fs_stat = os.statvfs(path)
  # Use only the specified percent of the disk for container usage. Keep the
  # remainder free for host-side things.
  total_size = (fs_stat.f_bsize * fs_stat.f_blocks) * usage_ratio
  # Each container gets its own seperate cache, so calculate the number of
  # needed caches. Note that some devices may temporarily disappear, so let's
  # provision for at least seven per bot. (In case 6 of the 7 drop off
  # momentarily and the remainder suddenly has the entire disk to work with.)
  number_of_caches = max(7, len(android_devices))
  partition_size = total_size / number_of_caches
  # Round to nearest block size
  partition_size = int(fs_stat.f_bsize * round(partition_size/fs_stat.f_bsize))
  # Finally, to ensure that we don't allocate a tiny cache if something goes
  # wrong above, ignore the calculated value if it's less than 10 GB.
  return max(10 * 1024 * 1024 * 1024, partition_size)


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


def add_device(docker_client, device, args):  # pylint: disable=unused-argument
  desc = containers.AndroidContainerDescriptor(device)
  try:
    with main_helpers.flock(desc.lock_file):
      docker_client.add_device(desc)
  except main_helpers.FlockTimeoutError:
    logging.error('Unable to acquire device lock on %s in time.', device)


def launch(docker_client, android_devices, args):
  container_descriptors = map(
      containers.AndroidContainerDescriptor, android_devices)
  main_helpers.launch_containers(docker_client, container_descriptors, args)


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
  main_helpers.add_launch_arguments(launch_subparser)
  args = parser.parse_args()

  # Udev-triggered runs of this script run as root while the crons run as
  # non-root. Manually set umask to ensure the world can read/write to the log
  # files even if they're owned by root.
  os.umask(0o000)
  log_prefix = '%d %s-%s' % (
      os.getpid(), args.name, ','.join(args.devices) if args.devices else 'all')
  main_helpers.configure_logging(
      'android_containers.log', log_prefix, args.verbose)

  if not os.path.exists(main_helpers.BOT_SHUTDOWN_FILE):
    logging.debug('Killing any host-side ADB processes.')
    kill_adb()

  docker_client = containers.AndroidDockerClient()
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
    with main_helpers.flock(_USB_BUS_LOCK_FILE):
      android_devices = usb_device.get_android_devices(args.devices)
  except main_helpers.FlockTimeoutError:
    logging.error('Unable to acquire usb bus lock in time.')
    return 1

  # Limit the isolated cache size of each container to avoid running out of
  # space on disk.
  docker_client.cache_size = get_disk_partition_size('/b/', android_devices)

  # Lock on each device individually so multiple devices can be worked on
  # simultaneously.
  if args.devices:
    def _process_device(d):
      args.func(docker_client, d, args)
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
  main_helpers.main_wrapper(main)
