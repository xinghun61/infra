# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes representing individual metrics that can be sent."""


import copy
import time

from monacq.proto import metrics_pb2

from infra.libs.ts_mon.errors import MonitoringDecreasingValueError
from infra.libs.ts_mon.errors import MonitoringIncrementUnsetValueError
from infra.libs.ts_mon.errors import MonitoringInvalidFieldTypeError
from infra.libs.ts_mon.errors import MonitoringInvalidValueTypeError
from infra.libs.ts_mon.errors import MonitoringTooManyFieldsError
from infra.libs.ts_mon.errors import MonitoringNoConfiguredTargetError

from infra.libs.ts_mon.interface import send


class Metric(object):
  """Abstract base class for a metric.

  A Metric is an attribute that may be monitored across many targets. Examples
  include disk usage or the number of requests a server has received. A single
  process may keep track of many metrics.

  Note that Metric objects may be initialized at any time (for example, at the
  top of a library), but cannot be sent until the underlying Monitor object
  has been set up (usually by the top-level process parsing the command line).

  Do not directly instantiate an object of this class.
  Use the concrete child classes instead:
  * StringMetric for metrics with string value
  * BooleanMetric for metrics with boolean values
  * CounterMetric for metrics with monotonically increasing integer values
  * GaugeMetric for metrics with arbitrarily varying integer values
  * CumulativeMetric for metrics with monotonically increasing float values
  * FloatMetric for metrics with arbitrarily varying float values
  """
  def __init__(self, name, target=None, fields=None):
    """Create an instance of a Metric.

    Args:
      name (str): the file-like name of this metric
      fields (dict): a set of key-value pairs to be set as metric fields
      target (Target): a Target to be used with this metric. This should be
                       specified only rarely; usually the library's default
                       Target will be used (set up by the top-level process).
    """
    self._name = name.lstrip('/')
    self._value = None
    self._target = target
    fields = fields or {}
    if len(fields) > 7:
      raise MonitoringTooManyFieldsError(self._name, fields)
    self._fields = fields

  def serialize(self, fields=None, default_target=None):
    """Convert this Metric into a metrics_pb2.MetricsData protobuf.

    Args:
      fields (dict): a set of key-value pairs to be set as extra metric fields
      default_target (Target): a Target to use if self._target is not set

    Returns:
      metrics_pb2.MetricsData protocol buffer with the current metric value

    Raises:
      MonitoringNoConfiguredTargetError: if neither self._target nor
                                         default_target is set
      MonitoringTooManyFieldsError: if the provided extra metric fields put the
                                    total over seven.
    """
    metric_pb = metrics_pb2.MetricsData(metric_name_prefix='/chrome/infra/',
                                        name=self._name)

    self._populate_metric_pb(metric_pb)
    self._populate_fields_pb(metric_pb, fields=fields)

    if self._target:
      self._target._populate_target_pb(metric_pb)
    elif default_target:
      default_target._populate_target_pb(metric_pb)
    else:
      raise MonitoringNoConfiguredTargetError(self._name)

    return metric_pb

  def _populate_fields_pb(self, metric, fields=None):
    """Fill in the fields attribute of a metric protocol buffer.

    Args:
      metric (metrics_pb2.MetricsData): a metrics protobuf to populate
      fields (dict): additional metric fields to complement those on self

    Raises:
      MonitoringTooManyFieldsError: if there are more than seven metric fields
      MonitoringInvalidFieldTypeError: if a field has a value of unknown type
    """
    all_fields = copy.copy(self._fields)
    all_fields.update(fields or {})
    if len(all_fields) > 7:
      raise MonitoringTooManyFieldsError(self._name, all_fields)
    for key, value in all_fields.iteritems():
      field = metric.fields.add()
      field.name = key
      if isinstance(value, basestring):
        field.type = metrics_pb2.MetricsField.STRING
        field.string_value = value
      elif isinstance(value, bool):
        field.type = metrics_pb2.MetricsField.BOOL
        field.bool_value = value
      elif isinstance(value, int):
        field.type = metrics_pb2.MetricsField.INT
        field.int_value = value
      else:
        raise MonitoringInvalidFieldTypeError(self._name, key, value)

  def _populate_metric_pb(self, metric):
    """Fill in the the data values of a metric protocol buffer.

    Args:
      metric (metrics_pb2.MetricsData): a metrics protobuf to populate
    """
    raise NotImplementedError()

  def set(self, value, fields=None):
    """Set a new value for this metric. Results in sending a new value.

    Args:
      value (see concrete class): the value of the metric to be set
      fields (dict): additional metric fields to complement those on self
    """
    raise NotImplementedError()


