# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import json
import logging
import os

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

  def __init__(self, base_url, metric_fields):
    if self.endpoint == 'FILE':
      self._url = base_url
    else:
      self._url = '%s/json%s' % (base_url.rstrip('/'), self.endpoint)
    self._metric_fields = metric_fields

  def poll(self):
    LOGGER.info('Requesting %s', self._url)

    try:
      response = instrumented_requests.get(self.__class__.__name__, self._url)
    except requests.exceptions.RequestException:
      LOGGER.exception('Request for %s failed', self._url)
      return False

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

  uptime = ts_mon.FloatMetric('uptime')
  accepting_builds = ts_mon.BooleanMetric('buildbot/master/accepting_builds')

  connected = ts_mon.GaugeMetric('buildbot/master/builders/connected_slaves')
  current_builds = ts_mon.GaugeMetric('buildbot/master/builders/current_builds')
  pending_builds = ts_mon.GaugeMetric('buildbot/master/builders/pending_builds')
  state = ts_mon.StringMetric('buildbot/master/builders/state')
  total = ts_mon.GaugeMetric('buildbot/master/builders/total_slaves')

  recent_builds = ts_mon.GaugeMetric(
      'buildbot/master/builders/recent_builds')

  recent_successful_build_times = ts_mon.NonCumulativeDistributionMetric(
      'buildbot/master/builders/recent_successful_build_times')
  recent_finished_build_times = ts_mon.NonCumulativeDistributionMetric(
      'buildbot/master/builders/recent_finished_build_times')

  def handle_response(self, data):
    self.uptime.set(data['server_uptime'], fields=self.fields())
    self.accepting_builds.set(data['accepting_builds'], self.fields())

    for builder_name, builder_info in data['builders'].iteritems():
      fields = self.fields({'builder': builder_name})

      self.connected.set(builder_info.get('connected_slaves', 0), fields=fields)
      self.current_builds.set(
          builder_info.get('current_builds', 0), fields=fields)
      self.pending_builds.set(
          builder_info.get('pending_builds', 0), fields=fields)
      self.state.set(builder_info.get('state', 'unknown'), fields=fields)
      self.total.set(builder_info.get('total_slaves', 0), fields=fields)

      for status, builds in builder_info.get(
          'recent_builds_by_status', {}).iteritems():
        recent_builds_fields = copy.copy(fields)
        recent_builds_fields['status'] = STATUS_TO_STRING.get(
            str(status), str(status))
        self.recent_builds.set(builds, fields=recent_builds_fields)

      successful_dist = ts_mon.Distribution(ts_mon.GeometricBucketer())
      for duration in builder_info.get('recent_successful_build_times', []):
        successful_dist.add(duration)
      self.recent_successful_build_times.set(successful_dist, fields=fields)

      finished_dist = ts_mon.Distribution(ts_mon.GeometricBucketer())
      for duration in builder_info.get('recent_finished_build_times', []):
        finished_dist.add(duration)
      self.recent_finished_build_times.set(finished_dist, fields=fields)


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
  result_count = ts_mon.CounterMetric('buildbot/master/builders/results/count')
  cycle_times = ts_mon.CumulativeDistributionMetric(
      'buildbot/master/builders/builds/durations')

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
    field_keys = ('builder', 'slave', 'result')
    fields = self.fields({k: data[k] for k in field_keys if k in data})
    self.result_count.increment(fields)
    if 'duration_s' in data:
      self.cycle_times.add(data['duration_s'], fields)
