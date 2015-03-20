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

import collections
import copy
import logging
import re
import socket

from infra.libs.ts_mon.errors import MonitoringNoConfiguredMonitorError
from infra.libs.ts_mon.monitor import ApiMonitor, DiskMonitor
from infra.libs.ts_mon.target import DeviceTarget, TaskTarget


Config = collections.namedtuple(
  # Package-level configuration is stored here so that it is easily accessible.
  # Configuration is kept in this one object at the global level so that all
  # libraries in use by the same tool or service can all take advantage of the
  # same configuration.
  'Config',
  [
    # The Monitor object that will be used to send all metrics.
    'global_monitor',
    # The Target object that will be paired with all metrics that don't supply
    # their own.
    'default_target',
    # The flush mode being used to control when metrics are pushed.
    'flush_mode',
    # The collection of metrics which have been stored but not yet flushed.
    'metric_store',
  ]
)
_config = Config(None, None, None, [])


def add_argparse_options(parser):
  """Add monitoring related flags to a process' argument parser.

  Args:
    parser (argparse.ArgumentParser): the parser for the main process.
  """
  parser.add_argument(
      '--ts-mon-endpoint',
      default='https://www.googleapis.com/acquisitions/v1_mon_shared/storage',
      help='url (including file://) to post monitoring metrics to')
  parser.add_argument(
      '--ts-mon-credentials',
      help='path to a pkcs8 json credential file')
  parser.add_argument(
      '--ts-mon-flush',
      choices=('all', 'manual'), default='all',
      help=('metric push behavior: all (send every metric individually), or '
            'manual (only send when flush() is called)'))

  parser.add_argument(
      '--ts-mon-target-type',
      choices=('device', 'task'),
      default='device',
      help='the type of target that is being monitored ("device" or "task")')

  fqdn = socket.getfqdn()  # foo-[a|m]N.[chrome|golo].chromium.org
  host = fqdn.split('.')[0]  # foo-[a|m]N
  parser.add_argument(
      '--ts-mon-device-hostname',
      default=host,
      help='name of this device')
  try:
    region = fqdn.split('.')[1]  # [chrome|golo]
  except IndexError:
    region = ''
  parser.add_argument(
      '--ts-mon-device-region',
      default=region,
      help='name of the region this devices lives in')
  try:
    network = re.match(r'\w*?(\d+)$', host).group(1)  # N
  except AttributeError:
    network = ''
  parser.add_argument(
      '--ts-mon-device-network',
      default=network,
      help='name of the network this device is connected to')

  parser.add_argument(
      '--ts-mon-task-service-name',
      help='name of the service being monitored')
  parser.add_argument(
      '--ts-mon-task-job-name',
      help='name of this job instance of the task')
  parser.add_argument(
      '--ts-mon-task-region',
      default=region,
      help='name of the region in which this task is running')
  parser.add_argument(
      '--ts-mon-task-hostname',
      default=host,
      help='name of the host on which this task is running')
  parser.add_argument(
      '--ts-mon-task-number', type=int,
      help='number (e.g. for replication) of this instance of this task')


def process_argparse_options(args):
  """Process command line arguments to initialize the global monitor.

  Also initializes the default target if sufficient arguments are supplied.
  If they aren't, all created metrics will have to supply their own target.
  This is generally a bad idea, as many libraries rely on the default target
  being set up.

  Args:
    args (argparse.Namespace): the result of parsing the command line arguments
  """
  global _config

  if args.ts_mon_endpoint.startswith('file://'):
    global_monitor = DiskMonitor(args.ts_mon_endpoint[len('file://'):])
  else:
    global_monitor = ApiMonitor(args.ts_mon_credentials,
                                         args.ts_mon_endpoint)

  if args.ts_mon_target_type == 'device':
    default_target = DeviceTarget(
        args.ts_mon_device_region,
        args.ts_mon_device_network,
        args.ts_mon_device_hostname)
  if args.ts_mon_target_type == 'task':
    default_target = TaskTarget(
        args.ts_mon_task_service_name,
        args.ts_mon_task_job_name,
        args.ts_mon_task_region,
        args.ts_mon_task_hostname,
        args.ts_mon_task_number)

  flush_mode = args.ts_mon_flush

  _config = Config(global_monitor, default_target, flush_mode, [])


def send(metric, fields=None):
  """Send a metric (with its current value and fields) to the monitoring api.

  In general, metrics are sent by calling their own .set() or related methods,
  which both set a value and send that new value, but this can be used to send
  the current value without setting a new one.

  Args:
    fields (dict): a key-value mapping of additional metric fields to send

  Raises:
    MonitoringNoConfiguredMonitorError: if the global Monitor doesn't exist
    MonitoringTooManyFieldsError: if the extra fields put the total over 7
  """
  if not _config.global_monitor:
    raise MonitoringNoConfiguredMonitorError(metric._name)

  proto = metric.serialize(fields=fields, default_target=_config.default_target)
  if _config.flush_mode == 'all':
    _config.global_monitor.send(proto)
  else:
    _config.metric_store.append(proto)


def flush():
  """Send all metrics which have been stored since the last flush()."""
  if _config.flush_mode != 'manual':  # pragma: no cover
    logging.warn('Manual flush() being called when flush mode is %s.',
                 _config.flush_mode)

  store_copy = copy.copy(_config.metric_store)
  _config.global_monitor.send(store_copy)
  _config.metric_store = _config.metric_store[len(store_copy):]
