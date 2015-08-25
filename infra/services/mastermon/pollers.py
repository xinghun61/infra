# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging

import requests

from infra_libs import instrumented_requests
from infra_libs import ts_mon

LOGGER = logging.getLogger(__name__)


class Poller(object):
  endpoint = None

  def __init__(self, base_url, metric_fields):
    self._url = '%s/json%s' % (base_url.rstrip('/'), self.endpoint)
    self._metric_fields = metric_fields

  def poll(self):
    LOGGER.info('Requesting %s', self._url)

    try:
      response = instrumented_requests.get(self.__class__.__name__, self._url)
    except requests.exceptions.RequestException:
      logging.exception('Request for %s failed', self._url)
      return False

    if response.status_code != requests.codes.ok:
      LOGGER.warning('Got status code %d from %s',
                     response.status_code, self._url)
      return False

    try:
      json = response.json()
    except Exception:
      LOGGER.exception('Failed to parse response from %s as JSON: %s',
                       self._url, response.text)
      return False

    self.handle_response(json)
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