class StringMetric(Metric):
  """A metric whose value type is a string."""

  def _populate_metric_pb(self, metric):
    metric.string_value = self._value

  def set(self, value, fields=None):
    if not isinstance(value, basestring):
      raise MonitoringInvalidValueTypeError(self._name, value)
    self._value = value
    send(self, fields)


class BooleanMetric(Metric):
  """A metric whose value type is a boolean."""

  def _populate_metric_pb(self, metric):
    metric.boolean_value = self._value

  def set(self, value, fields=None):
    if not isinstance(value, bool):
      raise MonitoringInvalidValueTypeError(self._name, value)
    self._value = value
    send(self, fields)

  def toggle(self, fields=None):
    self.set(not self._value, fields)


class NumericMetric(Metric):  # pylint: disable=abstract-method
  """Abstract base class for numeric (int or float) metrics."""
  #TODO(agable): Figure out if there's a way to send units with these metrics.

  def increment(self, fields=None):
    self.increment_by(1, fields)

  def increment_by(self, step, fields=None):
    if self._value is None:
      raise MonitoringIncrementUnsetValueError(self._name)
    self.set(self._value + step, fields)


class CounterMetric(NumericMetric):
  """A metric whose value type is a monotonically increasing integer."""

  def __init__(self, name, target=None, fields=None, start_time=None):
    super(CounterMetric, self).__init__(name, target=target, fields=fields)
    self._start_time = start_time or int(time.time() * 1000)

  def _populate_metric_pb(self, metric):
    metric.counter = self._value
    metric.start_timestamp_us = self._start_time

  def set(self, value, fields=None):
    if not isinstance(value, (int, long)):
      raise MonitoringInvalidValueTypeError(self._name, value)
    if value < self._value:
      raise MonitoringDecreasingValueError(self._name, self._value, value)
    self._value = value
    send(self, fields)


class GaugeMetric(NumericMetric):
  """A metric whose value type is an integer."""

  def _populate_metric_pb(self, metric):
    metric.gauge = self._value

  def set(self, value, fields=None):
    if not isinstance(value, (int, long)):
      raise MonitoringInvalidValueTypeError(self._name, value)
    self._value = value
    send(self, fields)


class CumulativeMetric(NumericMetric):
  """A metric whose value type is a monotonically increasing float."""

  def __init__(self, name, target=None, fields=None, start_time=None):
    super(CumulativeMetric, self).__init__(name, target=target, fields=fields)
    self._start_time = start_time or int(time.time() * 1000)

  def _populate_metric_pb(self, metric):
    metric.cumulative_double_value = self._value
    metric.start_timestamp_us = self._start_time

  def set(self, value, fields=None):
    if not isinstance(value, (float, int)):
      raise MonitoringInvalidValueTypeError(self._name, value)
    if value < self._value:
      raise MonitoringDecreasingValueError(self._name, self._value, value)
    self._value = float(value)
    send(self, fields)


class FloatMetric(NumericMetric):
  """A metric whose value type is a float."""

  def _populate_metric_pb(self, metric):
    metric.noncumulative_double_value = self._value

  def set(self, value, fields=None):
    if not isinstance(value, (float, int)):
      raise MonitoringInvalidValueTypeError(self._name, value)
    self._value = float(value)
    send(self, fields)
