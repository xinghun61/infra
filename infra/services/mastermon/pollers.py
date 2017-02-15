# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import json
import logging
import os
import time

import requests

from infra_libs import instrumented_requests
from infra_libs import ts_mon

LOGGER = logging.getLogger(__name__)


# These values are buildbot constants used for Build and BuildStep.
# This line was copied from master/buildbot/status/builder.py.
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY = range(6)


STATUS_TO_STRING = {
  str(SUCCESS): 'success',
  str(WARNINGS): 'warnings',
  str(FAILURE): 'failure',
  str(SKIPPED): 'skipped',
  str(EXCEPTION): 'exception',
  str(RETRY): 'retry',
}


class Poller(object):
  endpoint = None

  durations = ts_mon.CumulativeDistributionMetric(
      'buildbot/master/poller_durations',
      'Time (in milliseconds) taken for the buildbot master to respond to the '
      'request from mastermon',
      [ts_mon.StringField('master'), ts_mon.StringField('poller')])

  def __init__(self, base_url, metric_fields, time_fn=time.time):
    if self.endpoint == 'FILE':
      self._url = base_url
    else:
      self._url = '%s/json%s' % (base_url.rstrip('/'), self.endpoint)
    self._metric_fields = metric_fields
    self._time_fn = time_fn
    assert self._metric_fields.keys() == ['master']

  def poll(self):
    LOGGER.info('Requesting %s', self._url)

    start_time = self._time_fn()
    poller_name = self.__class__.__name__
    try:
      response = instrumented_requests.get(poller_name, self._url, timeout=10)
    except requests.exceptions.RequestException:
      LOGGER.exception('Request for %s failed', self._url)
      return False
    finally:
      self.durations.add((self._time_fn() - start_time) * 1000,
                         fields=self.fields({'poller': poller_name}))

    if response.status_code != requests.codes.ok:
      LOGGER.warning('Got status code %d from %s',
                     response.status_code, self._url)
      return False

    try:
      json_data = response.json()
    except Exception:
      LOGGER.exception('Failed to parse response from %s as JSON: %s',
                       self._url, response.text)
      return False

    self.handle_response(json_data)
    return True

  def handle_response(self, data):
    raise NotImplementedError

  def fields(self, extra_fields=None):
    if extra_fields is None:
      return self._metric_fields

    ret = self._metric_fields.copy()
    ret.update(extra_fields)
    return ret


class VarzPoller(Poller):
  endpoint = '/varz'

  field_spec = [ts_mon.StringField('master')]
  builder_field_spec = [ts_mon.StringField('master'),
                        ts_mon.StringField('builder')]

  uptime = ts_mon.FloatMetric('buildbot/master/uptime',
      'Time (in seconds) since the master was started',
      field_spec)
  accepting_builds = ts_mon.BooleanMetric('buildbot/master/accepting_builds',
      'Whether the master\'s BuildRequestDistributor is running',
      field_spec)

  connected = ts_mon.GaugeMetric('buildbot/master/builders/connected_slaves',
      'Number of slaves currently connected, per builder',
      builder_field_spec)
  current_builds = ts_mon.GaugeMetric('buildbot/master/builders/current_builds',
      'Number of builds currently running, per builder',
      builder_field_spec)
  pending_builds = ts_mon.GaugeMetric('buildbot/master/builders/pending_builds',
      'Number of builds pending, per builder',
      builder_field_spec)
  state = ts_mon.StringMetric('buildbot/master/builders/state',
      'State of this builder - building, idle, or offline',
      builder_field_spec)
  total = ts_mon.GaugeMetric('buildbot/master/builders/total_slaves',
      'Number of slaves configured on this builder - connected or not',
      builder_field_spec)

  pool_queue = ts_mon.GaugeMetric('buildbot/master/thread_pool/queue',
      'Number of runnables queued in the database thread pool',
      field_spec)
  pool_waiting = ts_mon.GaugeMetric('buildbot/master/thread_pool/waiting',
      'Number of idle workers for the database thread pool',
      field_spec)
  pool_working = ts_mon.GaugeMetric('buildbot/master/thread_pool/working',
      'Number of running workers for the database thread pool',
      field_spec)

  def handle_response(self, data):
    self.uptime.set(data['server_uptime'], fields=self.fields())
    self.accepting_builds.set(data['accepting_builds'], fields=self.fields())

    for builder_name, builder_info in data['builders'].iteritems():
      fields = self.fields({'builder': builder_name})

      self.connected.set(builder_info.get('connected_slaves', 0), fields=fields)
      self.current_builds.set(
          builder_info.get('current_builds', 0), fields=fields)
      self.pending_builds.set(
          builder_info.get('pending_builds', 0), fields=fields)
      self.state.set(builder_info.get('state', 'unknown'), fields=fields)
      self.total.set(builder_info.get('total_slaves', 0), fields=fields)

    if 'db_thread_pool' in data:
      db_thread_pool = data['db_thread_pool']
      fields = self.fields()
      self.pool_queue.set(db_thread_pool.get('queue', 0), fields=fields)
      self.pool_waiting.set(db_thread_pool.get('waiting', 0), fields=fields)
      self.pool_working.set(db_thread_pool.get('working', 0), fields=fields)


