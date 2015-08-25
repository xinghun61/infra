# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import subprocess
import sys
import time

import yaml

from infra_libs import ts_mon

if sys.platform == 'win32':  # pragma: no cover
  from infra.services.sysmon import puppet_metrics_win32


config_version = ts_mon.GaugeMetric('puppet/version/config')
puppet_version = ts_mon.StringMetric('puppet/version/puppet')
events = ts_mon.GaugeMetric('puppet/events')
resources = ts_mon.GaugeMetric('puppet/resources')
times = ts_mon.FloatMetric('puppet/times')
age = ts_mon.FloatMetric('puppet/age')


def reset_metrics_for_unittest():
  for metric in (config_version, puppet_version, events, resources, times, age):
    metric.reset()


def _lastrunfile():  # pragma: no cover
  if sys.platform == 'win32':
    return os.path.join(puppet_metrics_win32.common_appdata_path(),
                        'PuppetLabs\\puppet\\var\\state\\last_run_summary.yaml')
  return '/var/lib/puppet_last_run_summary.yaml'


def get_puppet_summary(time_fn=time.time):
  path = _lastrunfile()
  logging.info('Using puppet lastrunfile: %s', path)

  try:
    with open(path) as fh:
      data = yaml.safe_load(fh)
  except IOError:
    # This is fine - the system probably isn't managed by puppet.
    return
  except yaml.YAMLError:
    # This is less fine - the file exists but is invalid.
    logging.exception('Failed to read puppet lastrunfile %s', path)
    return

  if not isinstance(data, dict):
    return

  try:
    config_version.set(data['version']['config'])
  except KeyError:
    logging.warning('version/config not found in %s', path)

  try:
    puppet_version.set(data['version']['puppet'])
  except KeyError:
    logging.warning('version/puppet not found in %s', path)

  try:
    for key, value in data['events'].iteritems():
      if key != 'total':
        events.set(value, {'result': key})
  except KeyError:
    logging.warning('events not found in %s', path)

  try:
    for key, value in data['resources'].iteritems():
      resources.set(value, {'action': key})
  except KeyError:
    logging.warning('resources not found in %s', path)

  try:
    for key, value in data['time'].iteritems():
      if key == 'last_run':
        age.set(time_fn() - value)
      elif key != 'total':
        times.set(value, {'step': key})
  except KeyError:
    logging.warning('time not found in %s', path)
