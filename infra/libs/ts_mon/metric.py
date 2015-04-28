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

from infra.libs.ts_mon.interface import register
from infra.libs.ts_mon.interface import send
from infra.libs.ts_mon.interface import unregister


class Metric(object):
  """Abstract base class for a metric.

  A Metric is an attribute that may be monitored across many targets. Examples
  include disk usage or the number of requests a server has received. A single
  process may keep track of many metrics.

  Note that Metric objects may be initialized at any time (for example, at the
  top of a library), but cannot be sent until the underlying Monitor object
  has been set up (usually by the top-level process parsing the command line).

  A Metric can actually store multiple values that are identified by a set of
  fields (which are themselves key-value pairs).  Fields can be passed to the
  set() or increment() methods to modify a particular value, or passed to the
  constructor in which case they will be used as the defaults for this Metric.

  Do not directly instantiate an object of this class.
  Use the concrete child classes instead:
  * StringMetric for metrics with string value
  * BooleanMetric for metrics with boolean values
  * CounterMetric for metrics with monotonically increasing integer values
  * GaugeMetric for metrics with arbitrarily varying integer values
  * CumulativeMetric for metrics with monotonically increasing float values
  * FloatMetric for metrics with arbitrarily varying float values
  """

  _initial_value = None

  def __init__(self, name, target=None, fields=None):
    """Create an instance of a Metric.

    Args:
      name (str): the file-like name of this metric
      fields (dict): a set of key-value pairs to be set as default metric fields
      target (Target): a Target to be used with this metric. This should be
                       specified only rarely; usually the library's default
                       Target will be used (set up by the top-level process).
    """
    self._name = name.lstrip('/')
    self._values = {}
    self._target = target
    fields = fields or {}
    if len(fields) > 7:
      raise MonitoringTooManyFieldsError(self._name, fields)
    self._fields = fields
    self._normalized_fields = self._normalize_fields(self._fields)

    register(self)

  def unregister(self):
    unregister(self)

  def serialize_to(self, collection_pb, default_target=None):
    """Add this Metric to a metrics_pb2.MetricsCollection protobuf.

    Args:
      collection_pb (metrics_pb2.MetricsCollection): protocol buffer into which
        to add the current metric values.
      default_target (Target): a Target to use if self._target is not set.

    Raises:
      MonitoringNoConfiguredTargetError: if neither self._target nor
                                         default_target is set
    """

    for fields, value in self._values.iteritems():
      metric_pb = collection_pb.data.add()
      metric_pb.metric_name_prefix = '/chrome/infra/'
      metric_pb.name = self._name

      self._populate_value(metric_pb, value)
      self._populate_fields(metric_pb, fields)

      if self._target:
        self._target._populate_target_pb(metric_pb)
      elif default_target:
        default_target._populate_target_pb(metric_pb)
      else:
        raise MonitoringNoConfiguredTargetError(self._name)

  def _populate_fields(self, metric, fields):
    """Fill in the fields attribute of a metric protocol buffer.

    Args:
      metric (metrics_pb2.MetricsData): a metrics protobuf to populate
      fields (list of (key, value) tuples): normalized metric fields

    Raises:
      MonitoringInvalidFieldTypeError: if a field has a value of unknown type
    """
    for key, value in fields:
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

  def _normalize_fields(self, fields):
    """Merges the fields with the default fields and returns something hashable.

    Args:
      fields (dict): A dict of fields passed by the user, or None.

    Returns:
      A tuple of (key, value) tuples, ordered by key.  This whole tuple is used
      as the key in the self._values dict to identify the cell for a value.

    Raises:
      MonitoringTooManyFieldsError: if there are more than seven metric fields
    """
    if fields is None:
      return self._normalized_fields

    all_fields = copy.copy(self._fields)
    all_fields.update(fields)

    if len(all_fields) > 7:
      raise MonitoringTooManyFieldsError(self._name, all_fields)

    return tuple(sorted(all_fields.iteritems()))

  def _set_and_send_value(self, value, fields):
    """Called by subclasses to set a new value for this metric.

    Args:
      value (see concrete class): the value of the metric to be set
      fields (dict): additional metric fields to complement those on self
    """
    self._values[self._normalize_fields(fields)] = value
    send(self)

  def _populate_value(self, metric, value):
    """Fill in the the data values of a metric protocol buffer.

    Args:
      metric (metrics_pb2.MetricsData): a metrics protobuf to populate
      value (see concrete class): the value of the metric to be set
    """
    raise NotImplementedError()

  def set(self, value, fields=None):
    """Set a new value for this metric. Results in sending a new value.

    The subclass should do appropriate type checking on value and then call
    self._set_and_send_value.

    Args:
      value (see concrete class): the value of the metric to be set
      fields (dict): additional metric fields to complement those on self
    """
    raise NotImplementedError()

  def get(self, fields=None):
    """Returns the current value for this metric."""
    return self._values.get(self._normalize_fields(fields), self._initial_value)


