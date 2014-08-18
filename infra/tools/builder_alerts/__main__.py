#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import datetime
import json
import logging
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

from slave import gatekeeper_ng_config


CACHE_PATH = 'build_cache'


def apply_gatekeeper_rules(alerts, gatekeeper):
  filtered_alerts = []
  for alert in alerts:
    master_url = alert['master_url']
    master_name = buildbot.master_name_from_url(master_url)
    config = gatekeeper.get(master_url)
    if not config:
      # Unclear if this should be set or not?
      # alert['would_close_tree'] = False
      filtered_alerts.append(alert)
      continue
    excluded_builders = gatekeeper_extras.excluded_builders(config)
    if alert['builder_name'] in excluded_builders:
      continue
    alert['would_close_tree'] = \
      gatekeeper_extras.would_close_tree(config,
        alert['builder_name'], alert['step_name'])
    filtered_alerts.append(alert)
    alert['tree_name'] = gatekeeper_extras.tree_for_master(master_name)
  return filtered_alerts


def fetch_master_urls(gatekeeper, args):
  # Currently using gatekeeper.json, but could use:
  # https://chrome-infra-stats.appspot.com/_ah/api#p/stats/v1/stats.masters.list
  master_urls = gatekeeper.keys()
  if args.master_filter:
    master_urls = [url for url in master_urls if args.master_filter not in url]
  return master_urls


def main(args):
  logging.basicConfig(level=logging.DEBUG)

  parser = argparse.ArgumentParser()
  parser.add_argument('data_url', action='store', nargs='*')
  parser.add_argument('--use-cache', action='store_true')
  parser.add_argument('--master-filter', action='store')
  parser.add_argument('--builder-filter', action='store')
  args = parser.parse_args(args)

  if not args.data_url:
    logging.warn("No /data url passed, will write to builder_alerts.json")

  if args.use_cache:
    requests_cache.install_cache('failure_stats')
  else:
    requests_cache.install_cache(backend='memory')

  # FIXME: gatekeeper_config should find gatekeeper.json for us.
  gatekeeper_path = os.path.join(build_scripts_dir, 'slave', 'gatekeeper.json')
  gatekeeper = gatekeeper_ng_config.load_gatekeeper_config(gatekeeper_path)
  master_urls = fetch_master_urls(gatekeeper, args)
  start_time = datetime.datetime.now()

  latest_builder_info = {}

  cache = buildbot.BuildCache(CACHE_PATH)

  alerts = []
  for master_url in master_urls:
    master_json = buildbot.fetch_master_json(master_url)
    master_alerts = alert_builder.alerts_for_master(cache,
        master_url, master_json, args.builder_filter)
    alerts.extend(master_alerts)

    # FIXME: This doesn't really belong here. garden-o-matic wants
    # this data and we happen to have the builder json cached at
    # this point so it's cheap to compute.
    builder_info = buildbot.latest_builder_info_for_master(cache,
        master_url, master_json)
    latest_builder_info.update(builder_info)


  print "Fetch took: %s" % (datetime.datetime.now() - start_time)

  alerts = apply_gatekeeper_rules(alerts, gatekeeper)

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
