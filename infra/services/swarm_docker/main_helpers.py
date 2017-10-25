# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import json
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
import time

from infra.libs.service_utils import daemon
from infra.services.swarm_docker import containers


_REGISTRY_URL = 'gcr.io'

# Location of file that will prevent this script from spawning new containers.
# Useful when draining a host in order to debug failures. BOT_SHUTDOWN_FILE
# drains all containers, but individual containers can also be drained using
# container's shutdown file as returned by its descriptor class.
BOT_SHUTDOWN_FILE = '/b/shutdown.stamp'

# Time to wait for swarming bots to gracefully shutdown before triggering a
# host reboot. It should be at least as long as the longest expected task
# run time.
_REBOOT_GRACE_PERIOD_MIN = 240

# Defined in
# https://chromium.googlesource.com/infra/infra/+/master/build/packages/android_docker.yaml
_CIPD_VERSION_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'CIPD_VERSION.json'))


def get_cipd_version():
  if not os.path.exists(_CIPD_VERSION_FILE):
    logging.warning('Unable to find cipd version file %s', _CIPD_VERSION_FILE)
    return None
  try:
    with open(_CIPD_VERSION_FILE) as f:
      d = json.load(f)
    return d.get('instance_id')
  except (IOError, ValueError):
    logging.exception('Unable to read cipd version file %s', _CIPD_VERSION_FILE)
    return None


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


class FlockTimeoutError(Exception):
  pass


@contextlib.contextmanager
def flock(lock_file, retries=20, sleep_duration=3):  # pragma: no cover
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


def launch_containers(
    docker_client, container_descriptors, args):  # pragma: no cover
  draining_host = os.path.exists(BOT_SHUTDOWN_FILE)
  draining_container_descriptors = [
      cd for cd in container_descriptors if os.path.exists(cd.shutdown_file)
  ]
  if draining_host:
    logging.info(
        'In draining state due to existence of %s. No new containers will be '
        'created.', BOT_SHUTDOWN_FILE)
  elif draining_container_descriptors:
    logging.info(
        'Draining containers %s due to existence of files: %s. They will not '
        'be restarted automatically.',
        [cd.name for cd in draining_container_descriptors],
        [cd.shutdown_file for cd in draining_container_descriptors])

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

    # Send SIGTERM to bots in containers that have been running for too long, or
    # all of them regardless of uptime if draining. For Android containers (see
    # infra.services.android_swarm package), some containers may go missing due
    # to associated devices missing, so we need to examine *all* containers here
    # instead of doing that inside the per-container flock below.
    current_cipd_version = get_cipd_version()
    if draining_host:
      for c in running_containers:
        c.kill_swarming_bot()
    else:
      for cd in draining_container_descriptors:
        c = docker_client.get_container(cd)
        if c is not None:
          c.kill_swarming_bot()
      docker_client.stop_old_containers(
          running_containers, args.max_container_uptime)

      # Also stop any outdated container.
      if current_cipd_version is not None:
        for c in running_containers:
          if c.labels.get('cipd_version') != current_cipd_version:
            logging.debug(
                'Container %s is out of date. Shutting it down.', c.name)
            c.kill_swarming_bot()

    # Make sure all requested containers are running.
    if not draining_host:
      def _create_container(container_desc):
        try:
          with flock(container_desc.lock_file):
            c = docker_client.get_container(container_desc)
            if c is None:
              labels = {}
              # Attach current cipd version to container's metadata so it can
              # be restarted if version changes.
              if current_cipd_version is not None:
                labels['cipd_version'] = current_cipd_version
              docker_client.create_container(
                  container_desc, image_url, args.swarming_server, labels)
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
          logging.error(
              'Timed out while waiting for lock on container %s.',
              container_desc.name)

      threads = []
      for cd in container_descriptors:
        # TODO(sergiyb): Remove should_craete_container logic from this generic
        # container management loop and move it outside of the launch_container
        # function as it's specific to Android devices only.
        if (cd.should_create_container() and
            cd not in draining_container_descriptors):
          # Split this into threads so a blocking container doesn't block the
          # others (and also for speed!)
          t = threading.Thread(target=_create_container, args=(cd,))
          threads.append(t)
          t.start()
      for t in threads:
        t.join()


def add_launch_arguments(parser):
  parser.add_argument(
      '--max-container-uptime', type=int, default=60 * 4,
      help='Max uptime of a container, in minutes.')
  parser.add_argument(
      '--max-host-uptime', type=int, default=60 * 24,
      help='Max uptime of the host, in minutes.')
  parser.add_argument(
      '--image-name', default='swarm_docker:latest',
      help='Name of docker image to launch from.')
  parser.add_argument(
      '--swarming-server', default='https://chromium-swarm.appspot.com',
      help='URL of the swarming server to connect to.')
  parser.add_argument(
      '--registry-project', default='chromium-container-registry',
      help='Name of gcloud project id for the container registry.')
  parser.add_argument(
      '--credentials-file',
      default='/creds/service_accounts/'
              'service-account-container_registry_puller.json',
      help='Path to service account json file used to access the gcloud '
           'container registry.')


def configure_logging(log_filename, log_prefix, verbose):
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
  log_fmt = logging.Formatter(
      '%(asctime)s.%(msecs)03d %(levelname)s ' + log_prefix + ' %(message)s' ,
      datefmt='%y%m%d %H:%M:%S')

  file_handler = logging.handlers.RotatingFileHandler(
      '/var/log/chrome-infra/%s' % log_filename,
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


def main_wrapper(main_func):
  if sys.platform != 'linux2':
    print 'Only supported on linux.'
    sys.exit(1)
  try:
    sys.exit(main_func())
  except containers.FrozenEngineError:
    logging.exception('Docker engine frozen, triggering host reboot.')
    reboot_host()
  except Exception as e:
    logging.exception('Exception:')
    raise e
