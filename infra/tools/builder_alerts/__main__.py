#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import datetime
import json
import logging
import multiprocessing
import sys
import os

import requests
import requests_cache

from infra.tools.builder_alerts import analysis
from infra.tools.builder_alerts import buildbot
from infra.tools.builder_alerts import gatekeeper_extras
from infra.tools.builder_alerts import alert_builder


import infra
infra_module_path = os.path.dirname(os.path.abspath(infra.__file__))
infra_dir = os.path.dirname(infra_module_path)
top_dir = os.path.dirname(infra_dir)
build_scripts_dir = os.path.join(top_dir, 'build', 'scripts')
sys.path.insert(0, build_scripts_dir)

# Our sys.path hacks are too bursting with chest-hair for pylint's little brain.
from slave import gatekeeper_ng_config  # pylint: disable=F0401


CACHE_PATH = 'build_cache'
# We have 13 masters. No point in spawning more processes
PARALLEL_TASKS = 13
CONCURRENT_TASKS = 16


class SubProcess(object):
  def __init__(self, cache, old_alerts, builder_filter, jobs):
    super(SubProcess, self).__init__()
    self._cache = cache
    self._old_alerts = old_alerts
    self._builder_filter = builder_filter
    self._jobs = jobs

  def __call__(self, master_url):
    master_json = buildbot.fetch_master_json(master_url)
    if not master_json:
      return (None, None)

    master_alerts = alert_builder.alerts_for_master(self._cache,
        master_url, master_json, self._old_alerts, self._builder_filter,
        self._jobs)

    # FIXME: This doesn't really belong here. garden-o-matic wants
    # this data and we happen to have the builder json cached at
    # this point so it's cheap to compute.
    builder_info = buildbot.latest_builder_info_for_master(self._cache,
        master_url, master_json)
    return (master_alerts, builder_info)


def main(args):
  parser = argparse.ArgumentParser(prog='run.py %s' % __package__)
  parser.add_argument('data_url', action='store', nargs='*')
  parser.add_argument('--use-cache', action='store_true')
  parser.add_argument('--master-filter', action='store')
  parser.add_argument('--builder-filter', action='store')
  parser.add_argument('--processes', default=PARALLEL_TASKS, action='store')
  parser.add_argument('--jobs', default=CONCURRENT_TASKS, action='store')
  # FIXME: Ideally we'd have adjustable logging instead of just DEBUG vs. CRIT.
  parser.add_argument("-v", "--verbose", action='store_true')

  gatekeeper_json = os.path.join(build_scripts_dir, 'slave', 'gatekeeper.json')
  parser.add_argument('--gatekeeper', action='store', default=gatekeeper_json)
  args = parser.parse_args(args)

  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.CRITICAL)

  if not args.data_url:
    logging.warn("No /data url passed, will write to builder_alerts.json")

  if args.use_cache:
    requests_cache.install_cache('failure_stats')
  else:
    requests_cache.install_cache(backend='memory')

  # FIXME: gatekeeper_config should find gatekeeper.json for us.
  gatekeeper_path = os.path.abspath(args.gatekeeper)
  logging.debug("Processsing gatekeeper json: %s", gatekeeper_path)
  gatekeeper = gatekeeper_ng_config.load_gatekeeper_config(gatekeeper_path)

  gatekeeper_trees_path = os.path.join(os.path.dirname(gatekeeper_path),
                                       'gatekeeper_trees.json')
  logging.debug('Processing gatekeeper trees json: %s', gatekeeper_trees_path)
  gatekeeper_trees = gatekeeper_ng_config.load_gatekeeper_tree_config(
      gatekeeper_trees_path)

  master_urls = gatekeeper_extras.fetch_master_urls(gatekeeper, args)
  start_time = datetime.datetime.now()

  cache = buildbot.DiskCache(CACHE_PATH)

  old_alerts = {}
  if args.data_url:
    try:
      old_alerts_raw = requests.get(args.data_url[0]).json()
    except ValueError:
      logging.debug('No old alerts found.')
    else:
      for alert in old_alerts_raw['alerts']:
        master = alert['master_url']
        builder = alert['builder_name']
        step = alert['step_name']
        reason = alert['reason']
        alert_key = alert_builder.generate_alert_key(
            master, builder, step, reason)

        if alert_key in old_alerts:
          logging.critical('Incorrectly overwriting an alert reason from the'
              ' old alert data. master: %s, builder: %s, step: %s, reason:'
              ' %s' % (master, builder, step, reason))

        old_alerts[alert_key] = alert

  latest_builder_info = {}
  alerts = []

  pool = multiprocessing.Pool(processes=args.processes)
  master_datas = pool.map(SubProcess(cache, old_alerts, args.builder_filter,
      args.jobs), master_urls)
  pool.close()
  pool.join()

  for data in master_datas:
    if not data[0]:
      continue
    alerts.extend(data[0])
    latest_builder_info.update(data[1])

  print "Fetch took: %s" % (datetime.datetime.now() - start_time)

  alerts = gatekeeper_extras.apply_gatekeeper_rules(alerts, gatekeeper,
                                                    gatekeeper_trees)

  alerts = analysis.assign_keys(alerts)
  reason_groups = analysis.group_by_reason(alerts)
  range_groups = analysis.merge_by_range(reason_groups)
  data = { 'content': json.dumps({
      'alerts': alerts,
      'reason_groups': reason_groups,
      'range_groups': range_groups,
      'latest_builder_info': latest_builder_info,
  })}

  if not args.data_url:
    with open('builder_alerts.json', 'w') as f:
      f.write(json.dumps(data, indent=1))

  for url in args.data_url:
    logging.info('POST %s alerts to %s' % (len(alerts), url))
    requests.post(url, data=data)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
