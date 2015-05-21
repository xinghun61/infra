# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import logging
import os
import requests
import sys

from collections import defaultdict
from multiprocessing.pool import ThreadPool

import infra_libs.logs
from infra.libs.git2 import Repo

HERE = os.path.abspath(os.path.dirname(__file__))
LOGGER = logging.getLogger(__name__)


def get_builders():
  local_path = os.path.abspath(os.path.join(HERE, 'workdir'))
  data_url = 'https://chrome-internal.googlesource.com/infradata/hosts'
  buildermap_path = 'buildermap.json'
  mastermap_path = 'mastermap.json'
  r = Repo(data_url)
  r.repos_dir = local_path
  r.reify()
  r.fetch()
  builder_list = json.loads(
      r.run('cat-file', 'blob', 'refs/heads/master:%s' % buildermap_path))
  master_list = json.loads(
      r.run('cat-file', 'blob', 'refs/heads/master:%s' % mastermap_path))
  master_map = {master['dirname']: master for master in master_list}
  for entry in builder_list:
    master_url = master_map.get(entry['mastername'], {}).get('buildbot_url')
    if not master_url:
      LOGGER.warn('No master url found for %s/%s',
                  entry['mastername'], entry['builder'])
      url = None
    else:
      url = '%s/builders/%s' % (master_url.rstrip('/'), entry['builder'])
    entry['url'] = url
  return builder_list


def process_entry(entry):
  name = '%s/%s' % (entry['mastername'], entry['builder'])
  try:
    url = entry['url']
    if not url:
      LOGGER.error('No url for %s', name)
      return 'unknown', url
    us_url = '%s/builds/-1/steps/update_scripts/logs/stdio' % url
    log = requests.get(us_url)
    log.raise_for_status()
  except requests.exceptions.RequestException:
    LOGGER.error('Failed to get logs from %s', url)
    return 'unknown', url
  for line in log.text.splitlines():
    if 'master.DEPS' in line:
      LOGGER.error('Found master.DEPS on %s', name)
      return 'master', url
    if 'internal.DEPS' in line:
      LOGGER.warn('Found internal.DEPS on %s', name)
      return 'internal', url
    if 'slave.DEPS' in line:
      LOGGER.info('Found slave.DEPS on %s', name)
      return 'slave', url
  else:
    return 'unknown', url


def parse_args(args):  # pragma: no cover
  parser = argparse.ArgumentParser('./run.py %s' % __package__)
  parser.add_argument('-j', '--jobs', metavar='N', type=int, default=10,
                      help='Number of parallel logs-fetching threads to run.')
  infra_libs.logs.add_argparse_options(parser)
  opts = parser.parse_args(args)
  infra_libs.logs.process_argparse_options(opts)
  return opts


def main(args):  # pragma: no cover
  opts = parse_args(args)

  res = defaultdict(list)
  builders = get_builders()
  workers = ThreadPool(processes=opts.jobs)
  results = workers.imap_unordered(process_entry, builders)
  for result in results:
    res[result[0]].append(result[1])

  print json.dumps(res, sort_keys=True, indent=2, separators=(',', ': '))


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
