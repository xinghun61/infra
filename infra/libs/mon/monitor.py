# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes representing the monitoring interface for tasks or devices.

Usage:
  import argparse
  from infra.libs import mon

  p = argparse.ArgumentParser()
  mon.add_argparse_flags(p)
  args = p.parse_args()

  t = mon.TaskMonitor('service', 'job', 'region', 'host')  # or DeviceMonitor
  t.process_argparse_flags(args)

  t.send('metric', 'value', {'field1': 1, 'field2': 2})
"""


import logging
import os

from monacq import acquisition_api
from monacq.proto import acquisition_task_pb2, acquisition_network_device_pb2
from monacq.proto import metrics_pb2


class MonitoringError(Exception):
  """Base class for exceptions raised by this module."""


class MonitoringInvalidValueTypeError(MonitoringError):
  """Raised when sending a metric value is not a valid type."""

  def __init__(self, metric, value):
    self.metric = metric
    self.value = value
    super(MonitoringInvalidValueTypeError, self).__init__()

  def __str__(self):
    return 'Metric "%s" was given invalid value "%s" (%s).' % (
        self.metric, self.value, type(self.value))


class MonitoringTooManyFieldsError(MonitoringError):
  """Raised when sending a metric with more than 7 fields."""

  def __init__(self, metric, fields):
    self.metric = metric
    self.fields = fields
    super(MonitoringTooManyFieldsError, self).__init__()

  def __str__(self):
    return 'Metric "%s" was given too many (%d > 7) fields: %s.' % (
        self.metric, len(self.fields), self.fields)


class MonitoringInvalidFieldTypeError(MonitoringError):
  """Raised when sending a metric with a field value of an invalid type."""

  def __init__(self, metric, field, value):
    self.metric = metric
    self.field = field
    self.value = value
    super(MonitoringInvalidFieldTypeError, self).__init__()

  def __str__(self):
    return 'Metric "%s" was given field "%s" with invalid value "%s" (%s).' % (
        self.metric, self.field, self.value, type(self.value))


def _logging_callback(resp, content):
  logging.debug(repr(resp))
  logging.debug(content)


def add_argparse_options(parser):
  """Add monitoring related flags to a process' argument parser.

  Args:
    parser (argparse.ArgumentParser): the parser for the main process.
  """
  parser.add_argument(
      '--monitoring-endpoint',
      default='https://www.googleapis.com/acquisitions/v1_mon_shared/storage',
      help='url to post monitoring metrics to')
  parser.add_argument(
      '--monitoring-creds',
      help='path to a pkcs8 json credential file')


class Monitor(object):
  """Abstract base class for a monitoring interface.

  Use the concrete child classes instead:
  * TaskMonitor to monitor a job or tasks running in (potentially) many places;
  * DeviceMonitor to monitor a host machine that may be running a task.
  """

  def __init__(self):
    """Create a Monitor object and initialize internal state."""
    self._api = None
    self._target = None
    self._response_callback = _logging_callback

  def _populate_target(self, metric):
    """Populate the 'target' embedded message field of a metric protobuf."""
    raise NotImplementedError()

  def process_argparse_options(self, args):
    """Process monitoring related command line flags and initialize api.

    Args:
      args (argparse.Namespace): the result of parsing the command line.
    """
    # TODO(agable): Consider creating a top-level process_argparse_options which
    # can handle TaskMonitor- or DeviceMonitor-specific args and return
    # a Monitor object of the appropriate type. Args-processor as factory.
    creds = acquisition_api.AcquisitionCredential.Load(
        os.path.abspath(args.monitoring_creds))
    api = acquisition_api.AcquisitionApi(creds, args.monitoring_endpoint)
    api.SetResponseCallback(self._response_callback)
    self._api = api

  def send(self, name, value, fields=None, start_time=None):
    """Send a metric proto to the monitoring api.

    Takes a name, a value, and up to seven key/value pairs called "fields".
    Also takes an optional start timestamp, which will indicate that the value
    should be monotonically increasing since the given timestamp.
    If the value is a __, it will be translated into a __:
    * string                   --> string_value
    * bool                     --> boolean_value
    * int with start time      --> counter
    * int without start time   --> gauge
    * float with start time    --> noncumulative_double_value
    * float without start time --> cumulative_double_value

    Args:
      name (str): the name of the metric
      value: the value to send (see description of value types above)
      fields (dict): mapping of metadata string keys to string/int/bool values
      start_time (int): milliseconds between the epoch and when this cumulative
                        stream started

    Raises:
      MonitoringInvalidValueTypeError: if the value is not a valid type
      MonitoringTooManyFieldsError: if more than 7 fields are supplied
      MonitoringInvalidFieldTypeError: if a field value is not a valid type
    """
    # TODO(agable): start using the /crit/ prefix when we have real quota.
    metric = metrics_pb2.MetricsData(name=name)

    self._populate_target(metric)

    if isinstance(value, basestring):
      metric.string_value = value
    elif isinstance(value, bool):
      metric.boolean_value = value
    elif isinstance(value, int):
      if start_time:
        metric.counter = value
      else:
        metric.gauge = value
    elif isinstance(value, float):
      if start_time:
        metric.cumulative_double_value = value
      else:
        metric.noncumulative_double_value = value
    else:
      raise MonitoringInvalidValueTypeError(name, value)

    if start_time:
      metric.start_timestamp_us = start_time

    fields = fields or {}
    if len(fields) > 7:
      raise MonitoringTooManyFieldsError(name, fields)
    for key, value in fields.iteritems():
      field = metric.fields.add()
      field.name = key
      if isinstance(value, basestring):
        field.type = metrics_pb2.FieldType.STRING
        field.string_value = value
      elif isinstance(value, bool):
        field.type = metrics_pb2.FieldType.BOOL
        field.bool_value = value
      elif isinstance(value, int):
        field.type = metrics_pb2.FieldType.INT
        field.int_value = value
      else:
        raise MonitoringInvalidFieldTypeError(name, key, value)

    self._api.Send(metrics_pb2.MetricsCollection(data=[metric]))


class TaskMonitor(Monitor):
  """Monitoring interface class for monitoring active jobs or processes."""

  def __init__(self, service_name, job_name,
               region, hostname, task_num=0):
    """Create a Monitor object exporting info about a specific task.

    Args:
      service_name (str): service of which this task is a part.
      job_name (str): specific name of this task.
      region (str): general region in which this task is running.
      hostname (str): specific machine on which this task is running.
      task_num (str): replication id of this task.
    """
    super(TaskMonitor, self).__init__()
    self._service_name = service_name
    self._job_name = job_name
    self._region = region
    self._hostname = hostname
    self._task_num = task_num

  def _populate_target(self, metric):
    """Populate the 'task' embedded message field of a metric protobuf.

    Args:
      metric (metrics_pb2.MetricsData): the metric proto to be populated.
    """
    metric.task.service_name = self._service_name
    metric.task.job_name = self._job_name
    metric.task.data_center = self._region
    metric.task.host_name = self._hostname
    metric.task.task_num = self._task_num


class DeviceMonitor(Monitor):
  """Monitoring interface class for monitoring specific hosts or devices."""

  def __init__(self, region, network, hostname):
    """Create a Monitor object exporting info about a specific device.

    Args:
      region (str): physical region in which the device is located.
      network (str): virtual network on which the device is located.
      hostname (str): name by which the device self-identifies.
    """
    super(DeviceMonitor, self).__init__()
    self._region = region
    self._network = network
    self._hostname = hostname
    self._realm = 'ACQ_CHROME'
    self._alertable = True

  def _populate_target(self, metric):
    """Populate the 'network_device' embedded message of a metric protobuf.

    Args:
      metric (metrics_pb2.MetricsData): the metric proto to be populated.
    """
    # Note that this disregards the pop, asn, role, and vendor fields.
    metric.network_device.metro = self._region
    metric.network_device.hostgroup = self._network
    metric.network_device.hostname = self._hostname
    metric.network_device.realm = self._realm
    metric.network_device.alertable = self._alertable
