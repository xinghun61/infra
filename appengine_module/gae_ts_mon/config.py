# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from google.appengine.api import modules
from google.appengine.api.app_identity import app_identity

from infra_libs.ts_mon import memcache_metric_store
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common import monitors
from infra_libs.ts_mon.common import targets

REGION = 'appengine'
PUBSUB_PROJECT = 'chrome-infra-mon-pubsub'
PUBSUB_TOPIC = 'monacq'


def initialize():
  if interface.state.global_monitor is not None:
    # Even if ts_mon was already initialized in this instance we should update
    # the metric index in case any new metrics have been registered.
    interface.state.store.update_metric_index()
    return

  # Use the application ID as the service name and the module name as the job
  # name.
  service_name = app_identity.get_application_id()
  job_name = modules.get_current_module_name()
  hostname = modules.get_current_version_name()

  interface.state.target = targets.TaskTarget(
      service_name, job_name, REGION, hostname)
  interface.state.flush_mode = 'auto'
  interface.state.store = memcache_metric_store.MemcacheMetricStore(
      interface.state)

  # Don't send metrics when running on the dev appserver.
  if os.environ.get('SERVER_SOFTWARE', '').startswith('Development'):
    logging.info('Using debug monitor')
    interface.state.global_monitor = monitors.DebugMonitor()
  else:
    logging.info('Using pubsub monitor %s/%s', PUBSUB_PROJECT, PUBSUB_TOPIC)
    interface.state.global_monitor = monitors.PubSubMonitor(
        monitors.APPENGINE_CREDENTIALS, PUBSUB_PROJECT, PUBSUB_TOPIC)

  logging.info('Initialized ts_mon with service_name=%s, job_name=%s, '
               'hostname=%s',
               service_name, job_name, hostname)

