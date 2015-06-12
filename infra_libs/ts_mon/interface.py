# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes representing the monitoring interface for tasks or devices.

Usage:
  import argparse
  from infra_libs import ts_mon

  p = argparse.ArgumentParser()
  ts_mon.add_argparse_options(p)
  args = p.parse_args()  # Must contain info for Monitor (and optionally Target)
  ts_mon.process_argparse_options(args)

  # Will use the default Target set up via command line args:
  m = ts_mon.BooleanMetric('/my/metric/name', fields={'foo': 1, 'bar': 'baz'})
  m.set(True)

  # Use a custom Target:
  t = ts_mon.TaskTarget('service', 'job', 'region', 'host')  # or DeviceTarget
  m2 = ts_mon.GaugeMetric('/my/metric/name2', fields={'asdf': 'qwer'}, target=t)
  m2.set(5)

Library usage:
  from infra_libs.ts_mon import CounterMetric
  # No need to set up Monitor or Target, assume calling code did that.
  c = CounterMetric('/my/counter', fields={'source': 'mylibrary'})
  c.set(0)
  for x in range(100):
    c.increment()
"""

import logging
import json
import os
import re
import socket
import sys
import threading
import time

from monacq.proto import metrics_pb2

from infra_libs.ts_mon import errors
from infra_libs.ts_mon import monitors
from infra_libs.ts_mon import targets


class State(object):
  """Package-level state is stored here so that it is easily accessible.

  Configuration is kept in this one object at the global level so that all
  libraries in use by the same tool or service can all take advantage of the
  same configuration.
  """

  def __init__(self):
    # The Monitor object that will be used to send all metrics.
    self.global_monitor = None
    # The Target object that will be paired with all metrics that don't supply
    # their own.
    self.default_target = None
    # The flush mode being used to control when metrics are pushed.
    self.flush_mode = None
    # The background thread that flushes metrics every
    # --ts-mon-flush-interval-secs seconds.  May be None if
    # --ts-mon-flush != 'auto' or --ts-mon-flush-interval-secs == 0.
    self.flush_thread = None
    # All metrics created by this application.
    self.metrics = set()

_state = State()


def add_argparse_options(parser):
  """Add monitoring related flags to a process' argument parser.

  Args:
    parser (argparse.ArgumentParser): the parser for the main process.
  """
  parser = parser.add_argument_group('Timeseries Monitoring Options')
  parser.add_argument(
      '--ts-mon-config-file',
      default='/etc/chrome-infra/ts-mon.json',
      help='path to a JSON config file that contains suitable values for '
           '"endpoint" and "credentials" for this machine. This config file is '
           'intended to be shared by all processes on the machine, as the '
           'values depend on the machine\'s position in the network, IP '
           'whitelisting and deployment of credentials. (default: %(default)s)')
  parser.add_argument(
      '--ts-mon-endpoint',
      help='url (including file://) to post monitoring metrics to. If set, '
           'overrides the value in --ts-mon-config-file')
  parser.add_argument(
      '--ts-mon-credentials',
      help='path to a pkcs8 json credential file. If set, overrides the value '
           'in --ts-mon-config-file')
  parser.add_argument(
      '--ts-mon-flush',
      choices=('all', 'manual', 'auto'), default='auto',
      help=('metric push behavior: all (send every metric individually), '
            'manual (only send when flush() is called), or auto (send '
            'automatically every --ts-mon-flush-interval-secs seconds). '
            '(default: %(default)s)'))
  parser.add_argument(
      '--ts-mon-flush-interval-secs',
      type=int,
      default=60,
      help=('automatically push metrics on this interval if '
            '--ts-mon-flush=auto.'))

  parser.add_argument(
      '--ts-mon-target-type',
      choices=('device', 'task'),
      default='device',
      help='the type of target that is being monitored ("device" or "task").'
           ' (default: %(default)s)')

  fqdn = socket.getfqdn()  # foo-[a|m]N.[chrome|golo].chromium.org
  host = fqdn.split('.')[0]  # foo-[a|m]N
  parser.add_argument(
      '--ts-mon-device-hostname',
      default=host,
      help='name of this device, (default: %(default)s')
  try:
    region = fqdn.split('.')[1]  # [chrome|golo]
  except IndexError:
    region = ''
  parser.add_argument(
      '--ts-mon-device-region',
      default=region,
      help='name of the region this devices lives in. (default: %(default)s)')
  try:
    # Regular expression that matches the vast majority of our host names.
    # Matches everything of the form 'masterN', 'masterNa', and 'foo-xN'.
    network = re.match(r'^([\w-]*?-[acm]|master)(\d+)a?$', host).group(2)  # N
  except AttributeError:
    network = ''
  parser.add_argument(
      '--ts-mon-device-network',
      default=network,
      help='name of the network this device is connected to. '
           '(default: %(default)s)')

  parser.add_argument(
      '--ts-mon-task-service-name',
      help='name of the service being monitored')
  parser.add_argument(
      '--ts-mon-task-job-name',
      help='name of this job instance of the task')
  parser.add_argument(
      '--ts-mon-task-region',
      default=region,
      help='name of the region in which this task is running '
           '(default: %(default)s)')
  parser.add_argument(
      '--ts-mon-task-hostname',
      default=host,
      help='name of the host on which this task is running '
           '(default: %(default)s)')
  parser.add_argument(
      '--ts-mon-task-number', type=int, default=0,
      help='number (e.g. for replication) of this instance of this task '
           '(default: %(default)s)')


def load_machine_config(filename):
  if not os.path.exists(filename):
    logging.info('Configuration file does not exist, ignoring: %s', filename)
    return {}

  try:
    with open(filename) as fh:
      return json.load(fh)
  except Exception:
    logging.error('Configuration file couldn\'t be read: %s', filename)
    raise


def process_argparse_options(args):
  """Process command line arguments to initialize the global monitor.

  Also initializes the default target if sufficient arguments are supplied.
  If they aren't, all created metrics will have to supply their own target.
  This is generally a bad idea, as many libraries rely on the default target
  being set up.

  Starts a background thread to automatically flush monitoring metrics if not
  disabled by command line arguments.

  Args:
    args (argparse.Namespace): the result of parsing the command line arguments
  """

  # Parse the config file if it exists.
  config = load_machine_config(args.ts_mon_config_file)
  endpoint = config.get('endpoint', '')
  credentials = config.get('credentials', '')

  # Command-line args override the values in the config file.
  if args.ts_mon_endpoint:
    endpoint = args.ts_mon_endpoint
  if args.ts_mon_credentials:
    credentials = args.ts_mon_credentials

  if endpoint.startswith('file://'):
    _state.global_monitor = monitors.DiskMonitor(endpoint[len('file://'):])
  elif credentials:
    _state.global_monitor = monitors.ApiMonitor(credentials, endpoint)
  else:
    logging.error('Monitoring is disabled because --ts-mon-credentials was not '
                  'set')
    _state.global_monitor = monitors.NullMonitor()

  if args.ts_mon_target_type == 'device':
    _state.default_target = targets.DeviceTarget(
        args.ts_mon_device_region,
        args.ts_mon_device_network,
        args.ts_mon_device_hostname)
  if args.ts_mon_target_type == 'task':  # pragma: no cover
    # Reimplement ArgumentParser.error, since we don't have access to the parser
    if not args.ts_mon_task_service_name:
      print >> sys.stderr, ('Argument --ts-mon-task-service-name must be '
                            'provided when the target type is "task".')
      sys.exit(2)
    if not args.ts_mon_task_job_name:  # pragma: no cover
      print >> sys.stderr, ('Argument --ts-mon-task-job-name must be provided '
                            'when the target type is "task".')
      sys.exit(2)
    _state.default_target = targets.TaskTarget(
        args.ts_mon_task_service_name,
        args.ts_mon_task_job_name,
        args.ts_mon_task_region,
        args.ts_mon_task_hostname,
        args.ts_mon_task_number)

  _state.flush_mode = args.ts_mon_flush

  if args.ts_mon_flush == 'auto':
    _state.flush_thread = _FlushThread(args.ts_mon_flush_interval_secs)
    _state.flush_thread.start()


def send(metric):
  """Send a single metric to the monitoring api.

  This is called automatically by Metric.set - you don't need to call it
  manually.
  """
  if _state.flush_mode != 'all':
    return

  if not _state.global_monitor:
    raise errors.MonitoringNoConfiguredMonitorError(metric._name)

  proto = metrics_pb2.MetricsCollection()
  metric.serialize_to(proto, default_target=_state.default_target)
  _state.global_monitor.send(proto)


def flush():
  """Send all metrics that are registered in the application."""
  if not _state.global_monitor:
    raise errors.MonitoringNoConfiguredMonitorError(None)

  proto = metrics_pb2.MetricsCollection()
  for metric in _state.metrics:
    metric.serialize_to(proto, default_target=_state.default_target)

  _state.global_monitor.send(proto)


def register(metric):
  """Adds the metric to the list of metrics sent by flush().

  This is called automatically by Metric's constructor - you don't need to call
  it manually.
  """
  # If someone is registering the same metric object twice, that's okay, but
  # registering two different metric objects with the same metric name is not.
  if metric in _state.metrics:
    return
  if any([metric._name == m._name for m in _state.metrics]):
    raise errors.MonitoringDuplicateRegistrationError(metric._name)

  _state.metrics.add(metric)


def unregister(metric):
  """Removes the metric from the list of metrics sent by flush()."""
  _state.metrics.remove(metric)


def close():  # pragma: no cover
  """Stops any background threads and waits for them to exit."""
  if _state.flush_thread is not None:
    _state.flush_thread.stop()


class _FlushThread(threading.Thread):  # pragma: no cover
  """Background thread that flushes metrics on an interval."""

  def __init__(self, interval_secs, stop_event=None):
    super(_FlushThread, self).__init__(name='ts_mon')

    if stop_event is None:
      stop_event = threading.Event()

    self.daemon = True
    self.interval_secs = interval_secs
    self.stop_event = stop_event

  def _flush_and_log_exceptions(self):
    try:
      flush()
    except Exception:
      logging.exception('Automatic monitoring flush failed.')

  def run(self):
    next_timeout = self.interval_secs
    while True:
      if self.stop_event.wait(next_timeout):
        self._flush_and_log_exceptions()
        return

      # Try to flush every N seconds exactly so rate calculations are more
      # consistent.
      start = time.time()
      self._flush_and_log_exceptions()
      flush_duration = time.time() - start
      next_timeout = self.interval_secs - flush_duration

      if next_timeout < 0:
        logging.warning(
            'Last monitoring flush took %f seconds (longer than '
            '--ts-mon-flush-interval-secs = %f seconds)',
            flush_duration, self.interval_secs)
        next_timeout = 0

  def stop(self):
    """Stops the background thread and performs a final flush."""

    self.stop_event.set()
    self.join()
