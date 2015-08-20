# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes representing the monitoring interface for tasks or devices.

Usage:
  # symlink appengine/modules/gae_ts_mon into the top level directory
  # of your appengine app

  import gae_ts_mon
  from google.appengine.api import modules

  # Sets up default target
  instance_id = hash(modules.get_current_instance_id()) % 10
  gae_ts_mon.initialize(job_name='job', instance=instance_id,
                        service_name='service', endpoint='endpoint')

  # Will use the default Target set up with initialize
  count_metric = gae_ts_mon.CounterMetric('my/metric/name', fields={})
  count_metric.set(0)
  for x in range(100):
    count_metric.increment()

  # Use a custom Target:
  t = ts_mon.TaskTarget('service', 'job', 'region', 'host')
  g_metric = ts_mon.GaugeMetric('/my/metric/name2',
                                fields={'key': 'value'},
                                target=t)
  g_metric.set(5)

  # Flush (sends metrics to monarch, already done automatically every 5m)
  gae_ts_mon.flush()

"""

import logging
import os
import random
import time

from monacq.proto import metrics_pb2

from common import errors

# The maximum number of MetricsData messages to include in each HTTP request.
# MetricsCollections larger than this will be split into multiple requests.
METRICS_DATA_LENGTH_LIMIT = 1000


class State(object):
  """Package-level state is stored here so that it is easily accessible.

  Configuration is kept in this one object at the global level so that all
  libraries in use by the same tool or service can all take advantage of the
  same configuration.
  """

  def __init__(self):
    # The Monitor object that will be used to send all metrics.
    self.global_monitor = None
    # The Target object that will be paired with all metrics that don't supply
    # their own.
    self.default_target = None
    # The flush mode being used to control when metrics are pushed.
    self.flush_mode = None
    # All metrics created by this application.
    self.metrics = set()

state = State()


def send(metric):
  """Send a single metric to the monitoring api.

  This is called automatically by Metric.set - you don't need to call it
  manually.
  """
  if state.flush_mode != 'all':
    return

  if not state.global_monitor:
    raise errors.MonitoringNoConfiguredMonitorError(metric._name)

  proto = metrics_pb2.MetricsCollection()
  metric.serialize_to(proto, default_target=state.default_target)
  state.global_monitor.send(proto)


def flush():
  """Send all metrics that are registered in the application."""
  if not state.global_monitor:
    raise errors.MonitoringNoConfiguredMonitorError(None)

  proto = metrics_pb2.MetricsCollection()

  def loop_action(proto):
    if len(proto.data) >= METRICS_DATA_LENGTH_LIMIT:
      state.global_monitor.send(proto)
      del proto.data[:]

  for metric in state.metrics:
    metric.serialize_to(proto, default_target=state.default_target,
                        loop_action=loop_action)

  state.global_monitor.send(proto)


def register(metric):
  """Adds the metric to the list of metrics sent by flush().

  This is called automatically by Metric's constructor.
  """
  # If someone is registering the same metric object twice, that's okay, but
  # registering two different metric objects with the same metric name is not.
  for m in state.metrics:
    if metric == m:
      state.metrics.remove(m)
      state.metrics.add(metric)
      return
  if any([metric._name == m._name for m in state.metrics]):
    raise errors.MonitoringDuplicateRegistrationError(metric._name)

  state.metrics.add(metric)


def unregister(metric):
  """Removes the metric from the list of metrics sent by flush()."""
  state.metrics.remove(metric)
