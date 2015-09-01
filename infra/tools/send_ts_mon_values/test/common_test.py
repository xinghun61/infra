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
    self.assertEquals(md.value, 13)
    self.assertIsNone(md.start_time)
    self.assertIsNone(md.fields)

  def test_json_parsing_with_fields(self):
    md = common.json_to_metric_data('{"name": "testname", "value": 13, '
                                    '"myfield": "mystring", "otherfield": 42}')
    self.assertIsInstance(md.name, str)
    self.assertEquals(md.name, "testname")
    self.assertEquals(md.value, 13)
    self.assertIsNone(md.start_time)
    self.assertEquals(md.fields, {'myfield': 'mystring', 'otherfield': 42})

  def test_json_parsing_with_start_time(self):
    md = common.json_to_metric_data('{"name": "testname", "value": 13, '
                                    '"start_time": 1234}')
    self.assertIsInstance(md.name, str)
    self.assertEquals(md.name, "testname")
    self.assertEquals(md.value, 13)
    self.assertEquals(md.start_time, 1234)
    self.assertIsNone(md.fields)

  def test_json_parsing_with_missing_name(self):
    with self.assertRaises(KeyError):
      common.json_to_metric_data('{"value": 13, "start_time": 1234}')

  def test_json_parsing_with_missing_value(self):
    with self.assertRaises(KeyError):
      common.json_to_metric_data('{"name": "test/name", "start_time": 1234}')


class test_set_metric(unittest.TestCase):
  def test_set_one_metric(self):
    json_str = '{"name": "test/name", "value": 13}'
    metric = common.set_metric(json_str, ts_mon.GaugeMetric)
    self.assertIsInstance(metric, ts_mon.GaugeMetric)
    ts_mon.unregister(metric)  # Cleanup

  def test_set_metric_no_input(self):
    metric = common.set_metric(None, ts_mon.GaugeMetric)
    self.assertIsNone(metric)

  def test_set_one_metric_with_start_time(self):
    json_str = '{"name": "test/name", "value": 13, "start_time": 1234}'
    metric = common.set_metric(json_str, ts_mon.CounterMetric)
    self.assertIsInstance(metric, ts_mon.CounterMetric)
    self.assertTrue(metric._name.startswith("test/name"))
    self.assertEquals(metric._start_time, 1234)
    ts_mon.unregister(metric)  # Cleanup

  def test_set_one_metric_missing_name(self):
    json_str = '{"value": 13, "start_time": 1234}'
    metric = common.set_metric(json_str, ts_mon.CounterMetric)
    self.assertIsNone(metric)

  def test_set_one_metric_missing_value(self):
    json_str = '{"name": "test/name", "start_time": 1234}'
    metric = common.set_metric(json_str, ts_mon.CounterMetric)
    self.assertIsNone(metric)

  def test_set_multiple_metrics(self):
    # list of json strs, call set_metrics
    json_strs = ['{"name": "test/name1", "value": 13}',
                 '{"name": "test/name2", "value": 14}']
    metrics = common.set_metrics(json_strs, ts_mon.GaugeMetric)

    self.assertEquals(len(metrics), len(json_strs))

    for metric in metrics:
      self.assertIsInstance(metric, ts_mon.GaugeMetric)
      # TODO(pgervais): Add a property to ts_mon.Metric instead.
      self.assertTrue(metric._name.startswith("test/name"))
      ts_mon.unregister(metric)  # Cleanup

  def test_set_multiple_metrics_with_invalid(self):
    # list of json strs, call set_metrics
    json_strs = ['{"name": "test/name1", "value": 13}',
                 '{"name": "test/name2"}',
                 '{"name": "test/name3", "value": 14}']
    metrics = common.set_metrics(json_strs, ts_mon.GaugeMetric)

    self.assertEquals(len(metrics), len(json_strs))
    self.assertIsNone(metrics[1])
    metrics.pop(1)

    for metric in metrics:
      self.assertIsInstance(metric, ts_mon.GaugeMetric)
      # TODO(pgervais): Add a property to ts_mon.Metric instead.
      self.assertTrue(metric._name.startswith("test/name"))
      ts_mon.unregister(metric)  # Cleanup
