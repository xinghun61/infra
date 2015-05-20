#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import contextlib
import cStringIO
import datetime
import gzip
import json
import logging
import multiprocessing
import os
import sys
import traceback

import requests
import requests_cache

from infra.libs import logs
from infra.libs.service_utils import outer_loop

from infra.services.builder_alerts import analysis
from infra.services.builder_alerts import buildbot
from infra.services.builder_alerts import gatekeeper_extras
from infra.services.builder_alerts import alert_builder


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
    try:
      master_json = buildbot.fetch_master_json(master_url)
      if not master_json:
        return (None, None, None, master_url)

      master_alerts, stale_master_alert = alert_builder.alerts_for_master(
          self._cache, master_url, master_json, self._old_alerts,
          self._builder_filter, self._jobs)

      # FIXME: The builder info doesn't really belong here. The builder
      # revisions tool uses this and we happen to have the builder json cached
      # at this point so it's cheap to compute, but it should be moved
      # to a different feed.
      data, stale_builder_alerts = (
          buildbot.latest_builder_info_and_alerts_for_master(
              self._cache, master_url, master_json))
      if stale_master_alert:
        stale_builder_alerts.append(stale_master_alert)
      return (master_alerts, data, stale_builder_alerts, master_url)
    except:
      # Put all exception text into an exception and raise that so it doesn't
      # get eaten by the multiprocessing code.
      raise Exception(''.join(traceback.format_exception(*sys.exc_info())))


def query_findit(findit_api_url, alerts):
  """Get analysis results from Findit for failures in the given alerts.

  Args:
    findit_api_url (str): The URL to findit's api for build failure analysis.
    alerts (list): A non-empty list of failure alerts.

  Returns:
    A list of analysis results in the following form (could be an empty list):
    [
      {
        "master_url": "https://build.chromium.org/p/chromium.chromiumos",
        "builder_name": "Linux ChromiumOS GN",
        "build_number": 6146,
        "step_name": "compile",
        "first_known_failed_build_number": 6146,
        "is_sub_test": false,
        "suspected_cls": [
          {
            "repo_name": "chromium",
            "revision": "ed1e90f4f980709cef6a8a9c7e0f64cfe5578cdd",
            "commit_position": 311460,
          }
        ]
      },
      {
        "master_url": "https://build.chromium.org/p/chromium.linux",
        "builder_name": "Linux Tests",
        "build_number": 1234,
        "step_name": "browser_tests",
        "first_known_failed_build_number": 1232,
        "is_sub_test": true,
        "test_name": "TestSuite.TestName",
        "suspected_cls": [
          {
            "repo_name": "chromium",
            "revision": "another_git_hash",
            "commit_position": 23456,
          }
        ]
      }
    ]
  """
  # Alerts are per-step or per-reason, but analysis of build failures by Findit
  # is per-build. Thus use a dict to de-duplicate.
  builds = {}
  for alert in alerts:
    master_url = alert['master_url']
    builder_name = alert['builder_name']
    build_number = alert['last_failing_build']
    key = '%s-%s-%d' % (master_url, builder_name, build_number)
    builds[key] = {
        'master_url': master_url,
        'builder_name': builder_name,
        'build_number': build_number
    }

  try:
    headers = {'Content-type': 'application/json'}
    data_json = {'builds': builds.values()}

    logging.debug('Request to findit:\n%s', json.dumps(data_json, indent=2))

    start_time = datetime.datetime.utcnow()
    response = requests.post(findit_api_url, data=json.dumps(data_json),
                             headers=headers, timeout=60)
    logging.info('Query Findit took: %s seconds.',
                 (datetime.datetime.utcnow() - start_time).total_seconds())

    if response.status_code != 200:
      logging.error('Findit response status code:%d, content:%s',
                    response.status_code, response.text)
      return []

    response_json = response.json()

    logging.debug(
        'Response from findit:\n%s', json.dumps(response_json, indent=2))

    return response_json.get('results', [])
  except (requests.Timeout, ValueError, Exception):
    # TODO(crbug.com/468161): remove the "Exception" from the list above.
    # For now, it is to make sure any break on Findit side won't impact the
    # rest of builder_alerts.
    logging.exception('Failed to incorporate result from Findit.')
    return []


