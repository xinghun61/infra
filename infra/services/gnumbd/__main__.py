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
from infra.libs.service_utils import outer_loop
from infra.services.gnumbd import gnumbd
from infra_libs import infra_types
from infra_libs import logs
from infra_libs import ts_mon


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

  parser = argparse.ArgumentParser('python -m %s' % __package__)
  parser.add_argument('--dry_run', action='store_true',
                      help='Do not actually push anything.')
  parser.add_argument('--repo_dir', metavar='DIR', default='gnumbd_repos',
                      help=('The directory to use for git clones '
                            '(default: %(default)s)'))
  parser.add_argument('--json_output', metavar='PATH',
                      help='Path to write JSON with results of the run to')
  parser.add_argument('repo', nargs=1, help='The url of the repo to act on.',
                      type=check_url)
  logs.add_argparse_options(parser)
  ts_mon.add_argparse_options(parser)
  outer_loop.add_argparse_options(parser)

  parser.set_defaults(
      ts_mon_target_type='task',
      ts_mon_task_service_name='gnumbd',
  )

  opts = parser.parse_args(args)

  repo = opts.repo[0]
  repo.dry_run = opts.dry_run
  repo.repos_dir = os.path.abspath(opts.repo_dir)

  if not opts.ts_mon_task_job_name:
    opts.ts_mon_task_job_name = urlparse.urlparse(repo.url).path

  logs.process_argparse_options(opts)
  ts_mon.process_argparse_options(opts)
  loop_opts = outer_loop.process_argparse_options(opts)

  return Options(repo, loop_opts, opts.json_output)


def main(args):  # pragma: no cover
  opts = parse_args(args)
  commits_counter = ts_mon.CounterMetric('gnumbd/commit_count')
  cref = gnumbd.GnumbdConfigRef(opts.repo)
  opts.repo.reify()

  all_commits = []
  def outer_loop_iteration():
    success, commits = gnumbd.inner_loop(opts.repo, cref)
    all_commits.extend(commits)
    commits_counter.increment_by(len(commits))
    return success

  # TODO(iannucci): sleep_timeout should be an exponential backon/off.
  #   Whenever we push, we should decrease the interval at 'backon_rate'
  #   until we hit 'min_interval'.
  #   Whenever we fail/NOP, we should back off at 'backoff_rate' until we
  #   hit 'max_interval'.
  #
  #   When all is going well, this should be looping at < 1 sec. If things
  #   start going sideways, we should automatically back off.
  loop_results = outer_loop.loop(
      task=outer_loop_iteration,
      sleep_timeout=lambda: cref['interval'],
      **opts.loop_opts)

  if opts.json_output:
    with open(opts.json_output, 'w') as f:
      json.dump({
        'error_count': loop_results.error_count,
        'synthesized_commits': [
          {
            'commit': c.hsh,
            'footers': infra_types.thaw(c.data.footers),
          } for c in all_commits
        ],
      }, f)

  return 0 if loop_results.success else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
