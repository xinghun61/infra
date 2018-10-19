# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import collections
import os
import sys
import urlparse

from infra.libs import git2
from infra.libs.service_utils import outer_loop
from infra.services.gsubmodd import gsubmodd
from infra_libs import logs


# TODO: quit loading up this poor tuple with every new config option
# that comes along.
Options = collections.namedtuple('Options',
    'repo,target,loop_opts,dry_run,interval,limit,extras,epoch')


def parse_args(args):  # pragma: no cover
  def check_url(s):
    parsed = urlparse.urlparse(s)
    if parsed.scheme not in ('https', 'git', 'file'):
      raise argparse.ArgumentTypeError(
          'Repo URL must use https, git, or file protocol.')
    if not parsed.path.strip('/'):
      raise argparse.ArgumentTypeError('URL is missing a path?');
    return git2.Repo(s)

  parser = argparse.ArgumentParser('./run.py %s ' % __package__)
  parser.add_argument('--dry_run', action='store_true',
                      help='Do not actually push anything.')
  parser.add_argument('repo', nargs=1, type=check_url,
                      help='The URL of the repo to act on.')
  parser.add_argument('--target_repo',
                      help='URL of mirror repo to be built/maintained.')
  parser.add_argument('--extra_submodule', action='append', default=[],
                      help='path=URL for supplemental submodule definitions.')
  parser.add_argument('--limit', type=int,
                      help='Maximum number of commits to process per interval')
  parser.add_argument('--repo_dir', metavar='DIR', default='local_clones',
                      help=('The directory to use for git clones '
                            '(default: %(default)s)'))
  parser.add_argument('--epoch', metavar='SHA1',
                      help='Earliest commit to fortify with submodules')
  parser.add_argument(
      '--interval', type=float, default=5.0, metavar='SECONDS',
      help='How long (in seconds) to sleep between iterations of the '
      'gsubmodd processing step, during a single invocation of the service.')
  logs.add_argparse_options(parser)
  outer_loop.add_argparse_options(parser)

  opts = parser.parse_args(args)
  repo = opts.repo[0]
  repo.repos_dir = os.path.abspath(opts.repo_dir)

  logs.process_argparse_options(opts)
  loop_opts = outer_loop.process_argparse_options(opts)

  return Options(repo, opts.target_repo, loop_opts, opts.dry_run,
                 opts.interval, opts.limit, opts.extra_submodule, opts.epoch)


def main(args):  # pragma: no cover
  opts = parse_args(args)
  opts.repo.reify()

  loop_results = outer_loop.loop(
      task=lambda: gsubmodd.reify_submodules(opts.repo, opts.target,
          opts.dry_run, opts.limit, opts.extras, opts.epoch),
      sleep_timeout=lambda: opts.interval,
      **opts.loop_opts)

  return 0 if loop_results.success else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
