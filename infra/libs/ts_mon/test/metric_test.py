# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import unittest

import mock

from monacq.proto import metrics_pb2

import infra.libs.ts_mon.metric as metric

from infra.libs.ts_mon.errors import MonitoringDecreasingValueError
from infra.libs.ts_mon.errors import MonitoringIncrementUnsetValueError
from infra.libs.ts_mon.errors import MonitoringInvalidFieldTypeError
from infra.libs.ts_mon.errors import MonitoringInvalidValueTypeError
from infra.libs.ts_mon.errors import MonitoringTooManyFieldsError


class MetricTest(unittest.TestCase):

  def test_populate_fields(self):
    pb1 = metrics_pb2.MetricsData()
    m1 = metric.Metric('foo', fields={'asdf': 1})
    m1._populate_fields_pb(pb1)
    self.assertEquals(pb1.fields[0].name, 'asdf')
    self.assertEquals(pb1.fields[0].int_value, 1)

    pb2 = metrics_pb2.MetricsData()
    m2 = metric.Metric('bar', fields={'qwer': True})
    m2._populate_fields_pb(pb2)
    self.assertEquals(pb2.fields[0].name, 'qwer')
    self.assertEquals(pb2.fields[0].bool_value, True)

    pb3 = metrics_pb2.MetricsData()
    m3 = metric.Metric('baz', fields={'zxcv': 'baz'})
    m3._populate_fields_pb(pb3)
    self.assertEquals(pb3.fields[0].name, 'zxcv')
    self.assertEquals(pb3.fields[0].string_value, 'baz')

  def test_too_may_fields(self):
    fields = {str(i): str(i) for i in xrange(8)}
    with self.assertRaises(MonitoringTooManyFieldsError) as e:
      metric.Metric('test', fields=fields)
    self.assertEquals(e.exception.metric, 'test')
    self.assertEquals(len(e.exception.fields), 8)

  def test_invalid_field(self):
    pb = metrics_pb2.MetricsData()
    m = metric.Metric('test', fields={'pi': 3.14})
    with self.assertRaises(MonitoringInvalidFieldTypeError) as e:
      m._populate_fields_pb(pb)
    self.assertEquals(e.exception.metric, 'test')
    self.assertEquals(e.exception.field, 'pi')
    self.assertEquals(e.exception.value, 3.14)


class StringMetricTest(unittest.TestCase):

  def test_populate_metric(self):
    pb = metrics_pb2.MetricsData()
    m = metric.StringMetric('test')
    m._value = 'foo'
    m._populate_metric_pb(pb)
    self.assertEquals(pb.string_value, 'foo')

  @mock.patch('infra.libs.ts_mon.metric.send')
  def test_set(self, fake_send):
    m = metric.StringMetric('test')
    m.set('hello world')
    self.assertEquals(m._value, 'hello world')
    self.assertEquals(fake_send.call_count, 1)

  def test_non_string_raises(self):
    m = metric.StringMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())


class BooleanMetricTest(unittest.TestCase):

  def test_populate_metric(self):
    pb = metrics_pb2.MetricsData()
    m = metric.BooleanMetric('test')
    m._value = True
    m._populate_metric_pb(pb)
    self.assertEquals(pb.boolean_value, True)

  @mock.patch('infra.libs.ts_mon.metric.send')
  def test_set(self, fake_send):
    m = metric.BooleanMetric('test')
    m.set(False)
    self.assertEquals(m._value, False)
    self.assertEquals(fake_send.call_count, 1)

  @mock.patch('infra.libs.ts_mon.metric.send')
  def test_toggle(self, fake_send):
    m = metric.BooleanMetric('test')
    m._value = True
    m.toggle()
    self.assertEquals(m._value, False)
    self.assertEquals(fake_send.call_count, 1)

  def test_non_bool_raises(self):
    m = metric.BooleanMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())


