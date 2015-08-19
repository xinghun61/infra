# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes representing individual metrics that can be sent."""


import copy
import threading
import time

try:
  from infra_libs.ts_mon import interface
  from infra_libs.ts_mon.common import distribution
  from infra_libs.ts_mon.common import errors
  from monacq.proto import metrics_pb2
except ImportError: # pragma: no cover
  import interface
  from common import distribution
  from common import errors
  from proto import metrics_pb2


MICROSECONDS_PER_SECOND = 1000000


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
      raise errors.MonitoringTooManyFieldsError(self._name, fields)
    self._fields = fields
    self._normalized_fields = self._normalize_fields(self._fields)
    self._thread_lock = threading.Lock()

    interface.register(self)


  def __eq__(self, other):
    name = self._name == other._name
    target = self._target == other._target
    field = self._fields == other._fields
    instance_type = type(self) == type(other)
    return name and target and field and instance_type

  def unregister(self):
    interface.unregister(self)

  def serialize_to(self, collection_pb, default_target=None, loop_action=None):
    """Generate metrics_pb2.MetricsData messages for this metric.

    Args:
      collection_pb (metrics_pb2.MetricsCollection): protocol buffer into which
        to add the current metric values.
      default_target (Target): a Target to use if self._target is not set.
      loop_action (function(metrics_pb2.MetricsCollection)): a function that we
        must call with the collection_pb every loop iteration.

    Raises:
      MonitoringNoConfiguredTargetError: if neither self._target nor
                                         default_target is set
    """

    for fields, value in self._values.iteritems():
      if callable(loop_action):
        loop_action(collection_pb)
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
        raise errors.MonitoringNoConfiguredTargetError(self._name)

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
        raise errors.MonitoringInvalidFieldTypeError(self._name, key, value)

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
      raise errors.MonitoringTooManyFieldsError(self._name, all_fields)

    return tuple(sorted(all_fields.iteritems()))

  def _set_and_send_value(self, value, fields):
    """Called by subclasses to set a new value for this metric.

    Args:
      value (see concrete class): the value of the metric to be set
      fields (dict): additional metric fields to complement those on self
    """
    self._values[self._normalize_fields(fields)] = value
    interface.send(self)

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

  def reset(self):
    """Resets the current values for this metric to 0.  Useful for tests."""
    self._values = {}


class StringMetric(Metric):
  """A metric whose value type is a string."""

  def _populate_value(self, metric, value):
    metric.string_value = value

  def set(self, value, fields=None):
    if not isinstance(value, basestring):
      raise errors.MonitoringInvalidValueTypeError(self._name, value)
    self._set_and_send_value(value, fields)


class BooleanMetric(Metric):
  """A metric whose value type is a boolean."""

  def _populate_value(self, metric, value):
    metric.boolean_value = value

  def set(self, value, fields=None):
    if not isinstance(value, bool):
      raise errors.MonitoringInvalidValueTypeError(self._name, value)
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
      raise errors.MonitoringIncrementUnsetValueError(self._name)
    with self._thread_lock:
      self.set(self.get(fields) + step, fields)


class CounterMetric(NumericMetric):
  """A metric whose value type is a monotonically increasing integer."""

  _initial_value = 0

  def __init__(
      self, name, target=None, fields=None, start_time=None, time_fn=time.time):
    super(CounterMetric, self).__init__(name, target=target, fields=fields)
    self._start_time = start_time or int(time_fn() * MICROSECONDS_PER_SECOND)

  def _populate_value(self, metric, value):
    metric.counter = value
    metric.start_timestamp_us = self._start_time

  def set(self, value, fields=None):
    if not isinstance(value, (int, long)):
      raise errors.MonitoringInvalidValueTypeError(self._name, value)
    if value < self.get(fields):
      raise errors.MonitoringDecreasingValueError(
          self._name, self.get(fields), value)
    self._set_and_send_value(value, fields)


class GaugeMetric(NumericMetric):
  """A metric whose value type is an integer."""

  def _populate_value(self, metric, value):
    metric.gauge = value

  def set(self, value, fields=None):
    if not isinstance(value, (int, long)):
      raise errors.MonitoringInvalidValueTypeError(self._name, value)
    self._set_and_send_value(value, fields)


class CumulativeMetric(NumericMetric):
  """A metric whose value type is a monotonically increasing float."""

  _initial_value = 0.0

  def __init__(
      self, name, target=None, fields=None, start_time=None, time_fn=time.time):
    super(CumulativeMetric, self).__init__(name, target=target, fields=fields)
    self._start_time = start_time or int(time_fn() * MICROSECONDS_PER_SECOND)

  def _populate_value(self, metric, value):
    metric.cumulative_double_value = value
    metric.start_timestamp_us = self._start_time

  def set(self, value, fields=None):
    if not isinstance(value, (float, int)):
      raise errors.MonitoringInvalidValueTypeError(self._name, value)
    if value < self.get(fields):
      raise errors.MonitoringDecreasingValueError(
          self._name, self.get(fields), value)
    self._set_and_send_value(float(value), fields)


