# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import json
import logging
import os.path
import signal
import sys
import time

import psutil

from infra.libs.service_utils import daemon
from infra.services.service_manager import version_finder

LOGGER = logging.getLogger(__name__)


class ServiceException(Exception):
  pass


class Service(object):
  """Controls a running service process.

  Starts and stops the process, checks whether it is running, and creates and
  deletes its state file in the state_directory.

  State files are like UNIX PID files, except they also contain the starttime
  (read from /proc/$PID/stat) of the process to protect against the race
  condition of a different process reusing the same PID.
  """

  def __init__(self, state_directory, service_config, time_fn=time.time,
               sleep_fn=time.sleep):
    """
    Args:
      state_directory: A file will be created in this directory (with the same
          name as the service) when it is running containing its PID and
          starttime.
      service_config: A dictionary containing the service's config.  See README
          for a description of the fields.
    """

    self.config = service_config
    self.name = service_config['name']
    self.root_directory = service_config['root_directory']
    self.tool = service_config['tool']

    self.args = service_config.get('args', [])
    self.stop_time = int(service_config.get('stop_time', 10))

    self._state_file = os.path.join(state_directory, self.name)
    self._time_fn = time_fn
    self._sleep_fn = sleep_fn

  def get_running_process_state(self):
    """Returns an information dict about the process if it's currently running.

    The returned dict contains the following keys:
      pid: The process' PID.
      starttime: The time the process started (as read from /proc/$pid/stat).
          The value can be compared to the starttime of a process that claims
          the same PID in the future to check whether it's the same process, or
          a different process that has recycled the same PID.
      version: The version of the service's package at the time the service was
          started.

    Returns None if the service is not running.
    """

    if not os.path.exists(self._state_file):
      LOGGER.info('State file %s does not exist', self._state_file)
      return None

    try:
      with open(self._state_file) as fh:
        data = json.load(fh)
        pid = data['pid']
        starttime = data['starttime']  # pragma: no cover
    except IOError as ex:
      LOGGER.error('Failed to open state file %s: %r', self._state_file, ex)
      return None
    except Exception as ex:
      LOGGER.error('Failed to parse state file %s: %r', self._state_file, ex)
      return None

    # Check that the same process is still on this pid.
    actual_starttime = self._read_starttime(pid)
    if actual_starttime is None:
      LOGGER.warning('Process with PID %d is no longer running', pid)
      return None

    if actual_starttime != starttime:
      LOGGER.warning('Process with PID %d now has starttime %f, expected %f',
          pid, actual_starttime, starttime)
      return None

    return data

  def is_running(self):
    """Returns True if the service is running."""
    return self.get_running_process_state() is not None

  def has_version_changed(self):
    """Returns True if the version has changed since the process started."""

    state = self.get_running_process_state()
    if state is None:
      return False

    return state['version'] != version_finder.find_version(self.config)

  def start(self):
    """Starts the service if it's not running already.

    Does nothing if the service is running already.  Raises ServiceException if
    the process couldn't be started.
    """

    if self.is_running():
      return

    LOGGER.info("Starting service %s", self.name)

    pipe_r, pipe_w = os.pipe()
    child_pid = os.fork()
    if child_pid == 0:
      os.close(pipe_r)
      try:
        self._start_child(os.fdopen(pipe_w, 'w'))
      finally:
        os._exit(1)
    else:
      os.close(pipe_w)
      self._start_parent(os.fdopen(pipe_r, 'r'), child_pid)

  def stop(self):
    """Stops the service if it is currently running.

    Does nothing if it's not running.
    """

    data = self.get_running_process_state()
    if data is None:
      return

    if not self._signal_and_wait(
        data['pid'], data['starttime'], signal.SIGTERM, self.stop_time):
      self._signal_and_wait(
          data['pid'], data['starttime'], signal.SIGKILL, None)

    LOGGER.info("Service %s stopped", self.name)

    # Remove the state file.
    os.unlink(self._state_file)

  def _read_starttime(self, pid):  # pragma: no cover
    """Reads the starttime value of the process with the given PID.

    Returns None if that PID does not exist.
    """

    try:
      return psutil.Process(pid).create_time()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
      return None

  def _start_child(self, pipe):
    """The part of start() that runs in the child process.

    Daemonises the current process, writes the new PID to the pipe, and execs
    the service executable.
    """

    # Detach from the parent and close all FDs except that of the pipe.
    daemon.become_daemon(keep_fds={pipe.fileno()})

    # Write our new PID to the pipe and close it.
    json.dump({'pid': os.getpid()}, pipe)
    pipe.close()

    # Exec the service.
    runpy = os.path.join(self.root_directory, 'run.py')
    os.execv(runpy, [runpy, self.tool] + self.args)

  def _start_parent(self, pipe, child_pid):
    """The part of start() that runs in the parent process.

    Waits for the child to start and writes a state file for the process.
    """

    # Read the data from the pipe.  The daemon process will close this pipe
    # before starting the service, or it will be closed when the child exits.
    data = pipe.read()

    # Reap the child we forked.
    _, exit_status = os.waitpid(child_pid, 0)
    if exit_status != 0:
      raise ServiceException(
          'Failed to start %s: child process exited with %d' % (
              self.name, exit_status))

    # Try to parse the JSON sent by the daemon process.
    try:
      data = json.loads(data)
    except Exception:
      raise ServiceException(
          'Failed to start %s: daemon process didn\'t send a valid PID' %
          self.name)

    self._write_state_file(data['pid'])
    LOGGER.info("Service %s started with PID %d", self.name, data['pid'])

  def _write_state_file(self, pid):
    starttime = self._read_starttime(pid)
    if starttime is None:
      raise ServiceException(
          'Failed to start %s: daemon process exited' % self.name)

    contents = json.dumps({
        'pid': pid,
        'starttime': starttime,
        'version': version_finder.find_version(self.config),
    })
    LOGGER.info('Writing state file %s: %s', self._state_file, contents)

    # Write the daemon's PID and its starttime to the state file.
    with open(self._state_file, 'w') as fh:
      fh.write(contents)

  def _signal_and_wait(self, pid, starttime, sig, wait_timeout):
    """Sends a signal to the given process, and optionally waits for it to exit.

    Args:
      pid: The PID of the process to signal.
      starttime: The starttime of the process.  Used to check whether another
          process has recycled this PID.
      sig: The signal number to send (see the constants in the signal module).
      wait_timeout: Time in seconds to wait for this process to exit after
          sending the signal, or None to return immediately.

    Returns:
      False if the process was still running after the timeout, or True if the
      process exited within the timeout, or timeout was None.
    """

    LOGGER.info("Sending signal %d to %s with PID %d",
                sig, self.name, pid)
    try:
      os.kill(pid, sig)
    except OSError as ex:
      if ex.errno == errno.ESRCH:
        # The process exited before we could kill it.
        return True
      raise

    if wait_timeout is not None:
      return self._wait_with_timeout(pid, starttime, wait_timeout)

    return True

  def _wait_with_timeout(self, pid, starttime, timeout):
    """Waits for the process to exit."""

    deadline = self._time_fn() + timeout
    while self._time_fn() < deadline:
      actual_starttime = self._read_starttime(pid)
      if actual_starttime is None:
        # The process isn't running any more.
        return True
      if actual_starttime != starttime:
        # This PID belongs to a different process now.
        return True

      self._sleep_fn(0.1)
    return False


class OwnService(Service):
  """A special service that represents the service_manager itself.

  Makes the is_running() and has_version_changed() functionality available for
  the service_manager process.
  """

  def __init__(self, state_directory, root_directory, **kwargs):
    super(OwnService, self).__init__(state_directory, {
        'name': 'service_manager',
        'tool': '',
        'root_directory': root_directory,
    }, **kwargs)
    self._state_directory = state_directory

  def start(self):
    """Writes a state file, returns False if we're already running."""

    # Use a flock here to avoid a race condition where two service_managers
    # start at the same time and both write their own state file.
    try:
      with daemon.flock('service_manager.flock', self._state_directory):
        if self.is_running():
          return False

        self._write_state_file(os.getpid())
        return True
    except daemon.LockAlreadyLocked:
      return False

  def stop(self):
    sys.exit()
