# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import copy
import datetime
import logging
import os
import sys
import time
import threading

import webapp2

from google.appengine.api import modules
from google.appengine.api.app_identity import app_identity
from google.appengine.api import namespace_manager
from google.appengine.api import runtime
from google.appengine.ext import ndb

from infra_libs.ts_mon.common import http_metrics
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common import metric_store
from infra_libs.ts_mon.common import metrics
from infra_libs.ts_mon.common import monitors
from infra_libs.ts_mon.common import targets

REGION = 'appengine'
PUBSUB_PROJECT = 'chrome-infra-mon-pubsub'
PUBSUB_TOPIC = 'monacq'
INSTANCE_NAMESPACE = 'ts_mon_instance_namespace'
# Duration of inactivity to consider an instance dead.
INSTANCE_EXPIRE_SEC = 30 * 60
INSTANCE_EXPECTED_TO_HAVE_TASK_NUM_SEC = 5 * 60
INTERNAL_CALLBACK_NAME = '__gae_ts_mon_callback'


appengine_default_version = metrics.StringMetric(
    'appengine/default_version',
    description='Name of the version currently marked as default.')
started_counter = metrics.CounterMetric(
    'appengine/instances/started',
    description='Count the number of GAE instance initializations.')
shutdown_counter = metrics.CounterMetric(
    'appengine/instances/shutdown',
    description='Count the number of GAE instance shutdowns.')


global_metrics = {}
flush_callbacks = {}


def reset_for_unittest():
  global global_metrics
  global flush_callbacks
  global_metrics = {}
  flush_callbacks = {}


def register_global_metrics(metrics):
  """Declare metrics as global.

  Registering a metric as "global" simply means it will be reset every
  time the metric is sent. This allows any instance to send such a
  metric to a shared stream, e.g. by overriding target fields like
  task_num (instance ID), host_name (version) or job_name (module
  name).

  There is no "unregister". Multiple calls add up. It only needs to be
  called once, similar to gae_ts_mon.initialize().

  Args:
    metrics (iterable): a collection of Metric objects.
  """
  global_metrics.update({m.name: m for m in metrics})


def register_global_metrics_callback(name, callback):
  """Register a named function to compute global metrics values.

  There can only be one callback for a given name. Setting another
  callback with the same name will override the previous one. To disable
  a callback, set its function to None.

  Args:
    name (string): name of the callback.
    callback (function): this function will be called without arguments
      every minute from the gae_ts_mon cron job. It is intended to set the
      values of the global metrics.
  """
  if not callback:
    if name in flush_callbacks:
      del flush_callbacks[name]
  else:
    flush_callbacks[name] = callback


class Instance(ndb.Model):
  """Used to map instances to small integers.

  Each instance "owns" an entity with the key <instance-id>.<version>.<module>.
  `task_num` is a mapping assigned by a cron job to the instance; -1=undefined.
  """
  task_num = ndb.IntegerProperty(default=-1)
  last_updated = ndb.DateTimeProperty(auto_now_add=True)


def _instance_key_id():
  return '%s.%s.%s' % (
      modules.get_current_instance_id(),
      modules.get_current_version_name(),
      modules.get_current_module_name())


@contextlib.contextmanager
def instance_namespace_context():
  previous_namespace = namespace_manager.get_namespace()
  try:
    namespace_manager.set_namespace(INSTANCE_NAMESPACE)
    yield
  finally:
    namespace_manager.set_namespace(previous_namespace)


def _get_instance_entity():
  with instance_namespace_context():
    return Instance.get_or_insert(_instance_key_id())


def _reset_cumulative_metrics():
  """Clear the state when an instance loses its task_num assignment."""
  logging.warning('Instance %s got purged from Datastore, but is still alive. '
                  'Clearing cumulative metrics.', _instance_key_id())
  for _target, metric, start_time, _fields in interface.state.store.get_all():
    if metric.is_cumulative():
      metric.reset()


_flush_metrics_lock = threading.Lock()


def flush_metrics_if_needed(time_fn=datetime.datetime.utcnow):
  time_now = time_fn()
  minute_ago = time_now - datetime.timedelta(seconds=60)
  if interface.state.last_flushed > minute_ago:
    return False
  # Do not hammer Datastore if task_num is not yet assigned.
  interface.state.last_flushed = time_now
  with _flush_metrics_lock:
    return _flush_metrics_if_needed_locked(time_now)


def _flush_metrics_if_needed_locked(time_now):
  """Return True if metrics were actually sent."""
  entity = _get_instance_entity()
  if entity.task_num < 0:
    if interface.state.target.task_num >= 0:
      _reset_cumulative_metrics()
    interface.state.target.task_num = -1
    interface.state.last_flushed = entity.last_updated
    updated_sec_ago = (time_now - entity.last_updated).total_seconds()
    if updated_sec_ago > INSTANCE_EXPECTED_TO_HAVE_TASK_NUM_SEC:
      logging.warning('Instance %s is %n seconds old with no task_num.',
                      _instance_key_id(), updated_sec_ago)
    return False
  interface.state.target.task_num = entity.task_num

  entity.last_updated = time_now
  entity_deferred = entity.put_async()

  interface.flush()

  for metric in global_metrics.itervalues():
    metric.reset()

  entity_deferred.get_result()
  return True