def safe_remove(filename):
  try:
    os.remove(filename)
  except OSError as e:
    LOGGER.error('Could not remove rotated file %s: %s', filename, e)


def rotated_filename(filename):
  return '%s.1' % filename


class FilePoller(Poller):
  """Poll a file instead of an endpoint.

  The base_url in __init__ must be the file path.  The file is assumed
  to contain JSON objects, one per line.

  The poller will first rotate the file (rename), read it, and delete
  the file.  The writer of the file is expected to create a new file if
  it was rotated or deleted.
  """
  endpoint = 'FILE'
  fields_from_json = [
      ts_mon.StringField('builder'),
      ts_mon.StringField('slave'),
      ts_mon.StringField('result'),
      ts_mon.StringField('project_id'),
      ts_mon.StringField('subproject_tag'),
  ]

  field_spec = fields_from_json + [
      ts_mon.StringField('master'),
  ]

  ### These metrics are sent when a build finishes.
  result_count = ts_mon.CounterMetric('buildbot/master/builders/results/count',
      'Number of items consumed from ts_mon.log by mastermon',
      field_spec)
  # A custom bucketer with 12% resolution in the range of 1..10**5,
  # better suited for build cycle times.
  bucketer = ts_mon.GeometricBucketer(
      growth_factor=10**0.05, num_finite_buckets=100)
  cycle_times = ts_mon.CumulativeDistributionMetric(
      'buildbot/master/builders/builds/durations',
      'Durations (in seconds) that slaves spent actively doing work towards '
      'builds for each builder',
      field_spec, bucketer=bucketer)
  pending_times = ts_mon.CumulativeDistributionMetric(
      'buildbot/master/builders/builds/pending_durations',
      'Durations (in seconds) that the master spent waiting for slaves to '
      'become available for each builder',
      field_spec, bucketer=bucketer)
  total_times = ts_mon.CumulativeDistributionMetric(
      'buildbot/master/builders/builds/total_durations',
      'Total duration (in seconds) that builds took to complete for each '
      'builder',
      field_spec, bucketer=bucketer)

  pre_test_times = ts_mon.CumulativeDistributionMetric(
      'buildbot/master/builders/builds/pre_test_durations',
      'Durations (in seconds) that builds spent before their "before_tests" '
      'step',
      field_spec, bucketer=bucketer)

  def poll(self):
    LOGGER.info('Collecting results from %s', self._url)

    if not os.path.isfile(self._url):
      LOGGER.info('No file found, assuming no data: %s', self._url)
      return True

    try:
      rotated_name = rotated_filename(self._url)
      # Remove the previous rotated file. We keep it on disk after
      # processing for debugging.
      safe_remove(rotated_name)
      os.rename(self._url, rotated_name)
      with open(rotated_name, 'r') as f:
        for line in f:  # pragma: no branch
          self.handle_response(json.loads(line))
    except (ValueError, OSError, IOError) as e:
      LOGGER.error('Could not collect or send results from %s: %s',
                   self._url, e)

    # Never return False - we don't know if master is down.
    return True

  def handle_response(self, data):
    # We handle two cases here: whether the data was generated when a build
    # finished or when a step finished. We use the content of the json dict to
    # tell the difference.

    if 'step_result' not in data:  # We only care about builds
      fields = self.fields({f.name: data.get(f.name, 'unknown')
                            for f in self.fields_from_json})
      self.result_count.increment(fields)
      if 'duration_s' in data:
        self.cycle_times.add(data['duration_s'], fields)
      if 'pending_s' in data:
        self.pending_times.add(data['pending_s'], fields)
      if 'total_s' in data:
        self.total_times.add(data['total_s'], fields)
      if 'pre_test_time_s' in data:
        self.pre_test_times.add(data['pre_test_time_s'], fields)