def inner_loop(args):
  if not args.data_url:
    logging.warn('No /data url passed, will write to builder_alerts.json')

  if args.use_cache:
    requests_cache.install_cache('failure_stats')
  else:
    requests_cache.install_cache(backend='memory')

  # FIXME: gatekeeper_config should find gatekeeper.json for us.
  gatekeeper_path = os.path.abspath(args.gatekeeper)
  logging.debug('Processsing gatekeeper json: %s', gatekeeper_path)
  gatekeeper = gatekeeper_ng_config.load_gatekeeper_config(gatekeeper_path)

  gatekeeper_trees_path = os.path.abspath(args.gatekeeper_trees)
  logging.debug('Processing gatekeeper trees json: %s', gatekeeper_trees_path)
  gatekeeper_trees = gatekeeper_ng_config.load_gatekeeper_tree_config(
      gatekeeper_trees_path)

  master_urls = gatekeeper_extras.fetch_master_urls(gatekeeper, args)
  start_time = datetime.datetime.utcnow()

  cache = buildbot.DiskCache(CACHE_PATH)

  old_alerts = {}
  if args.data_url:
    try:
      old_alerts_raw = requests.get(args.data_url[0]).json()
    except ValueError:
      logging.debug('No old alerts found.')
    else:
      # internal-alerts will have a redirect instead of alerts if you're
      # signed in.
      if 'alerts' in old_alerts_raw:
        for alert in old_alerts_raw['alerts']:
          master = alert['master_url']
          builder = alert['builder_name']
          step = alert['step_name']
          reason = alert['reason']
          alert_key = alert_builder.generate_alert_key(
              master, builder, step, reason)

          if alert_key in old_alerts:
            logging.critical(
                'Incorrectly overwriting an alert reason from the'
                ' old alert data. master: %s, builder: %s, step: %s, reason:'
                ' %s' % (master, builder, step, reason))

          old_alerts[alert_key] = alert

  latest_builder_info = {}
  stale_builder_alerts = []
  missing_masters = []
  alerts = []
  suspected_cls = []

  pool = multiprocessing.Pool(processes=args.processes)
  master_datas = pool.map(SubProcess(cache, old_alerts, args.builder_filter,
                                     args.jobs), master_urls)
  pool.close()
  pool.join()

  for data in master_datas:
    # TODO(ojan): We should put an alert in the JSON for this master so
    # we can show that the master is down in the sheriff-o-matic UI.
    if not data[0]:
      missing_masters.extend([data[3]])
      continue
    alerts.extend(data[0])
    latest_builder_info.update(data[1])
    stale_builder_alerts.extend(data[2])

  logging.info('Fetch took: %s seconds.',
               (datetime.datetime.utcnow() - start_time).total_seconds())

  alerts = gatekeeper_extras.apply_gatekeeper_rules(alerts, gatekeeper,
                                                    gatekeeper_trees)
  stale_builder_alerts = gatekeeper_extras.apply_gatekeeper_rules(
      stale_builder_alerts, gatekeeper, gatekeeper_trees)

  alerts = analysis.assign_keys(alerts)
  reason_groups = analysis.group_by_reason(alerts)
  range_groups = analysis.merge_by_range(reason_groups)

  if args.findit_api_url and alerts:
    suspected_cls = query_findit(args.findit_api_url, alerts)

  data = {'content': json.dumps({
      'alerts': alerts,
      'suspected_cls': suspected_cls,
      'reason_groups': reason_groups,
      'range_groups': range_groups,
      'latest_builder_info': latest_builder_info,
      'stale_builder_alerts': stale_builder_alerts,
      'missing_masters': missing_masters,
  })}

  if not args.data_url:
    with open('builder_alerts.json', 'w') as f:
      f.write(json.dumps(data, indent=1))

  ret = True

  json_data = json.dumps(data)
  logging.info('Alerts json is %s bytes uncompressed.', len(json_data))
  s = cStringIO.StringIO()
  with contextlib.closing(gzip.GzipFile(fileobj=s, mode='w')) as g:
    g.write(json_data)
  gzipped_data = s.getvalue()

  for url in args.data_url:
    logging.info('POST %s alerts (%s bytes compressed) to %s',
                 len(alerts), len(gzipped_data), url)
    resp = requests.post(url, data=gzipped_data,
                         headers={'content-encoding': 'gzip'})
    try:
      resp.raise_for_status()
    except requests.HTTPError as e:
      logging.error('POST to %s failed! %d %s, %s, %s',
                    url, resp.status_code, resp.reason, resp.content, e)
      ret = False

  return ret


def main(args):
  parser = argparse.ArgumentParser(prog='run.py %s' % __package__)
  parser.add_argument('data_url', action='store', nargs='*')
  parser.add_argument('--use-cache', action='store_true')
  parser.add_argument('--master-filter', action='store')
  parser.add_argument('--builder-filter', action='store')
  parser.add_argument('--processes', default=PARALLEL_TASKS, action='store',
                      type=int)
  parser.add_argument('--jobs', default=CONCURRENT_TASKS, action='store',
                      type=int)
  logs.add_argparse_options(parser)
  outer_loop.add_argparse_options(parser)

  gatekeeper_json = os.path.join(build_scripts_dir, 'slave', 'gatekeeper.json')
  parser.add_argument('--gatekeeper', action='store', default=gatekeeper_json)
  gatekeeper_trees_json = os.path.join(build_scripts_dir, 'slave',
                                       'gatekeeper_trees.json')
  parser.add_argument('--gatekeeper-trees', action='store',
                      default=gatekeeper_trees_json)

  parser.add_argument('--findit-api-url',
                      help='Query findit results from this url.')

  args = parser.parse_args(args)
  logs.process_argparse_options(args)
  loop_args = outer_loop.process_argparse_options(args)

  # Suppress all logging from connectionpool; it is too verbose at info level.
  if args.log_level != logging.DEBUG:
    class _ConnectionpoolFilter(object):

      @staticmethod
      def filter(record):
        if record.levelno == logging.INFO:
          return False
        return True
    logging.getLogger('requests.packages.urllib3.connectionpool').addFilter(
        _ConnectionpoolFilter())

  def outer_loop_iteration():
    return inner_loop(args)

  loop_results = outer_loop.loop(
      task=outer_loop_iteration,
      sleep_timeout=lambda: 5,
      **loop_args)

  return 0 if loop_results.success else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