class StringMetric(Metric):
  """A metric whose value type is a string."""

  def _populate_value(self, metric, value):
    metric.string_value = value

  def set(self, value, fields=None):
    if not isinstance(value, basestring):
      raise MonitoringInvalidValueTypeError(self._name, value)
    self._set_and_send_value(value, fields)


class BooleanMetric(Metric):
  """A metric whose value type is a boolean."""

  def _populate_value(self, metric, value):
    metric.boolean_value = value

  def set(self, value, fields=None):
    if not isinstance(value, bool):
      raise MonitoringInvalidValueTypeError(self._name, value)
    self._set_and_send_value(value, fields)

  def toggle(self, fields=None):
    self.set(not self.get(fields), fields)


class NumericMetric(Metric):  # pylint: disable=abstract-method
  """Abstract base class for numeric (int or float) metrics."""
  #TODO(agable): Figure out if there's a way to send units with these metrics.

  def increment(self, fields=None):
    self.increment_by(1, fields)

  def increment_by(self, step, fields=None):
    if self.get(fields) is None:
      raise MonitoringIncrementUnsetValueError(self._name)
    self.set(self.get(fields) + step, fields)


class CounterMetric(NumericMetric):
  """A metric whose value type is a monotonically increasing integer."""

  _initial_value = 0

  def __init__(self, name, target=None, fields=None, start_time=None):
    super(CounterMetric, self).__init__(name, target=target, fields=fields)
    self._start_time = start_time or int(time.time() * 1000)

  def _populate_value(self, metric, value):
    metric.counter = value
    metric.start_timestamp_us = self._start_time

  def set(self, value, fields=None):
    if not isinstance(value, (int, long)):
      raise MonitoringInvalidValueTypeError(self._name, value)
    if value < self.get(fields):
      raise MonitoringDecreasingValueError(
          self._name, self.get(fields), value)
    self._set_and_send_value(value, fields)


class GaugeMetric(NumericMetric):
  """A metric whose value type is an integer."""

  def _populate_value(self, metric, value):
    metric.gauge = value

  def set(self, value, fields=None):
    if not isinstance(value, (int, long)):
      raise MonitoringInvalidValueTypeError(self._name, value)
    self._set_and_send_value(value, fields)


class CumulativeMetric(NumericMetric):
  """A metric whose value type is a monotonically increasing float."""

  _initial_value = 0.0

  def __init__(self, name, target=None, fields=None, start_time=None):
    super(CumulativeMetric, self).__init__(name, target=target, fields=fields)
    self._start_time = start_time or int(time.time() * 1000)

  def _populate_value(self, metric, value):
    metric.cumulative_double_value = value
    metric.start_timestamp_us = self._start_time

  def set(self, value, fields=None):
    if not isinstance(value, (float, int)):
      raise MonitoringInvalidValueTypeError(self._name, value)
    if value < self.get(fields):
      raise MonitoringDecreasingValueError(
          self._name, self.get(fields), value)
    self._set_and_send_value(float(value), fields)


class FloatMetric(NumericMetric):
  """A metric whose value type is a float."""

  def _populate_value(self, metric, value):
    metric.noncumulative_double_value = value

  def set(self, value, fields=None):
    if not isinstance(value, (float, int)):
      raise MonitoringInvalidValueTypeError(self._name, value)
    self._set_and_send_value(float(value), fields)
