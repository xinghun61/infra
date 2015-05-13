# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes representing the monitoring interface for tasks or devices.

Usage:
  import argparse
  from infra.libs import ts_mon

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
  from infra.libs.ts_mon import CounterMetric
  # No need to set up Monitor or Target, assume calling code did that.
  c = CounterMetric('/my/counter', fields={'source': 'mylibrary'})
  c.set(0)
  for x in range(100):
    c.increment()
"""

import logging
import re
import socket
import sys

from monacq.proto import metrics_pb2

from infra.libs.ts_mon.errors import MonitoringDuplicateRegistrationError
from infra.libs.ts_mon.errors import MonitoringNoConfiguredMonitorError
from infra.libs.ts_mon.monitor import ApiMonitor, DiskMonitor, NullMonitor
from infra.libs.ts_mon.target import DeviceTarget, TaskTarget


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
      '--ts-mon-endpoint',
      default='https://www.googleapis.com/acquisitions/v1_mon_shared/storage',
      help='url (including file://) to post monitoring metrics to.'
           ' (default: %(default)s)')
  parser.add_argument(
      '--ts-mon-credentials',
      help='path to a pkcs8 json credential file')
  parser.add_argument(
      '--ts-mon-flush',
      choices=('all', 'manual'), default='manual',
      help=('metric push behavior: all (send every metric individually), or '
            'manual (only send when flush() is called). '
            '(default: %(default)s)'))

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


def process_argparse_options(args):
  """Process command line arguments to initialize the global monitor.

  Also initializes the default target if sufficient arguments are supplied.
  If they aren't, all created metrics will have to supply their own target.
  This is generally a bad idea, as many libraries rely on the default target
  being set up.

  Args:
    args (argparse.Namespace): the result of parsing the command line arguments
  """
  if args.ts_mon_endpoint.startswith('file://'):
    _state.global_monitor = DiskMonitor(args.ts_mon_endpoint[len('file://'):])
  elif args.ts_mon_credentials:
    _state.global_monitor = ApiMonitor(args.ts_mon_credentials,
                                       args.ts_mon_endpoint)
  else:
    logging.warning('Monitoring is disabled because --ts-mon-credentials was '
                    'not set')
    _state.global_monitor = NullMonitor()

  if args.ts_mon_target_type == 'device':
    _state.default_target = DeviceTarget(
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
    _state.default_target = TaskTarget(
        args.ts_mon_task_service_name,
        args.ts_mon_task_job_name,
        args.ts_mon_task_region,
        args.ts_mon_task_hostname,
        args.ts_mon_task_number)

  _state.flush_mode = args.ts_mon_flush


def send(metric):
  """Send a single metric to the monitoring api.

  This is called automatically by Metric.set - you don't need to call it
  manually.
  """
  if _state.flush_mode != 'all':
    return

  if not _state.global_monitor:
    raise MonitoringNoConfiguredMonitorError(metric._name)

  proto = metrics_pb2.MetricsCollection()
  metric.serialize_to(proto, default_target=_state.default_target)
  _state.global_monitor.send(proto)


def flush():
  """Send all metrics that are registered in the application."""
  if not _state.global_monitor:
    raise MonitoringNoConfiguredMonitorError(None)

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
    raise MonitoringDuplicateRegistrationError(metric._name)

  _state.metrics.add(metric)


def unregister(metric):
  """Removes the metric from the list of metrics sent by flush()."""
  _state.metrics.remove(metric)
