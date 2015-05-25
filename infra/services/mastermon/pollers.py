# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging

import requests

from infra.libs import ts_mon

LOGGER = logging.getLogger(__name__)


class Poller(object):
  endpoint = None

  def __init__(self, base_url):
    self.url = '%s/json%s' % (base_url, self.endpoint)

  def poll(self):
    LOGGER.info('Requesting %s', self.url)

    response = requests.get(self.url)
    if response.status_code != requests.codes.ok:
      return False

    self.handle_response(response.json())
    return True

  def handle_response(self, data):
    raise NotImplementedError


class ClockPoller(Poller):
  endpoint = '/clock'
  uptime = ts_mon.FloatMetric('uptime')

  def handle_response(self, data):
    self.uptime.set(data['server_uptime'])


class BuildStatePoller(Poller):
  endpoint = '/buildstate'
  accepting_builds = ts_mon.BooleanMetric('buildbot/master/accepting_builds')
  current_builds = ts_mon.GaugeMetric('buildbot/master/builders/current_builds')
  pending_builds = ts_mon.GaugeMetric('buildbot/master/builders/pending_builds')
  state = ts_mon.StringMetric('buildbot/master/builders/state')

  def handle_response(self, data):
    self.accepting_builds.set(data['accepting_builds'])

    for builder in data['builders']:
      labels = {'builder': builder['builderName']}
      self.current_builds.set(len(builder['currentBuilds']), labels)
      self.pending_builds.set(builder['pendingBuilds'], labels)
      self.state.set(builder['state'], labels)


class SlavesPoller(Poller):
  endpoint = '/slaves'
  total = ts_mon.GaugeMetric('buildbot/master/builders/total_slaves')
  connected = ts_mon.GaugeMetric('buildbot/master/builders/connected_slaves')
  running_builds = ts_mon.GaugeMetric('buildbot/master/builders/running_builds')

  def handle_response(self, data):
    def increment(dictionary, builder_names, delta=1):
      for builder_name in builder_names:
        dictionary[builder_name] += delta

    def set_metric(dictionary, metric):
      for builder_name, value in dictionary.iteritems():
        metric.set(value, {'builder': builder_name})

    totals = collections.defaultdict(int)
    connected = collections.defaultdict(int)
    running_builds = collections.defaultdict(int)

    for slave in data.values():
      builder_names = slave['builders'].keys()
      increment(totals, builder_names)
      if slave['connected']:
        increment(connected, builder_names)
      if slave['runningBuilds']:
        increment(running_builds, builder_names)

    set_metric(totals, self.total)
    set_metric(connected, self.connected)
    set_metric(running_builds, self.running_builds)