class NumericMetricTest(unittest.TestCase):

  def test_increment(self):
    m = metric.NumericMetric('test')
    def set_stub(val):
      m._value = val
    m.set = set_stub
    m._value = 1
    m.increment()
    self.assertEquals(m._value, 2)
    m.increment_by(3.14)
    self.assertAlmostEquals(m._value, 5.14)

  def test_unset_increment_raises(self):
    m = metric.NumericMetric('test')
    with self.assertRaises(MonitoringIncrementUnsetValueError):
      m.increment()


class CounterMetricTest(unittest.TestCase):

  def test_populate_metric(self):
    pb = metrics_pb2.MetricsData()
    m = metric.CounterMetric('test')
    m._value = 1
    m._populate_metric_pb(pb)
    self.assertEquals(pb.counter, 1)

  @mock.patch('infra.libs.ts_mon.metric.send')
  def test_set(self, fake_send):
    m = metric.CounterMetric('test')
    m.set(10)
    self.assertEquals(m._value, 10)
    self.assertEquals(fake_send.call_count, 1)

  def test_decrement_raises(self):
    m = metric.CounterMetric('test')
    m._value = 1
    with self.assertRaises(MonitoringDecreasingValueError):
      m.set(0)
    with self.assertRaises(MonitoringDecreasingValueError):
      m.increment_by(-1)

  def test_non_int_raises(self):
    m = metric.CounterMetric('test')
    m._value = 0
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(1.5)
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.increment_by(1.5)


class GaugeMetricTest(unittest.TestCase):

  def test_populate_metric(self):
    pb = metrics_pb2.MetricsData()
    m = metric.GaugeMetric('test')
    m._value = 1
    m._populate_metric_pb(pb)
    self.assertEquals(pb.gauge, 1)

  @mock.patch('infra.libs.ts_mon.metric.send')
  def test_set(self, fake_send):
    m = metric.GaugeMetric('test')
    m.set(10)
    self.assertEquals(m._value, 10)
    self.assertEquals(fake_send.call_count, 1)
    m.set(sys.maxint + 1)
    self.assertEquals(m._value, sys.maxint + 1)
    self.assertEquals(fake_send.call_count, 2)

  def test_non_int_raises(self):
    m = metric.GaugeMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())


class CumulativeMetricTest(unittest.TestCase):

  def test_populate_metric(self):
    pb = metrics_pb2.MetricsData()
    m = metric.CumulativeMetric('test')
    m._value = 1.618
    m._populate_metric_pb(pb)
    self.assertAlmostEquals(pb.cumulative_double_value, 1.618)

  @mock.patch('infra.libs.ts_mon.metric.send')
  def test_set(self, fake_send):
    m = metric.CumulativeMetric('test')
    m.set(3.14)
    self.assertAlmostEquals(m._value, 3.14)
    self.assertEquals(fake_send.call_count, 1)

  def test_decrement_raises(self):
    m = metric.CumulativeMetric('test')
    m._value = 3.14
    with self.assertRaises(MonitoringDecreasingValueError):
      m.set(0)
    with self.assertRaises(MonitoringDecreasingValueError):
      m.increment_by(-1)

  def test_non_number_raises(self):
    m = metric.CumulativeMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())


class FloatMetricTest(unittest.TestCase):

  def test_populate_metric(self):
    pb = metrics_pb2.MetricsData()
    m = metric.FloatMetric('test')
    m._value = 1.618
    m._populate_metric_pb(pb)
    self.assertEquals(pb.noncumulative_double_value, 1.618)

  @mock.patch('infra.libs.ts_mon.metric.send')
  def test_set(self, fake_send):
    m = metric.FloatMetric('test')
    m.set(3.14)
    self.assertEquals(m._value, 3.14)
    self.assertEquals(fake_send.call_count, 1)

  def test_non_number_raises(self):
    m = metric.FloatMetric('test')
    with self.assertRaises(MonitoringInvalidValueTypeError):
      m.set(object())