def _shutdown_hook():
  if flush_metrics_if_needed():
    logging.info('Shutdown hook: deleting %s, metrics were flushed.',
                 _instance_key_id())
  else:
    logging.warning('Shutdown hook: deleting %s, metrics were NOT flushed.',
                    _instance_key_id())
  with instance_namespace_context():
    ndb.Key('Instance', _instance_key_id()).delete()


def _internal_callback():
  for module_name in modules.get_modules():
    target_fields = {
        'task_num': 0,
        'hostname': '',
        'job_name': module_name,
    }
    appengine_default_version.set(modules.get_default_version(module_name),
                                  target_fields=target_fields)


def initialize(app=None, enable=True, is_local_unittest=None):
  if is_local_unittest is None:  # pragma: no cover
    # Since gae_ts_mon.initialize is called at module-scope by appengine apps,
    # AppengineTestCase.setUp() won't have run yet and none of the appengine
    # stubs will be initialized, so accessing Datastore or even getting the
    # application ID will fail.
    is_local_unittest = ('expect_tests' in sys.argv[0])

  if enable and app is not None:
    instrument_wsgi_application(app)

  # Use the application ID as the service name and the module name as the job
  # name.
  if is_local_unittest:  # pragma: no cover
    service_name = 'unittest'
    job_name = 'unittest'
    hostname = 'unittest'
  else:
    service_name = app_identity.get_application_id()
    job_name = modules.get_current_module_name()
    hostname = modules.get_current_version_name()
    _get_instance_entity()  # Create an Instance entity.
    runtime.set_shutdown_hook(_shutdown_hook)

  interface.state.target = targets.TaskTarget(
      service_name, job_name, REGION, hostname, task_num=-1)
  interface.state.flush_mode = 'manual'
  interface.state.last_flushed = datetime.datetime.utcnow()

  # Don't send metrics when running on the dev appserver.
  if (is_local_unittest or
      os.environ.get('SERVER_SOFTWARE', '').startswith('Development')):
    logging.info('Using debug monitor')
    interface.state.global_monitor = monitors.DebugMonitor()
  else:
    logging.info('Using pubsub monitor %s/%s', PUBSUB_PROJECT, PUBSUB_TOPIC)
    interface.state.global_monitor = monitors.PubSubMonitor(
        monitors.APPENGINE_CREDENTIALS, PUBSUB_PROJECT, PUBSUB_TOPIC)

  register_global_metrics([appengine_default_version])
  register_global_metrics_callback(INTERNAL_CALLBACK_NAME, _internal_callback)

  logging.info('Initialized ts_mon with service_name=%s, job_name=%s, '
               'hostname=%s',
               service_name, job_name, hostname)


def _instrumented_dispatcher(dispatcher, request, response, time_fn=time.time):
  start_time = time_fn()
  response_status = 0
  interface.state.store.initialize_context()
  try:
    ret = dispatcher(request, response)
  except webapp2.HTTPException as ex:
    response_status = ex.code
    raise
  except Exception:
    response_status = 500
    raise
  else:
    if isinstance(ret, webapp2.Response):
      response = ret
    response_status = response.status_int
  finally:
    elapsed_ms = int((time_fn() - start_time) * 1000)

    fields = {'status': response_status, 'name': '', 'is_robot': False}
    if request.route is not None:
      # Use the route template regex, not the request path, to prevent an
      # explosion in possible field values.
      fields['name'] = request.route.template
    if request.user_agent is not None:
      # We must not log user agents, but we can store whether or not the
      # user agent string indicates that the requester was a Google bot.
      fields['is_robot'] = (
          'GoogleBot' in request.user_agent or
          'GoogleSecurityScanner' in request.user_agent)

    http_metrics.server_durations.add(elapsed_ms, fields=fields)
    http_metrics.server_response_status.increment(fields=fields)
    if request.content_length is not None:
      http_metrics.server_request_bytes.add(request.content_length,
                                            fields=fields)
    if response.content_length is not None:  # pragma: no cover
      http_metrics.server_response_bytes.add(response.content_length,
                                             fields=fields)
    flush_metrics_if_needed()

  return ret


def instrument_wsgi_application(app, time_fn=time.time):
  # Don't instrument the same router twice.
  if hasattr(app.router, '__instrumented_by_ts_mon'):
    return

  old_dispatcher = app.router.dispatch

  def dispatch(router, request, response):
    return _instrumented_dispatcher(old_dispatcher, request, response,
                                    time_fn=time_fn)

  app.router.set_dispatcher(dispatch)
  app.router.__instrumented_by_ts_mon = True
