# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import glob
import json
import logging
import os
import os.path
import time

from infra.services.service_manager import service
from infra.services.service_manager import service_thread

LOGGER = logging.getLogger(__name__)


class _Metadata(object):
  def __init__(self, mtime, config=None, thread=None):
    self.mtime = mtime
    self.config = config
    self.thread = thread


class ConfigWatcher(object):
  """Polls a directory for .json files describing services to be run.

  Tries to keep the running services in sync with the config files - services
  are started immediately when valid configs are added, restarted when their
  configs change (adding or removing args for example), and stopped when the
  configs are deleted.
  """

  def __init__(self, config_directory, config_poll_interval,
               service_poll_interval, state_directory, root_directory,
               cloudtail_path,
               sleep_fn=time.sleep):
    """
    Args:
      config_directory: Directory containing .json config files to monitor.
      config_poll_interval: How often (in seconds) to poll config_directory
          for changes.
      service_poll_interval: How often (in seconds) to restart failed services.
      state_directory: A file will be created in this directory (with the same
          name as the service) when it is running containing its PID and
          starttime.
      cloudtail_path: Path to the cloudtail binary to use for logging, or None
          if logging is disabled.
    """

    self._config_glob = os.path.join(config_directory, '*.json')
    self._config_poll_interval = config_poll_interval
    self._service_poll_interval = service_poll_interval
    self._state_directory = state_directory
    self._cloudtail_path = cloudtail_path

    self._metadata = {}  # Filename -> _Metadata
    self._services = {}  # Service name -> Filename
    self._stop = False

    self._sleep_fn = sleep_fn

    self._own_service = service.OwnService(state_directory, root_directory)

  def run(self):
    """Runs continuously in this thread until stop() is called."""

    if not self._own_service.start():  # pragma: no cover
      # Another instance is already running.  Exit immediately to prevent the
      # ts_mon.close() in BaseApplication from being called.
      os._exit(0)

    while not self._stop:
      self._iteration()
      if not self._stop:  # pragma: no cover
        self._sleep_fn(self._config_poll_interval)

  def _iteration(self):
    """Runs one iteration of the loop.  Useful for testing."""

    own_state = self._own_service.get_running_process_state()
    if self._own_service.has_version_changed(own_state):
      logging.info("The service_manager's version has changed, exiting")
      self.stop()
      return

    files = set(glob.glob(self._config_glob))
    for filename in files:
      mtime = os.path.getmtime(filename)

      if filename in self._metadata:
        metadata = self._metadata[filename]
        if mtime == metadata.mtime:
          continue

        self._config_changed(filename, metadata, mtime)
      else:
        self._config_added(filename, mtime)

    for filename, metadata in self._metadata.iteritems():
      if filename not in files and metadata.config is not None:
        self._config_removed(metadata)

  def stop(self):
    """Signals that run() should stop on its next iteration."""

    self._stop = True
    for metadata in self._metadata.values():
      if metadata.thread is not None:
        metadata.thread.stop()

  def _load_config(self, filename):
    try:
      with open(filename) as fh:
        config = json.load(fh)
    except Exception:
      LOGGER.exception('Error opening or parsing %s', filename)
      return None

    return config

  def _config_added(self, filename, mtime):
    config = self._load_config(filename)

    if config is None:
      # Add a bad metadata entry so we don't call _config_added again every
      # time we read it.
      self._metadata[filename] = _Metadata(mtime)
      return

    if config['name'] in self._services:
      LOGGER.error('Duplicate service name "%s" (defined in %s and %s)' % (
          config['name'], self._services[config['name']], filename))
      return

    LOGGER.info('Adding new service config for %s', config['name'])

    thread = service_thread.ServiceThread(
        self._service_poll_interval,
        self._state_directory,
        config,
        self._cloudtail_path)
    thread.start()
    thread.start_service()
    self._metadata[filename] = _Metadata(mtime, config, thread)
    self._services[config['name']] = filename

  def _config_changed(self, filename, metadata, new_mtime):
    if metadata.config is not None:
      del self._services[metadata.config['name']]

    metadata.config = self._load_config(filename)
    metadata.mtime = new_mtime

    if (metadata.config is not None and
        metadata.config['name'] in self._services):
      LOGGER.error('Duplicate service name "%s" (defined in %s and %s)' % (
          metadata.config['name'],
          self._services[metadata.config['name']],
          filename))
      metadata.config = None

    if metadata.config is None:
      if metadata.thread is not None:
        metadata.thread.stop_service()
      return

    LOGGER.info('Updating service config for %s', metadata.config['name'])

    if metadata.thread is None:
      metadata.thread = service_thread.ServiceThread(
          self._service_poll_interval,
          self._state_directory,
          metadata.config,
          self._cloudtail_path)
      metadata.thread.start()
      metadata.thread.start_service()
    else:
      metadata.thread.restart_with_new_config(metadata.config)

    self._services[metadata.config['name']] = filename

  def _config_removed(self, metadata):
    LOGGER.info('Removing service config for %s', metadata.config['name'])

    del self._services[metadata.config['name']]

    metadata.config = None
    metadata.mtime = None
    metadata.thread.stop_service()
