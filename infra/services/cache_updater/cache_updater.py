# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Cache_updater."""

import logging
import os
import requests
import subprocess
import sys
import hashlib

from infra.path_hacks.depot_tools import _depot_tools as depot_tools_path

sys.path.append(depot_tools_path)
import git_cache


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


PROJECTS = [
  'https://chromium.googlesource.com/a/',
  'https://chrome-internal.googlesource.com/a/',
  'https://chromium.googlesource.com/',
  'https://chrome-internal.googlesource.com/',
]


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument(
      '--cache-dir', help='Directory to store cached repos.',
      default=os.path.expanduser('~/cache_dir'))
  parser.add_argument(
      '--shard-total', help='Total number of shards.', type=int, default=1)
  parser.add_argument(
      '--shard-index', help='Shard index, in the range of [0:shard-total].',
      type=int, default=0)


def parse_args(parser, argv):
  args = parser.parse_args(argv)
  if args.shard_index < 0:
    parser.error('--shard-index must be positive.')
  if args.shard_total < 0:
    parser.error('--shard-total must be positive.')
  if args.shard_index > args.shard_total:
    parser.error('--shard-index must be less than --shard-total.')
  return args



class FakeFile(object):
  def write(self, *_, **__):  # pragma: no cover
    pass

  def flush(self, *_, **__):  # pragma: no cover
    pass


def update_bootstrap(repo):  # pragma: no cover
  orig_out = sys.stdout
  orig_err = sys.stderr
  sys.stderr = FakeFile()
  sys.stdout = FakeFile()
  try:
    mirror = git_cache.Mirror(repo)
    mirror.populate(verbose=False, shallow=False, bootstrap=False)
    if subprocess.check_output(['git', 'ls-remote', '--heads', '.'],
                               cwd=mirror.mirror_path).strip():
      mirror.update_bootstrap()
    else:
      print >> orig_out, 'Not a real repo, skipped'
  finally:
    sys.stderr = orig_err
    sys.stdout = orig_out


def get_project_list(project):  # pragma: no cover
  """Fetch the list of all git repositories in a project."""
  # Uses ~/.netrc by default \o/.
  r = requests.get('%s?format=TEXT' % project)
  if r.status_code == 403:
    raise Exception('Auth failed, check your netrc')
  return ['%s%s' % (project, repo) for repo in r.text.splitlines()
          if repo and repo.lower() not in ['all-projects', 'all-users']]


def shard(name, total):
  num = int(hashlib.sha1(name).hexdigest(), 16)
  return num % total


def run_project(project, shard_index, shard_total):  # pragma: no cover
  for url in get_project_list(project):
    unit_shard = shard(url, shard_total)
    if unit_shard == shard_index:
      try:
        print '===Updating %s===' % url
        update_bootstrap(url)
      except subprocess.CalledProcessError:
        print >> sys.stderr, 'Failed to update %s:'
        sys.excepthook(*sys.exc_info())
        print '===Failed==='
      else:
        print '===Done==='
        print
    else:
      print '%s is in shard %d, not %d' % (url, unit_shard, shard_index)
      print 'Skipping...'


def run(cache_dir, shard_index, shard_total):  # pragma: no cover
  git_cache.Mirror.SetCachePath(cache_dir)
  os.environ['CHROME_HEADLESS'] = '1'
  if not os.path.isdir(cache_dir):
    os.makedirs(cache_dir)
  for project in PROJECTS:
    # Run this serially.  Running it overly parallel could cause
    # memory/harddrive exhaustion.
    run_project(project, shard_index, shard_total)
