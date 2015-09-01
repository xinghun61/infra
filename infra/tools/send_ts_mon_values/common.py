# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""CLI to send data via ts_mon from outside infra.git."""

import argparse
import collections
import logging
import json
import textwrap

from infra_libs import ts_mon
import infra_libs.logs

LOGGER = logging.getLogger(__name__)

MetricData = collections.namedtuple('MetricData',
                                    ('name', 'value', 'start_time', 'fields'))


def get_arguments(argv):
  parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent("""
    CLI to send data via ts_mon from outside infra.git.
    Example invocation:

    run.py infra.tools.send_ts_mon_values \\
        --verbose
        --ts-mon-endpoint=file:///tmp/send_ts_mon_value.log \\
        --ts-mon-target-type task \\
        --ts-mon-task-service-name generic_system \\
        --ts-mon-task-job-name chromium \\
        --gauge='{"name":"task/m1", "value":18, "custom_field": "value"}' \\
        --float='{"name":"task/m2", "value":45}'

    The argument to a metric argument (like --gauge, --float) must be a json
    string. The names 'name', 'value' and 'start_time' are reserved because
    they represent the metric name, and value (start_time only for --counter and
    --cumulative). All the other keys are expected to be metric fields (with
    a maximum of seven).
    """))

  metrics_group = parser.add_argument_group('Metric types')
  metrics_group.add_argument('--gauge', metavar='JSON', action='append',
                             help="Send data for a gauge metric.")
  metrics_group.add_argument('--float', metavar='JSON', action='append',
                             help="Send data for a float metric.")
  metrics_group.add_argument('--string', metavar='JSON', action='append',
                             help="Send data for a string metric.")
  metrics_group.add_argument('--bool', '--boolean',
                             metavar='JSON', action='append',
                             help="Send data for a boolean metric.")
  metrics_group.add_argument('--counter', metavar='JSON', action='append',
                             help="Send data for a counter metric.")
  metrics_group.add_argument('--cumulative', metavar='JSON', action='append',
                             help="Send data for a cumulative metric.")

  infra_libs.logs.add_argparse_options(parser)
  ts_mon.add_argparse_options(parser)
  args = parser.parse_args(argv)
  # Forcing manual flush here for efficiency.
  args.ts_mon_flush = 'manual'
  return args


def json_to_metric_data(json_str):
  """Parse arguments given to a metric flag"""
  fields = json.loads(json_str)
  metric_name = str(fields.pop('name'))
  metric_value = fields.pop('value')
  start_time = fields.pop('start_time', None)
  if not fields:
    fields = None
  return MetricData(metric_name, metric_value, start_time, fields)


def set_metrics(json_strs, metric_type):
  """Create metrics and set their values.

  Args:
    json_str (str): json dict with keys 'name', 'value', plus at most 7 other.
    metric_type (ts_mon.Metric): any class deriving from ts_mon.Metric.
      For ex. ts_mon.GaugeMetric.

  Returns:
    metric (list of metric_type): the metric instances, filled.
  """
  return [set_metric(json_str, metric_type) for json_str in json_strs or []]


def set_metric(json_str, metric_type):
  """Create one metric and set its value.

  Args:
    json_str (str): json dict with keys 'name', 'value', plus at most 7 other.
    metric_type (ts_mon.Metric): any class deriving from ts_mon.Metric.
      For ex. ts_mon.GaugeMetric.

  Returns:
    metric (metric_type): the metric instance, filled.
  """
  if json_str is None:
    return
  try:
    md = json_to_metric_data(json_str)
  except KeyError:
    LOGGER.exception("Invalid json string: %s", str(json_str))
    return

  if metric_type in (ts_mon.CumulativeMetric, ts_mon.CounterMetric):
    metric = metric_type(md.name, start_time=md.start_time)
  else:
    metric = metric_type(md.name)

  metric.set(md.value, md.fields)
  return metric


def main(argv):  # pragma: no cover
  args = get_arguments(argv)
  infra_libs.logs.process_argparse_options(args)
  ts_mon.process_argparse_options(args)

  set_metrics(args.gauge, ts_mon.GaugeMetric)
  set_metrics(args.float, ts_mon.FloatMetric)
  set_metrics(args.string, ts_mon.StringMetric)
  set_metrics(args.bool, ts_mon.BooleanMetric)
  set_metrics(args.counter, ts_mon.CounterMetric)
  set_metrics(args.cumulative, ts_mon.CumulativeMetric)

  ts_mon.flush()
