# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import textwrap
import unittest

import mock

try:
  from infra_libs.ts_mon import interface
  from infra_libs.ts_mon.common import metrics
  from infra_libs.ts_mon.common import distribution
  from infra_libs.ts_mon.common import errors
  from infra_libs.ts_mon.common import targets
  from monacq.proto import metrics_pb2
except ImportError: # pragma: no cover
  import interface
  from common import metrics
  from common import distribution
  from common import errors
  from common import targets
  from monacq.proto import metrics_pb2


class FakeState(interface.State):
  def __init__(self):
    super(FakeState, self).__init__()
    self.global_monitor = mock.Mock()


class MetricTestBase(unittest.TestCase):
  def setUp(self):
    self.fake_state = FakeState()
    self.state_patcher = mock.patch(
        'infra_libs.ts_mon.interface.state', new=self.fake_state)
    self.send_patcher = mock.patch('infra_libs.ts_mon.interface.send')

    self.state_patcher.start()
    self.fake_send = self.send_patcher.start()

  def tearDown(self):
    self.state_patcher.stop()
    self.send_patcher.stop()


class MetricTest(MetricTestBase):

  def test_init_too_may_fields(self):
    fields = {str(i): str(i) for i in xrange(8)}
    with self.assertRaises(errors.MonitoringTooManyFieldsError) as e:
      metrics.Metric('test', fields=fields)
    self.assertEquals(e.exception.metric, 'test')
    self.assertEquals(len(e.exception.fields), 8)

  def test_serialize(self):
    t = targets.DeviceTarget('reg', 'net', 'host')
    m = metrics.StringMetric('test', target=t, fields={'bar': 1})
    m.set('val', fields={'baz': False})
    p = metrics_pb2.MetricsCollection()
    m.serialize_to(p)
    e = textwrap.dedent('''\
        data {
          name: "test"
          metric_name_prefix: "/chrome/infra/"
          network_device {
            alertable: true
            realm: "ACQ_CHROME"
            metro: "reg"
            hostname: "host"
            hostgroup: "net"
          }
          fields {
            name: "bar"
            type: INT
            int_value: 1
          }
          fields {
            name: "baz"
            type: BOOL
            bool_value: false
          }
          string_value: "val"
        }
    ''')
    self.assertEquals(str(p), e)

  def test_serialize_multiple_values(self):
    t = targets.DeviceTarget('reg', 'net', 'host')
    m = metrics.StringMetric('test', target=t)
    m.set('val1', fields={'foo': 1})
    m.set('val2', fields={'foo': 2})
    p = metrics_pb2.MetricsCollection()
    loop_action = mock.Mock()
    m.serialize_to(p, loop_action=loop_action)
    e = textwrap.dedent('''\
        data {
          name: "test"
          metric_name_prefix: "/chrome/infra/"
          network_device {
            alertable: true
            realm: "ACQ_CHROME"
            metro: "reg"
            hostname: "host"
            hostgroup: "net"
          }
          fields {
            name: "foo"
            type: INT
            int_value: 2
          }
          string_value: "val2"
        }
        data {
          name: "test"
          metric_name_prefix: "/chrome/infra/"
          network_device {
            alertable: true
            realm: "ACQ_CHROME"
            metro: "reg"
            hostname: "host"
            hostgroup: "net"
          }
          fields {
            name: "foo"
            type: INT
            int_value: 1
          }
          string_value: "val1"
        }
    ''')
    self.assertEquals(str(p), e)
    self.assertEquals(2, loop_action.call_count)

  def test_serialize_default_target(self):
    t = targets.DeviceTarget('reg', 'net', 'host')
    m = metrics.StringMetric('test')
    m.set('val')
    p = metrics_pb2.MetricsCollection()
    m.serialize_to(p, default_target=t)
    e = textwrap.dedent('''\
        data {
          name: "test"
          metric_name_prefix: "/chrome/infra/"
          network_device {
            alertable: true
            realm: "ACQ_CHROME"
            metro: "reg"
            hostname: "host"
            hostgroup: "net"
          }
          string_value: "val"
        }
    ''')
    self.assertEquals(str(p), e)

  def test_serialize_no_target(self):
    m = metrics.StringMetric('test')
    m.set('val')
    with self.assertRaises(errors.MonitoringNoConfiguredTargetError):
      p = metrics_pb2.MetricsCollection()
      m.serialize_to(p)

  def test_serialze_too_many_fields(self):
    t = targets.DeviceTarget('reg', 'net', 'host')
    m = metrics.StringMetric('test', target=t,
                            fields={'a': 1, 'b': 2, 'c': 3, 'd': 4})
    m.set('val', fields={'e': 5, 'f': 6, 'g': 7})
    with self.assertRaises(errors.MonitoringTooManyFieldsError):
      m.set('val', fields={'e': 5, 'f': 6, 'g': 7, 'h': 8})

  def test_populate_field_values(self):
    pb1 = metrics_pb2.MetricsData()
    m1 = metrics.Metric('foo', fields={'asdf': 1})
    m1._populate_fields(pb1, m1._normalized_fields)
    self.assertEquals(pb1.fields[0].name, 'asdf')
    self.assertEquals(pb1.fields[0].int_value, 1)

    pb2 = metrics_pb2.MetricsData()
    m2 = metrics.Metric('bar', fields={'qwer': True})
    m2._populate_fields(pb2, m2._normalized_fields)
    self.assertEquals(pb2.fields[0].name, 'qwer')
    self.assertEquals(pb2.fields[0].bool_value, True)

    pb3 = metrics_pb2.MetricsData()
    m3 = metrics.Metric('baz', fields={'zxcv': 'baz'})
    m3._populate_fields(pb3, m3._normalized_fields)
    self.assertEquals(pb3.fields[0].name, 'zxcv')
    self.assertEquals(pb3.fields[0].string_value, 'baz')

  def test_invalid_field_value(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.Metric('test', fields={'pi': 3.14})
    with self.assertRaises(errors.MonitoringInvalidFieldTypeError) as e:
      m._populate_fields(pb, m._normalized_fields)
    self.assertEquals(e.exception.metric, 'test')
    self.assertEquals(e.exception.field, 'pi')
    self.assertEquals(e.exception.value, 3.14)

  def test_register_unregister(self):
    self.assertEquals(0, len(self.fake_state.metrics))
    m = metrics.Metric('test', fields={'pi': 3.14})
    self.assertEquals(1, len(self.fake_state.metrics))
    m.unregister()
    self.assertEquals(0, len(self.fake_state.metrics))

  def test_reset(self):
    m = metrics.StringMetric('test')
    self.assertIsNone(m.get())
    m.set('foo')
    self.assertEqual('foo', m.get())
    m.reset()
    self.assertIsNone(m.get())


class StringMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.StringMetric('test')
    m._populate_value(pb, 'foo')
    self.assertEquals(pb.string_value, 'foo')

  def test_set(self):
    m = metrics.StringMetric('test')
    m.set('hello world')
    self.assertEquals(m.get(), 'hello world')
    self.assertEquals(self.fake_send.call_count, 1)

  def test_non_string_raises(self):
    m = metrics.StringMetric('test')
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set(object())


class BooleanMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.BooleanMetric('test')
    m._populate_value(pb, True)
    self.assertEquals(pb.boolean_value, True)

  def test_set(self):
    m = metrics.BooleanMetric('test')
    m.set(False)
    self.assertEquals(m.get(), False)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_toggle(self):
    m = metrics.BooleanMetric('test')
    m.set(True)
    self.assertEquals(m.get(), True)
    self.assertEquals(self.fake_send.call_count, 1)
    m.toggle()
    self.assertEquals(m.get(), False)
    self.assertEquals(self.fake_send.call_count, 2)

  def test_non_bool_raises(self):
    m = metrics.BooleanMetric('test')
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set(object())
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set('True')
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set(123)


class CounterMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.CounterMetric('test')
    m._populate_value(pb, 1)
    self.assertEquals(pb.counter, 1)

  def test_starts_at_zero(self):
    m = metrics.CounterMetric('test')
    self.assertEquals(m.get(), 0)
    m.increment()
    self.assertEquals(m.get(), 1)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_set(self):
    m = metrics.CounterMetric('test')
    m.set(10)
    self.assertEquals(m.get(), 10)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_increment(self):
    m = metrics.CounterMetric('test')
    m.set(1)
    self.assertEquals(m.get(), 1)
    self.assertEquals(self.fake_send.call_count, 1)
    m.increment()
    self.assertEquals(m.get(), 2)
    self.assertEquals(self.fake_send.call_count, 2)
    m.increment_by(3)
    self.assertAlmostEquals(m.get(), 5)
    self.assertEquals(self.fake_send.call_count, 3)

  def test_decrement_raises(self):
    m = metrics.CounterMetric('test')
    m.set(1)
    with self.assertRaises(errors.MonitoringDecreasingValueError):
      m.set(0)
    with self.assertRaises(errors.MonitoringDecreasingValueError):
      m.increment_by(-1)

  def test_non_int_raises(self):
    m = metrics.CounterMetric('test')
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set(object())
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set(1.5)
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.increment_by(1.5)

  def test_multiple_field_values(self):
    m = metrics.CounterMetric('test')
    m.increment({'foo': 'bar'})
    m.increment({'foo': 'baz'})
    m.increment({'foo': 'bar'})
    self.assertEquals(0, m.get())
    self.assertEquals(2, m.get({'foo': 'bar'}))
    self.assertEquals(1, m.get({'foo': 'baz'}))

  def test_override_fields(self):
    m = metrics.CounterMetric('test', fields={'foo': 'bar'})
    m.increment()
    m.increment({'foo': 'baz'})
    self.assertEquals(1, m.get())
    self.assertEquals(1, m.get({'foo': 'bar'}))
    self.assertEquals(1, m.get({'foo': 'baz'}))

  def test_start_timestamp(self):
    t = targets.DeviceTarget('reg', 'net', 'host')
    m = metrics.CounterMetric(
        'test', target=t, fields={'foo': 'bar'}, time_fn=lambda: 1234)
    m.increment()
    p = metrics_pb2.MetricsCollection()
    m.serialize_to(p)
    self.assertEquals(1234000000, p.data[0].start_timestamp_us)


class GaugeMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.GaugeMetric('test')
    m._populate_value(pb, 1)
    self.assertEquals(pb.gauge, 1)

  def test_set(self):
    m = metrics.GaugeMetric('test')
    m.set(10)
    self.assertEquals(m.get(), 10)
    self.assertEquals(self.fake_send.call_count, 1)
    m.set(sys.maxint + 1)
    self.assertEquals(m.get(), sys.maxint + 1)
    self.assertEquals(self.fake_send.call_count, 2)

  def test_non_int_raises(self):
    m = metrics.GaugeMetric('test')
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set(object())

  def test_unset_increment_raises(self):
    m = metrics.GaugeMetric('test')
    with self.assertRaises(errors.MonitoringIncrementUnsetValueError):
      m.increment()


class CumulativeMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.CumulativeMetric('test')
    m._populate_value(pb, 1.618)
    self.assertAlmostEquals(pb.cumulative_double_value, 1.618)

  def test_starts_at_zero(self):
    m = metrics.CumulativeMetric('test')
    self.assertEquals(m.get(), 0.0)
    m.increment()
    self.assertEquals(m.get(), 1.0)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_set(self):
    m = metrics.CumulativeMetric('test')
    m.set(3.14)
    self.assertAlmostEquals(m.get(), 3.14)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_decrement_raises(self):
    m = metrics.CumulativeMetric('test')
    m.set(3.14)
    with self.assertRaises(errors.MonitoringDecreasingValueError):
      m.set(0)
    with self.assertRaises(errors.MonitoringDecreasingValueError):
      m.increment_by(-1)

  def test_non_number_raises(self):
    m = metrics.CumulativeMetric('test')
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set(object())

  def test_start_timestamp(self):
    t = targets.DeviceTarget('reg', 'net', 'host')
    m = metrics.CumulativeMetric(
        'test', target=t, fields={'foo': 'bar'}, time_fn=lambda: 1234)
    m.set(3.14)
    p = metrics_pb2.MetricsCollection()
    m.serialize_to(p)
    self.assertEquals(1234000000, p.data[0].start_timestamp_us)


class FloatMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.FloatMetric('test')
    m._populate_value(pb, 1.618)
    self.assertEquals(pb.noncumulative_double_value, 1.618)

  def test_set(self):
    m = metrics.FloatMetric('test')
    m.set(3.14)
    self.assertEquals(m.get(), 3.14)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_non_number_raises(self):
    m = metrics.FloatMetric('test')
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set(object())


class RunningZeroGeneratorTest(unittest.TestCase):
  def assertZeroes(self, expected, sequence):
    self.assertEquals(expected,
        list(metrics.DistributionMetric._running_zero_generator(sequence)))

  def test_running_zeroes(self):
    self.assertZeroes([1, -1, 1], [1, 0, 1])
    self.assertZeroes([1, -2, 1], [1, 0, 0, 1])
    self.assertZeroes([1, -3, 1], [1, 0, 0, 0, 1])
    self.assertZeroes([1, -1, 1, -1, 2], [1, 0, 1, 0, 2])
    self.assertZeroes([1, -1, 1, -2, 2], [1, 0, 1, 0, 0, 2])
    self.assertZeroes([1, -2, 1, -2, 2], [1, 0, 0, 1, 0, 0, 2])

  def test_leading_zeroes(self):
    self.assertZeroes([-1, 1], [0, 1])
    self.assertZeroes([-2, 1], [0, 0, 1])
    self.assertZeroes([-3, 1], [0, 0, 0, 1])

  def test_trailing_zeroes(self):
    self.assertZeroes([1], [1])
    self.assertZeroes([1], [1, 0])
    self.assertZeroes([1], [1, 0, 0])
    self.assertZeroes([], [])
    self.assertZeroes([], [0])
    self.assertZeroes([], [0, 0])


class DistributionMetricTest(MetricTestBase):

  def test_populate_canonical(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.DistributionMetric('test')
    m._populate_value(pb,
        distribution.Distribution(distribution.GeometricBucketer()))
    self.assertEquals(pb.distribution.spec_type,
        metrics_pb2.PrecomputedDistribution.CANONICAL_POWERS_OF_10_P_0_2)

    m._populate_value(pb,
        distribution.Distribution(distribution.GeometricBucketer(2)))
    self.assertEquals(pb.distribution.spec_type,
        metrics_pb2.PrecomputedDistribution.CANONICAL_POWERS_OF_2)

    m._populate_value(pb,
        distribution.Distribution(distribution.GeometricBucketer(10)))
    self.assertEquals(pb.distribution.spec_type,
        metrics_pb2.PrecomputedDistribution.CANONICAL_POWERS_OF_10)

  def test_populate_custom(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.DistributionMetric('test')
    m._populate_value(pb,
        distribution.Distribution(distribution.GeometricBucketer(4)))
    self.assertEquals(pb.distribution.spec_type,
        metrics_pb2.PrecomputedDistribution.CUSTOM_PARAMETERIZED)
    self.assertEquals(0, pb.distribution.width)
    self.assertEquals(4, pb.distribution.growth_factor)
    self.assertEquals(100, pb.distribution.num_buckets)

    m._populate_value(pb,
        distribution.Distribution(distribution.FixedWidthBucketer(10)))
    self.assertEquals(pb.distribution.spec_type,
        metrics_pb2.PrecomputedDistribution.CUSTOM_PARAMETERIZED)
    self.assertEquals(10, pb.distribution.width)
    self.assertEquals(0, pb.distribution.growth_factor)
    self.assertEquals(100, pb.distribution.num_buckets)

  def test_populate_buckets(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.DistributionMetric('test')
    d = distribution.Distribution(
        distribution.FixedWidthBucketer(10))
    d.add(5)
    d.add(15)
    d.add(35)
    d.add(65)

    m._populate_value(pb, d)
    self.assertEquals([1, 1, -1, 1, -2, 1], pb.distribution.bucket)
    self.assertEquals(0, pb.distribution.underflow)
    self.assertEquals(0, pb.distribution.overflow)
    self.assertEquals(30, pb.distribution.mean)

    pb = metrics_pb2.MetricsData()
    d = distribution.Distribution(
        distribution.FixedWidthBucketer(10, num_finite_buckets=1))
    d.add(5)
    d.add(15)
    d.add(25)

    m._populate_value(pb, d)
    self.assertEquals([1], pb.distribution.bucket)
    self.assertEquals(0, pb.distribution.underflow)
    self.assertEquals(2, pb.distribution.overflow)
    self.assertEquals(15, pb.distribution.mean)

  def test_populate_buckets_last_zero(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.DistributionMetric('test')
    d = distribution.Distribution(
        distribution.FixedWidthBucketer(10, num_finite_buckets=10))
    d.add(5)
    d.add(105)

    m._populate_value(pb, d)
    self.assertEquals([1], pb.distribution.bucket)
    self.assertEquals(1, pb.distribution.overflow)

  def test_populate_buckets_underflow(self):
    pb = metrics_pb2.MetricsData()
    m = metrics.DistributionMetric('test')
    d = distribution.Distribution(
        distribution.FixedWidthBucketer(10, num_finite_buckets=10))
    d.add(-5)
    d.add(-1000000)

    m._populate_value(pb, d)
    self.assertEquals([], pb.distribution.bucket)
    self.assertEquals(2, pb.distribution.underflow)
    self.assertEquals(0, pb.distribution.overflow)
    self.assertEquals(-500002.5, pb.distribution.mean)

  def test_populate_is_cumulative(self):
    pb = metrics_pb2.MetricsData()
    d = distribution.Distribution(
        distribution.FixedWidthBucketer(10, num_finite_buckets=10))
    m = metrics.CumulativeDistributionMetric('test')

    m._populate_value(pb, d)
    self.assertTrue(pb.distribution.is_cumulative)

    m = metrics.NonCumulativeDistributionMetric('test2')

    m._populate_value(pb, d)
    self.assertFalse(pb.distribution.is_cumulative)

  def test_add(self):
    m = metrics.DistributionMetric('test')
    m.add(1)
    m.add(10)
    m.add(100)
    self.assertEquals({2: 1, 6: 1, 11: 1}, m.get().buckets)
    self.assertEquals(111, m.get().sum)
    self.assertEquals(3, m.get().count)

  def test_add_custom_bucketer(self):
    m = metrics.DistributionMetric('test',
        bucketer=distribution.FixedWidthBucketer(10))
    m.add(1)
    m.add(10)
    m.add(100)
    self.assertEquals({1: 1, 2: 1, 11: 1}, m.get().buckets)
    self.assertEquals(111, m.get().sum)
    self.assertEquals(3, m.get().count)

  def test_set(self):
    d = distribution.Distribution(
        distribution.FixedWidthBucketer(10, num_finite_buckets=10))
    d.add(1)
    d.add(10)
    d.add(100)

    m = metrics.CumulativeDistributionMetric('test')
    with self.assertRaises(TypeError):
      m.set(d)

    m = metrics.NonCumulativeDistributionMetric('test2')
    m.set(d)
    self.assertEquals(d, m.get())

    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set(1)
    with self.assertRaises(errors.MonitoringInvalidValueTypeError):
      m.set('foo')

  def test_start_timestamp(self):
    t = targets.DeviceTarget('reg', 'net', 'host')
    m = metrics.CumulativeDistributionMetric(
        'test', target=t, time_fn=lambda: 1234)
    m.add(1)
    m.add(5)
    m.add(25)
    p = metrics_pb2.MetricsCollection()
    m.serialize_to(p)
    self.assertEquals(1234000000, p.data[0].start_timestamp_us)