class FloatMetric(NumericMetric):
  """A metric whose value type is a float."""

  def _populate_value(self, metric, value):
    metric.noncumulative_double_value = value

  def set(self, value, fields=None):
    if not isinstance(value, (float, int)):
      raise errors.MonitoringInvalidValueTypeError(self._name, value)
    self._set_and_send_value(float(value), fields)


class DistributionMetric(Metric):
  """A metric that holds a distribution of values.

  By default buckets are chosen from a geometric progression, each bucket being
  approximately 1.59 times bigger than the last.  In practice this is suitable
  for many kinds of data, but you may want to provide a FixedWidthBucketer or
  GeometricBucketer with different parameters."""

  CANONICAL_SPEC_TYPES = {
      2: metrics_pb2.PrecomputedDistribution.CANONICAL_POWERS_OF_2,
      10**0.2: metrics_pb2.PrecomputedDistribution.CANONICAL_POWERS_OF_10_P_0_2,
      10: metrics_pb2.PrecomputedDistribution.CANONICAL_POWERS_OF_10,
  }

  def __init__(self, name, is_cumulative=True, bucketer=None, target=None,
               fields=None, start_time=None, time_fn=time.time):
    super(DistributionMetric, self).__init__(name, target, fields)
    self._start_time = start_time or int(time_fn() * MICROSECONDS_PER_SECOND)

    if bucketer is None:
      bucketer = distribution.GeometricBucketer()

    self.is_cumulative = is_cumulative
    self.bucketer = bucketer

  def _populate_value(self, metric, value):
    pb = metric.distribution

    pb.is_cumulative = self.is_cumulative
    metric.start_timestamp_us = self._start_time

    # Copy the bucketer params.
    if (value.bucketer.width == 0 and
        value.bucketer.growth_factor in self.CANONICAL_SPEC_TYPES):
      pb.spec_type = self.CANONICAL_SPEC_TYPES[value.bucketer.growth_factor]
    else:
      pb.spec_type = metrics_pb2.PrecomputedDistribution.CUSTOM_PARAMETERIZED
      pb.width = value.bucketer.width
      pb.growth_factor = value.bucketer.growth_factor
      pb.num_buckets = value.bucketer.num_finite_buckets

    # Copy the distribution bucket values.  Only include the finite buckets, not
    # the overflow buckets on each end.
    pb.bucket.extend(self._running_zero_generator(
        value.buckets.get(i, 0) for i in
        xrange(1, value.bucketer.total_buckets - 1)))

    # Add the overflow buckets if present.
    if value.bucketer.underflow_bucket in value.buckets:
      pb.underflow = value.buckets[value.bucketer.underflow_bucket]
    if value.bucketer.overflow_bucket in value.buckets:
      pb.overflow = value.buckets[value.bucketer.overflow_bucket]

    if value.count != 0:
      pb.mean = float(value.sum) / value.count

  @staticmethod
  def _running_zero_generator(iterable):
    """Compresses sequences of zeroes in the iterable into negative zero counts.

    For example an input of [1, 0, 0, 0, 2] is converted to [1, -3, 2].
    """

    count = 0

    for value in iterable:
      if value == 0:
        count += 1
      else:
        if count != 0:
          yield -count
          count = 0
        yield value

  def add(self, value, fields=None):
    with self._thread_lock:
      dist = self.get(fields)
      if dist is None:
        dist = distribution.Distribution(self.bucketer)

      dist.add(value)
      self._set_and_send_value(dist, fields)

  def set(self, value, fields=None):
    """Replaces the distribution with the given fields with another one.

    This only makes sense on non-cumulative DistributionMetrics.

    Args:
      value: A infra_libs.ts_mon.Distribution.
    """

    if self.is_cumulative:
      raise TypeError(
          'Cannot set() a cumulative DistributionMetric (use add() instead)')

    if not isinstance(value, distribution.Distribution):
      raise errors.MonitoringInvalidValueTypeError(self._name, value)

    self._set_and_send_value(value, fields)


class CumulativeDistributionMetric(DistributionMetric):
  """A DistributionMetric with is_cumulative set to True."""

  def __init__(
      self, name, bucketer=None, target=None, fields=None, time_fn=time.time):
    super(CumulativeDistributionMetric, self).__init__(
        name,
        is_cumulative=True,
        bucketer=bucketer,
        target=target,
        fields=fields,
        time_fn=time_fn)


class NonCumulativeDistributionMetric(DistributionMetric):
  """A DistributionMetric with is_cumulative set to False."""

  def __init__(
      self, name, bucketer=None, target=None, fields=None, time_fn=time.time):
    super(NonCumulativeDistributionMetric, self).__init__(
        name,
        is_cumulative=False,
        bucketer=bucketer,
        target=target,
        fields=fields,
        time_fn=time_fn)
