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

# Our sys.path hacks are too bursting with chest-hair for pylint's little brain.
from slave import gatekeeper_ng_config  # pylint: disable=F0401


CACHE_PATH = 'build_cache'


def main(args):
  parser = argparse.ArgumentParser(prog='run.py %s' % __package__)
  parser.add_argument('data_url', action='store', nargs='*')
  parser.add_argument('--use-cache', action='store_true')
  parser.add_argument('--master-filter', action='store')
  parser.add_argument('--builder-filter', action='store')
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
