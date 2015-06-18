# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes representing the monitoring interface for tasks or devices.

Usage:
  import argparse
  from infra_libs import ts_mon

  p = argparse.ArgumentParser()
  ts_mon.add_argparse_options(p)
  args = p.parse_args()  # Must contain info for Monitor (and optionally Target)
  ts_mon.process_argparse_options(args)

  # Will use the default Target set up via command line args:
  m = ts_mon.BooleanMetric('/my/metric/name', fields={'foo': 1, 'bar': 'baz'})
  m.set(True)

  # Use a custom Target:
  t = ts_mon.TaskTarget('service', 'job', 'region', 'host')  # or DeviceTarget
  m2 = ts_mon.GaugeMetric('/my/metric/name2', fields={'asdf': 'qwer'}, target=t)
  m2.set(5)

Library usage:
  from infra_libs.ts_mon import CounterMetric
  # No need to set up Monitor or Target, assume calling code did that.
  c = CounterMetric('/my/counter', fields={'source': 'mylibrary'})
  c.set(0)
  for x in range(100):
    c.increment()
"""

import logging
import os
import threading
import time

from monacq.proto import metrics_pb2

from infra_libs.ts_mon import errors
from infra_libs.ts_mon import monitors
from infra_libs.ts_mon import targets


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
    # The background thread that flushes metrics every
    # --ts-mon-flush-interval-secs seconds.  May be None if
    # --ts-mon-flush != 'auto' or --ts-mon-flush-interval-secs == 0.
    self.flush_thread = None
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
  for metric in state.metrics:
    metric.serialize_to(proto, default_target=state.default_target)

  state.global_monitor.send(proto)


def register(metric):
  """Adds the metric to the list of metrics sent by flush().

  This is called automatically by Metric's constructor - you don't need to call
  it manually.
  """
  # If someone is registering the same metric object twice, that's okay, but
  # registering two different metric objects with the same metric name is not.
  if metric in state.metrics:
    return
  if any([metric._name == m._name for m in state.metrics]):
    raise errors.MonitoringDuplicateRegistrationError(metric._name)

  state.metrics.add(metric)


def unregister(metric):
  """Removes the metric from the list of metrics sent by flush()."""
  state.metrics.remove(metric)


def close():
  """Stops any background threads and waits for them to exit."""
  if state.flush_thread is not None:
    state.flush_thread.stop()


class _FlushThread(threading.Thread):
  """Background thread that flushes metrics on an interval."""

  def __init__(self, interval_secs, stop_event=None):
    super(_FlushThread, self).__init__(name='ts_mon')

    if stop_event is None:
      stop_event = threading.Event()

    self.daemon = True
    self.interval_secs = interval_secs
    self.stop_event = stop_event

  def _flush_and_log_exceptions(self):
    try:
      flush()
    except Exception:
      logging.exception('Automatic monitoring flush failed.')

  def run(self):
    next_timeout = self.interval_secs
    while True:
      if self.stop_event.wait(next_timeout):
        self._flush_and_log_exceptions()
        return

      # Try to flush every N seconds exactly so rate calculations are more
      # consistent.
      start = time.time()
      self._flush_and_log_exceptions()
      flush_duration = time.time() - start
      next_timeout = self.interval_secs - flush_duration

      if next_timeout < 0:
        logging.warning(
            'Last monitoring flush took %f seconds (longer than '
            '--ts-mon-flush-interval-secs = %f seconds)',
            flush_duration, self.interval_secs)
        next_timeout = 0

  def stop(self):
    """Stops the background thread and performs a final flush."""

    self.stop_event.set()
    self.join()
