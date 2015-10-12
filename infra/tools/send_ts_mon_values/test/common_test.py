# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import unittest

from infra_libs import ts_mon
from infra.tools.send_ts_mon_values import common


class ArgumentTest(unittest.TestCase):
  # send_ts_mon_values is supposed to be called from scripts. Arguments
  # are thus considered an API and must be tested for backward-compatibility.
  def test_smoke_one_flag(self):
    args = common.get_arguments(('--gauge={}',))
    self.assertIsInstance(args, argparse.Namespace)
    self.assertEquals(args.gauge, ['{}'])

  def test_smoke_one_flag_repeated(self):
    args = common.get_arguments(('--gauge={}', '--gauge={}'))
    self.assertIsInstance(args, argparse.Namespace)
    self.assertEquals(args.gauge, ['{}', '{}'])

  def test_smoke_all_flags(self):
    args = common.get_arguments(('--gauge={}',
                                 '--float={}',
                                 '--string={}',
                                 '--bool={}',
                                 '--boolean={}',
                                 '--counter={}',
                                 '--cumulative={}'))
    self.assertIsInstance(args, argparse.Namespace)


class JsonParsingTest(unittest.TestCase):
  def test_json_parsing_minimal_input(self):
    md = common.json_to_metric_data('{"name": "testname", "value": 13}')
    self.assertIsInstance(md.name, str)
    self.assertEquals(md.name, "testname")
    self.assertEquals(md.points[0].value, 13)
    self.assertIsNone(md.start_time)
    self.assertIsNone(md.points[0].fields)

  def test_json_parsing_with_fields(self):
    md = common.json_to_metric_data('{"name": "testname", "value": 13, '
                                    '"myfield": "mystring", "otherfield": 42}')
    self.assertIsInstance(md.name, str)
    self.assertEquals(md.name, "testname")
    self.assertEquals(md.points[0].value, 13)
    self.assertIsNone(md.start_time)
    self.assertEquals(md.points[0].fields,
                      {'myfield': 'mystring', 'otherfield': 42})

  def test_json_parsing_with_start_time(self):
    md = common.json_to_metric_data('{"name": "testname", "value": 13, '
                                    '"start_time": 1234}')
    self.assertIsInstance(md.name, str)
    self.assertEquals(md.name, "testname")
    self.assertEquals(md.points[0].value, 13)
    self.assertEquals(md.start_time, 1234)
    self.assertIsNone(md.points[0].fields)

  def test_json_parsing_with_missing_name(self):
    self.assertIsNone(common.json_to_metric_data(
        '{"value": 13, "start_time": 1234}'))

  def test_json_parsing_with_missing_value(self):
    self.assertIsNone(common.json_to_metric_data(
        '{"name": "test/name", "start_time": 1234}'))

  def test_json_parsing_bad_string(self):
    self.assertIsNone(common.json_to_metric_data('}'))


class test_collapse_metrics(unittest.TestCase):
  def test_collapse_metrics_empty(self):
    """Test for empty input, for coverage."""
    self.assertIsNone(common.collapse_metrics([]))

  def test_collapse_metrics_no_points(self):
    """Test when no points are present, for coverage."""
    self.assertIsNone(common.collapse_metrics([
        common.MetricData('name', None, [])]))

  def test_collapse_metrics_multi_points(self):
    """Test that it can handle multiple points in the input."""
    points1 = [common.PointData(1, {'f': 'v1'}),
               common.PointData(2, {'f': 'v2'})]
    points2 = [common.PointData(3, {'f': 'v3'}),
               common.PointData(4, {'f': 'v4'})]
    md = common.collapse_metrics([
        common.MetricData('name', None, points1),
        common.MetricData('name', None, points2)])
    self.assertEqual(md.points, points1 + points2)


