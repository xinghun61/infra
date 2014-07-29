# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import errno
import logging
import os
import sys
import time
import urlparse

from infra.libs import git2
from infra.libs import logs

from infra.services.gnumbd import gnumbd


LOGGER = logging.getLogger(__name__)

DEFAULT_REPO_DIR = 'gnumbd_repos'


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
  parser.add_argument('--repo_dir', metavar='DIR', default=DEFAULT_REPO_DIR,
                      help=('The directory to use for git clones '
                            '(default: %(default)s)'))
  parser.add_argument('repo', nargs=1, help='The url of the repo to act on.',
                      type=check_url)
  logs.add_argparse_options(parser)
  opts = parser.parse_args(args)
  logs.process_argparse_options(opts)

  repo = opts.repo[0]
  repo.dry_run = opts.dry_run
  repo.repos_dir = os.path.abspath(opts.repo_dir)
  try:
    LOGGER.info('making repo dir: %s', repo.repos_dir)
    os.makedirs(repo.repos_dir)
  except OSError as e:
    if e.errno != errno.EEXIST:
      raise

  return repo


def main(args):  # pragma: no cover
  repo = parse_args(args)
  cref = gnumbd.GnumbdConfigRef(repo)
  repo.reify()

  loop_count = 0
  try:
    while True:
      start = time.time()
      LOGGER.info('Begin loop %d', loop_count)

      try:
        gnumbd.inner_loop(repo, cref)
      except KeyboardInterrupt:
        raise
      except Exception:
        LOGGER.exception('Uncaught exception in inner_loop')

      LOGGER.info('End loop %d (%f sec)', loop_count, time.time() - start)

      # TODO(iannucci): This timeout should be an exponential backon/off.
      #   Whenever we push, we should decrease the interval at 'backon_rate'
      #   until we hit 'min_interval'.
      #   Whenever we fail/NOP, we should back off at 'backoff_rate' until we
      #   hit 'max_interval'.
      #
      #   When all is going well, this should be looping at < 1 sec. If things
      #   start going sideways, we should automatically back off.
      time.sleep(cref['interval'])
      loop_count += 1
  except KeyboardInterrupt:
    LOGGER.warn('Stopping due to KeyboardInterrupt')

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
