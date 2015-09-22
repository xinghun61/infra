# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""CLI to send data via ts_mon from outside infra.git."""

import argparse
import collections
import itertools
import logging
import json
import textwrap

from infra_libs import ts_mon
import infra_libs.logs

LOGGER = logging.getLogger(__name__)

MetricData = collections.namedtuple('MetricData',
                                    ('name', 'start_time', 'points'))
PointData = collections.namedtuple('PointData', ('value', 'fields'))


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
        --float='{"name":"task/m2", "value":45}' \\
        --counter='{"name":"task/count", "start_time": 149523409000000, \\
                    "value": 42}'

    The argument to a metric argument (like --gauge, --float) must be a json
    string. The names 'name', 'value' and 'start_time' are reserved because
    they represent the metric name, and value (start_time only for --counter and
    --cumulative, in microseconds since UNIX epoch). All the other keys are
    expected to be metric fields (with a maximum of seven).

    Note, that all points in the same metric must have the same set of metric
    fields. This must be true for all instances of the metric globally,
    otherwise the metric will be rejected by the ts_mon endpoint.

    Also, all cumulative metric points must have the same start_time value.
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
  """Parse arguments given to a metric flag.

  Args:
    json_str (str): JSON string describing a metric point.

  Returns:
    MetricData or None: parsed metric if JSON is valid, otherwise None.
  """
  try:
    fields = json.loads(json_str)
    metric_name = str(fields.pop('name'))
    metric_value = fields.pop('value')
  except ValueError:
    LOGGER.error("Invalid json string: %s", str(json_str))
    return None
  except KeyError:
    LOGGER.error("Missing required fields ('name', 'value') in json string: %s",
                 str(json_str))
    return None
  start_time = fields.pop('start_time', None)
  if not fields:
    fields = None
  metric_points = [PointData(metric_value, fields)]
  return MetricData(metric_name, start_time, metric_points)


def set_metrics(json_strs, metric_type):
  """Create metrics and set their values.

  Args:
    json_str (str): json dict with keys 'name', 'value', plus at most 7 other.
    metric_type (ts_mon.Metric): any class deriving from ts_mon.Metric.
      For ex. ts_mon.GaugeMetric.

  Returns:
    metric (list of metric_type): the metric instances, filled.
  """
  if not json_strs:
    return []

  decoded_metrics = [json_to_metric_data(s) for s in json_strs]
  grouped_metrics = group_metrics(decoded_metrics)
  collapsed_metrics = [
      collapse_metrics(m) for m in grouped_metrics.itervalues()]
  return [set_metric(md, metric_type) for md in collapsed_metrics if md]


def group_metrics(metrics):
  """Given signleton MetricData points, group them by metric name.

  Args:
    metrics (list of MetricData or None): each element is has a single point.

  Returns:
    dict: a mapping of metric names to the list of correspoinding MetricData.

  Skip entries that are None, but otherwise don't do any validation.
  """
  grouped_metrics = {}
  for metric in metrics:
    if not metric:
      continue
    grouped_metrics.setdefault(metric.name, []).append(metric)
  return grouped_metrics


def collapse_metrics(metrics):
  """Collapses a list of MetricData objects into a single MetricData object.

  Validates that the points are consistent, i.e. have the same set of fields,
  and the same start_time, if present.

  Assumes that all metrics have the same metric name.

  Args:
    metrics (list of MetricData): list of MetricData objects.

  Returns:
    MetricData on None: collects all points from input metrics into a single
      list of points.
  """
  if not metrics:
    return None
  metric_name = metrics[0].name
  metric_start_time = metrics[0].start_time
  assert all(m.name == metric_name for m in metrics)

  if not all(m.start_time == metric_start_time for m in metrics):
    LOGGER.error(
        "Start time must match in all points of %s. Skipping this metric.",
        metric_name)
    return None

  points = list(itertools.chain.from_iterable(m.points for m in metrics))
  if not points:
    return None

  def get_fields_set(point):
    if point.fields:
      return set(point.fields.iterkeys())
    else:
      return set()

  fields = get_fields_set(points[0])
  if not all(get_fields_set(p) == fields for p in points):
    LOGGER.error('Metric %s: all points must have the same number of fields. '
                 'The metric was not sent.', metric_name)
    return None
  return MetricData(metric_name, metric_start_time, points)


def set_metric(metric_data, metric_type):
  """Create one metric and set its value.

  Args:
    metric_data (MetricData):
      All points for the metric are aggregated into ``points`` field.
    metric_type (ts_mon.Metric): any class deriving from ts_mon.Metric.
      For ex. ts_mon.GaugeMetric.

  Returns:
    metric (metric_type): the metric instance, filled.
  """
  if metric_type in (ts_mon.CumulativeMetric, ts_mon.CounterMetric):
    metric = metric_type(metric_data.name, start_time=metric_data.start_time)
  else:
    metric = metric_type(metric_data.name)

  for point in metric_data.points:
    metric.set(point.value, point.fields)
  return metric


def main(argv):
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
