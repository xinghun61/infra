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
import os
import re
import socket

from monacq import acquisition_api
from monacq.proto import metrics_pb2

from infra.libs.ts_mon.errors import MonitoringNoConfiguredMonitorError
from infra.libs.ts_mon.errors import MonitoringNoConfiguredTargetError
from infra.libs.ts_mon.target import DeviceTarget, TaskTarget


# The global monitor that will be used to send all metrics.
_global_monitor = None

# The default target that will be paired with all metrics that don't supply
# their own.
_default_target = None


def add_argparse_options(parser):
  """Add monitoring related flags to a process' argument parser.

  Args:
    parser (argparse.ArgumentParser): the parser for the main process.
  """
  parser.add_argument(
      '--ts-mon-endpoint',
      default='https://www.googleapis.com/acquisitions/v1_mon_shared/storage',
      help='url to post monitoring metrics to')
  parser.add_argument(
      '--ts-mon-credentials',
      help='path to a pkcs8 json credential file')

  parser.add_argument(
      '--ts-mon-target-type',
      choices=['device', 'task'],
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
  global _global_monitor
  global _default_target
  _global_monitor = Monitor(args.ts_mon_credentials, args.ts_mon_endpoint)

  if args.ts_mon_target_type == 'device':
    _default_target = DeviceTarget(
        args.ts_mon_device_region,
        args.ts_mon_device_network,
        args.ts_mon_device_hostname)
  if args.ts_mon_target_type == 'task':
    _default_target = TaskTarget(
        args.ts_mon_task_service_name,
        args.ts_mon_task_job_name,
        args.ts_mon_task_region,
        args.ts_mon_task_hostname,
        args.ts_mon_task_number)


def send(metric):
  """Send a metric (with its current value and fields) to the monitoring api.

  Raises:
    MonitoringNoConfiguredMonitorError: if the global Monitor doesn't exist
  """
  if not _global_monitor:
    raise MonitoringNoConfiguredMonitorError(metric._name)
  _global_monitor.send(metric)


def _logging_callback(resp, content):  # pragma: no cover
  logging.debug(repr(resp))
  logging.debug(content)


class Monitor(object):
  """Class encapsulating the ability to send metrics to the api.

  This is a singleton class. There should only be one instance of a Monitor at
  a time. It will be created and initialized by process_argparse_options. It
  must exist in order for any metrics to be sent, although both Targets and
  Metrics may be initialized before the underlying Monitor. If it does not exist
  at the time that a Metric is sent, an exception will be raised.
  """
  def __init__(self, credsfile, endpoint):
    """Process monitoring related command line flags and initialize api.

    Args:
      credsfile (str): path to the credentials json file
      endpoint (str): url of the monitoring endpoint to hit
    """
    creds = acquisition_api.AcquisitionCredential.Load(
        os.path.abspath(credsfile))
    api = acquisition_api.AcquisitionApi(creds, endpoint)
    api.SetResponseCallback(_logging_callback)
    self._api = api

  def send(self, metric):
    """Send a metric proto to the monitoring api.

    Args:
      metric (Metric): the Metric to send

    Raises:
      MonitoringNoConfiguredTargetError: if there is no Target object
    """
    # TODO(agable): start using the /crit/ prefix when we have real quota,
    # instead of just using the crit/ subspace of /acquisitions/monitoring/.
    metric_pb = metrics_pb2.MetricsData(name='crit/' + metric._name)

    metric._populate_metric_pb(metric_pb)
    metric._populate_fields_pb(metric_pb)

    if metric._target:
      metric._target._populate_target_pb(metric_pb)
    elif _default_target:
      _default_target._populate_target_pb(metric_pb)
    else:
      raise MonitoringNoConfiguredTargetError(metric._name)

    self._api.Send(metrics_pb2.MetricsCollection(data=[metric_pb]))
