# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import collections
import json
import os
import sys
import urlparse

from infra.libs import git2
from infra.libs import ts_mon
from infra.libs.service_utils import outer_loop
from infra.services.gsubtreed import gsubtreed
from infra_libs import logs


# Return value of parse_args.
Options = collections.namedtuple('Options', 'repo loop_opts json_output')


def parse_args(args):  # pragma: no cover
  def check_url(s):
    parsed = urlparse.urlparse(s)
    if parsed.scheme not in ('https', 'git', 'file'):
      raise argparse.ArgumentTypeError(
          'Repo URL must use https, git or file protocol.')
    if not parsed.path.strip('/'):
      raise argparse.ArgumentTypeError('URL is missing a path?')
    return git2.Repo(s)

  parser = argparse.ArgumentParser('./run.py %s' % __package__)
  parser.add_argument('--dry_run', action='store_true',
                      help='Do not actually push anything.')
  parser.add_argument('--repo_dir', metavar='DIR', default='gsubtreed_repos',
                      help=('The directory to use for git clones '
                            '(default: %(default)s)'))
  parser.add_argument('--json_output', metavar='PATH',
                      help='Path to write JSON with results of the run to')
  parser.add_argument('repo', nargs=1, help='The url of the repo to act on.',
                      type=check_url)
  logs.add_argparse_options(parser)
  ts_mon.add_argparse_options(parser)
  outer_loop.add_argparse_options(parser)

  opts = parser.parse_args(args)

  logs.process_argparse_options(opts)
  ts_mon.process_argparse_options(opts)
  loop_opts = outer_loop.process_argparse_options(opts)

  repo = opts.repo[0]
  repo.dry_run = opts.dry_run
  repo.repos_dir = os.path.abspath(opts.repo_dir)

  return Options(repo, loop_opts, opts.json_output)


def main(args):  # pragma: no cover
  opts = parse_args(args)
  commits_counter = ts_mon.CounterMetric('gsubtreed/commit_count')
  cref = gsubtreed.GsubtreedConfigRef(opts.repo)
  opts.repo.reify()

  summary = collections.defaultdict(int)
  def outer_loop_iteration():
    success, paths_counts = gsubtreed.inner_loop(opts.repo, cref)
    for path, count in paths_counts.iteritems():
      summary[path] += count
      commits_counter.increment_by(count, fields={'path': path})
    return success

  loop_results = outer_loop.loop(
      task=outer_loop_iteration,
      sleep_timeout=lambda: cref['interval'],
      **opts.loop_opts)

  if opts.json_output:
    with open(opts.json_output, 'w') as f:
      json.dump({
        'error_count': loop_results.error_count,
        'summary': summary,
      }, f)

  return 0 if loop_results.success else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