class test_set_metric(unittest.TestCase):
  def test_set_no_metrics(self):
    metrics = common.set_metrics([], ts_mon.GaugeMetric)
    self.assertEqual(0, len(metrics))

  def test_set_one_metric(self):
    json_str = '{"name": "test/name", "value": 13}'
    metrics = common.set_metrics([json_str], ts_mon.GaugeMetric)
    self.assertEqual(1, len(metrics))
    self.assertIsInstance(metrics[0], ts_mon.GaugeMetric)
    for metric in metrics:
      metric.unregister()  # Cleanup

  def test_set_metric_no_input(self):
    metrics = common.set_metrics(None, ts_mon.GaugeMetric)
    self.assertEqual([], metrics)

  def test_set_one_metric_with_start_time(self):
    json_str = '{"name": "test/name", "value": 13, "start_time": 1234}'
    metrics = common.set_metrics([json_str], ts_mon.CounterMetric)
    self.assertEqual(1, len(metrics))
    self.assertIsInstance(metrics[0], ts_mon.CounterMetric)
    self.assertTrue(metrics[0].name.startswith("test/name"))
    self.assertEquals(metrics[0]._start_time, 1234)
    for metric in metrics:
      metric.unregister()  # Cleanup

  def test_set_one_metric_missing_name(self):
    json_str = '{"value": 13, "start_time": 1234}'
    metrics = common.set_metrics([json_str], ts_mon.CounterMetric)
    self.assertEqual([], metrics)

  def test_set_one_metric_missing_value(self):
    json_str = '{"name": "test/name", "start_time": 1234}'
    metrics = common.set_metrics([json_str], ts_mon.CounterMetric)
    self.assertEqual([], metrics)

  def test_set_multiple_metrics(self):
    # list of json strs, call set_metrics
    json_strs = ['{"name": "test/name1", "value": 13}',
                 '{"name": "test/name2", "value": 14}']
    metrics = common.set_metrics(json_strs, ts_mon.GaugeMetric)

    self.assertEquals(len(metrics), len(json_strs))

    for metric in metrics:
      self.assertIsInstance(metric, ts_mon.GaugeMetric)
      self.assertTrue(metric.name.startswith("test/name"))
      metric.unregister()  # Cleanup

  def test_set_multiple_points(self):
    # list of json strs, call set_metrics
    json_strs = ['{"name": "test/name", "field": "foo", "value": 13}',
                 '{"name": "test/name", "field": "bar", "value": 14}']
    metrics = common.set_metrics(json_strs, ts_mon.GaugeMetric)

    self.assertEquals(1, len(metrics))

    self.assertIsInstance(metrics[0], ts_mon.GaugeMetric)
    self.assertEqual(metrics[0].name, "test/name")
    self.assertEqual(13, metrics[0].get({'field': 'foo'}))
    self.assertEqual(14, metrics[0].get({'field': 'bar'}))
    for metric in metrics:
      metric.unregister()  # Cleanup

  def test_set_multiple_points_wrong_fields(self):
    # list of json strs, call set_metrics
    json_strs = ['{"name": "test/name", "field1": "foo", "value": 13}',
                 '{"name": "test/name", "field2": "bar", "value": 14}']
    metrics = common.set_metrics(json_strs, ts_mon.GaugeMetric)

    self.assertEquals(0, len(metrics))

  def test_set_multiple_points_wrong_start_time(self):
    # list of json strs, call set_metrics
    json_strs = [
        '{"name": "test", "field": "foo", "value": 13, "start_time": 1234}',
        '{"name": "test", "field": "baz", "value": 17, "start_time": 1234}',
        '{"name": "test", "field": "bar", "value": 14, "start_time": 123}']
    metrics = common.set_metrics(json_strs, ts_mon.CounterMetric)

    self.assertEquals(0, len(metrics))

  def test_set_multiple_metrics_with_invalid(self):
    # list of json strs, call set_metrics
    json_strs = ['{"name": "test/name1", "value": 13}',
                 '{"name": "test/name2"}',
                 '{"name": "test/name3", "value": 14}']
    metrics = common.set_metrics(json_strs, ts_mon.GaugeMetric)

    self.assertEquals(len(metrics) + 1, len(json_strs))

    for metric in metrics:
      self.assertIsInstance(metric, ts_mon.GaugeMetric)
      self.assertTrue(metric.name.startswith("test/name"))
      metric.unregister()  # Cleanup


class main_test(unittest.TestCase):
  def test_main(self):
    """Smoke test for the main function."""
    common.main(['--ts-mon-config-file', 'non-existent-file'])
