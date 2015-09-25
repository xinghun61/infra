# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import logging
import threading

from infra.services.service_manager import service
from infra_libs import ts_mon

LOGGER = logging.getLogger(__name__)


class _State(object):
  def __init__(self):
    self.should_run = None
    self.exit = False
    self.new_config = None

  def clone(self):
    ret = _State()
    ret.should_run = self.should_run
    ret.exit = self.exit
    ret.new_config = self.new_config
    return ret


class ServiceThread(threading.Thread):
  """Thread that controls a single Service object.

  The methods on this object (start_service(), stop_service(), etc.) can be
  called from any thread and are asynchronous - they just instruct the thread to
  perform the given action on the Service.

  This thread also polls the service occasionally and restarts it if it crashed.
  """

  failures = ts_mon.CounterMetric('service_manager/failures')
  reconfigs = ts_mon.CounterMetric('service_manager/reconfigs')
  upgrades = ts_mon.CounterMetric('service_manager/upgrades')

  def __init__(self, poll_interval, state_directory, service_config,
               cloudtail_path,
               wait_condition=None):
    """
    Args:
      poll_interval: How often (in seconds) to restart failed services.
      state_directory: A file will be created in this directory (with the same
          name as the service) when it is running containing its PID and
          starttime.
      service_config: A dictionary containing the service's config.  See README
          for a description of the fields.
      cloudtail_path: Path to the cloudtail binary to use for logging, or None
          if logging is disabled.
    """

    super(ServiceThread, self).__init__()

    if wait_condition is None:  # pragma: no cover
      wait_condition = threading.Condition()

    self._poll_interval = poll_interval
    self._state_directory = state_directory
    self._cloudtail_path = cloudtail_path
    self._service = service.Service(self._state_directory,
                                    service_config,
                                    self._cloudtail_path)

    self._condition = wait_condition  # Protects _state.
    self._state = _State()  # _condition must be held.
    self._state_changed = False

    self._started = False  # Whether we started the service already.

  def _wait(self):
    with self._condition:
      if not self._state_changed:  # pragma: no cover
        self._condition.wait(self._poll_interval)

      # Clone the state object so we can release the lock.
      ret = self._state.clone()
      self._state.new_config = None
      self._state_changed = False
      return ret

  @contextlib.contextmanager
  def _change_state(self):
    with self._condition:
      yield
      self._state_changed = True
      self._condition.notify()

  def run(self):
    while True:
      try:
        state = self._wait()

        if state.exit:
          return
        elif state.new_config is not None:
          # Stop the service if it's currently running.
          self._service.stop()

          # Recreate it with the new config and start it.
          self.reconfigs.increment(fields={'service': self._service.name})
          self._service = service.Service(self._state_directory,
                                          state.new_config,
                                          self._cloudtail_path)
          self._service.start()
          self._started = True
        elif state.should_run == False:
          # Ensure the service is stopped.
          self._service.stop()
          self._started = False
        elif state.should_run == True:
          try:
            state = self._service.get_running_process_state()
          except service.UnexpectedProcessStateError:
            self.failures.increment(fields={'service': self._service.name})
            logging.exception('Unexpected error getting state for service %s',
                self._service.name)
          except service.ProcessNotRunning as ex:
            if self._started:
              # We started it last time but it's not running any more.
              self.failures.increment(fields={'service': self._service.name})
              LOGGER.warning('Service %s failed (%r), restarting',
                             self._service.name, ex)
            else:
              # We're about to start it for the first time.
              LOGGER.info('Starting service %s for the first time (%r)',
                          self._service.name, ex)
          else:
            if self._service.has_version_changed(state):
              self.upgrades.increment(fields={'service': self._service.name})
              LOGGER.info('Service %s has a new package version, restarting',
                          self._service.name)
              self._service.stop()
            elif self._service.has_args_changed(state):
              self.reconfigs.increment(fields={'service': self._service.name})
              LOGGER.info('Service %s has new args: was %s, restarting with %s',
                          self._service.name, state.args, self._service.args)
              self._service.stop()

          # Ensure the service is running.
          self._service.start()
          self._started = True

      except Exception:
        LOGGER.exception('Service thread failed for service %s',
                         self._service.name)

  def start_service(self):
    with self._change_state():
      self._state.should_run = True

  def stop_service(self):
    with self._change_state():
      self._state.should_run = False

  def stop(self, join=True):
    with self._change_state():
      self._state.exit = True

    if join:  # pragma: no cover
      self.join()

  def restart_with_new_config(self, new_config):
    with self._change_state():
      self._state.new_config = new_config
      self._state.should_run = True
