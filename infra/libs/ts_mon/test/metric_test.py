# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import textwrap
import unittest

import mock

from monacq.proto import metrics_pb2

import infra.libs.ts_mon.interface as interface
import infra.libs.ts_mon.metric as metric

from infra.libs.ts_mon.errors import MonitoringDecreasingValueError
from infra.libs.ts_mon.errors import MonitoringIncrementUnsetValueError
from infra.libs.ts_mon.errors import MonitoringInvalidFieldTypeError
from infra.libs.ts_mon.errors import MonitoringInvalidValueTypeError
from infra.libs.ts_mon.errors import MonitoringTooManyFieldsError
from infra.libs.ts_mon.errors import MonitoringNoConfiguredTargetError
from infra.libs.ts_mon.target import DeviceTarget


class FakeState(interface.State):
  def __init__(self):
    super(FakeState, self).__init__()
    self.global_monitor = mock.Mock()


class MetricTestBase(unittest.TestCase):
  def setUp(self):
    self.fake_state = FakeState()
    self.state_patcher = mock.patch(
        'infra.libs.ts_mon.interface._state', new=self.fake_state)
    self.send_patcher = mock.patch('infra.libs.ts_mon.metric.send')

    self.state_patcher.start()
    self.fake_send = self.send_patcher.start()

  def tearDown(self):
    self.state_patcher.stop()
    self.send_patcher.stop()


class MetricTest(MetricTestBase):

  def test_init_too_may_fields(self):
    fields = {str(i): str(i) for i in xrange(8)}
    with self.assertRaises(MonitoringTooManyFieldsError) as e:
      metric.Metric('test', fields=fields)
    self.assertEquals(e.exception.metric, 'test')
    self.assertEquals(len(e.exception.fields), 8)

  def test_serialize(self):
    t = DeviceTarget('reg', 'net', 'host')
    m = metric.StringMetric('test', target=t, fields={'bar': 1})
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
    t = DeviceTarget('reg', 'net', 'host')
    m = metric.StringMetric('test', target=t)
    m.set('val1', fields={'foo': 1})
    m.set('val2', fields={'foo': 2})
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

  def test_serialize_default_target(self):
    t = DeviceTarget('reg', 'net', 'host')
    m = metric.StringMetric('test')
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
    m = metric.StringMetric('test')
    m.set('val')
    with self.assertRaises(MonitoringNoConfiguredTargetError):
      p = metrics_pb2.MetricsCollection()
      m.serialize_to(p)

  def test_serialze_too_many_fields(self):
    t = DeviceTarget('reg', 'net', 'host')
    m = metric.StringMetric('test', target=t,
                            fields={'a': 1, 'b': 2, 'c': 3, 'd': 4})
    m.set('val', fields={'e': 5, 'f': 6, 'g': 7})
    with self.assertRaises(MonitoringTooManyFieldsError):
      m.set('val', fields={'e': 5, 'f': 6, 'g': 7, 'h': 8})

  def test_populate_field_values(self):
    pb1 = metrics_pb2.MetricsData()
    m1 = metric.Metric('foo', fields={'asdf': 1})
    m1._populate_fields(pb1, m1._normalized_fields)
    self.assertEquals(pb1.fields[0].name, 'asdf')
    self.assertEquals(pb1.fields[0].int_value, 1)

    pb2 = metrics_pb2.MetricsData()
    m2 = metric.Metric('bar', fields={'qwer': True})
    m2._populate_fields(pb2, m2._normalized_fields)
    self.assertEquals(pb2.fields[0].name, 'qwer')
    self.assertEquals(pb2.fields[0].bool_value, True)

    pb3 = metrics_pb2.MetricsData()
    m3 = metric.Metric('baz', fields={'zxcv': 'baz'})
    m3._populate_fields(pb3, m3._normalized_fields)
    self.assertEquals(pb3.fields[0].name, 'zxcv')
    self.assertEquals(pb3.fields[0].string_value, 'baz')

  def test_invalid_field_value(self):
    pb = metrics_pb2.MetricsData()
    m = metric.Metric('test', fields={'pi': 3.14})
    with self.assertRaises(MonitoringInvalidFieldTypeError) as e:
      m._populate_fields(pb, m._normalized_fields)
    self.assertEquals(e.exception.metric, 'test')
    self.assertEquals(e.exception.field, 'pi')
    self.assertEquals(e.exception.value, 3.14)

  def test_register_unregister(self):
    self.assertEquals(0, len(self.fake_state.metrics))
    m = metric.Metric('test', fields={'pi': 3.14})
    self.assertEquals(1, len(self.fake_state.metrics))
    m.unregister()
    self.assertEquals(0, len(self.fake_state.metrics))


class StringMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metric.StringMetric('test')
    m._populate_value(pb, 'foo')
    self.assertEquals(pb.string_value, 'foo')

  def test_set(self):
    m = metric.StringMetric('test')
    m.set('hello world')
    self.assertEquals(m.get(), 'hello world')
    self.assertEquals(self.fake_send.call_count, 1)

  def test_non_string_raises(self):
    m = metric.StringMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())


class BooleanMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metric.BooleanMetric('test')
    m._populate_value(pb, True)
    self.assertEquals(pb.boolean_value, True)

  def test_set(self):
    m = metric.BooleanMetric('test')
    m.set(False)
    self.assertEquals(m.get(), False)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_toggle(self):
    m = metric.BooleanMetric('test')
    m.set(True)
    self.assertEquals(m.get(), True)
    self.assertEquals(self.fake_send.call_count, 1)
    m.toggle()
    self.assertEquals(m.get(), False)
    self.assertEquals(self.fake_send.call_count, 2)

  def test_non_bool_raises(self):
    m = metric.BooleanMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set('True')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(123)


class CounterMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metric.CounterMetric('test')
    m._populate_value(pb, 1)
    self.assertEquals(pb.counter, 1)

  def test_starts_at_zero(self):
    m = metric.CounterMetric('test')
    self.assertEquals(m.get(), 0)
    m.increment()
    self.assertEquals(m.get(), 1)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_set(self):
    m = metric.CounterMetric('test')
    m.set(10)
    self.assertEquals(m.get(), 10)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_increment(self):
    m = metric.CounterMetric('test')
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
    m = metric.CounterMetric('test')
    m.set(1)
    with self.assertRaises(MonitoringDecreasingValueError):
      m.set(0)
    with self.assertRaises(MonitoringDecreasingValueError):
      m.increment_by(-1)

  def test_non_int_raises(self):
    m = metric.CounterMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(1.5)
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.increment_by(1.5)

  def test_multiple_field_values(self):
    m = metric.CounterMetric('test')
    m.increment({'foo': 'bar'})
    m.increment({'foo': 'baz'})
    m.increment({'foo': 'bar'})
    self.assertEquals(0, m.get())
    self.assertEquals(2, m.get({'foo': 'bar'}))
    self.assertEquals(1, m.get({'foo': 'baz'}))

  def test_override_fields(self):
    m = metric.CounterMetric('test', fields={'foo': 'bar'})
    m.increment()
    m.increment({'foo': 'baz'})
    self.assertEquals(1, m.get())
    self.assertEquals(1, m.get({'foo': 'bar'}))
    self.assertEquals(1, m.get({'foo': 'baz'}))


class GaugeMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metric.GaugeMetric('test')
    m._populate_value(pb, 1)
    self.assertEquals(pb.gauge, 1)

  def test_set(self):
    m = metric.GaugeMetric('test')
    m.set(10)
    self.assertEquals(m.get(), 10)
    self.assertEquals(self.fake_send.call_count, 1)
    m.set(sys.maxint + 1)
    self.assertEquals(m.get(), sys.maxint + 1)
    self.assertEquals(self.fake_send.call_count, 2)

  def test_non_int_raises(self):
    m = metric.GaugeMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())

  def test_unset_increment_raises(self):
    m = metric.GaugeMetric('test')
    with self.assertRaises(MonitoringIncrementUnsetValueError):
      m.increment()


class CumulativeMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metric.CumulativeMetric('test')
    m._populate_value(pb, 1.618)
    self.assertAlmostEquals(pb.cumulative_double_value, 1.618)

  def test_starts_at_zero(self):
    m = metric.CumulativeMetric('test')
    self.assertEquals(m.get(), 0.0)
    m.increment()
    self.assertEquals(m.get(), 1.0)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_set(self):
    m = metric.CumulativeMetric('test')
    m.set(3.14)
    self.assertAlmostEquals(m.get(), 3.14)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_decrement_raises(self):
    m = metric.CumulativeMetric('test')
    m.set(3.14)
    with self.assertRaises(MonitoringDecreasingValueError):
      m.set(0)
    with self.assertRaises(MonitoringDecreasingValueError):
      m.increment_by(-1)

  def test_non_number_raises(self):
    m = metric.CumulativeMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())


class FloatMetricTest(MetricTestBase):

  def test_populate_value(self):
    pb = metrics_pb2.MetricsData()
    m = metric.FloatMetric('test')
    m._populate_value(pb, 1.618)
    self.assertEquals(pb.noncumulative_double_value, 1.618)

  def test_set(self):
    m = metric.FloatMetric('test')
    m.set(3.14)
    self.assertEquals(m.get(), 3.14)
    self.assertEquals(self.fake_send.call_count, 1)

  def test_non_number_raises(self):
    m = metric.FloatMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())
