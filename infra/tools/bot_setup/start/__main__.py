# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Sets up and starts a Swarming slave."""

import argparse
import re
import sys
import threading


# pylint: disable=F0401
from infra.tools.bot_setup.start import swarming
from infra.services.git_cookie_daemon import git_cookie_daemon


if sys.platform.startswith('win'):
  # TODO(hinoka): Maybe we should also check E:\b?
  DEFAULT_ROOT = 'C:\\b'
else:
  DEFAULT_ROOT = '/b'


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument('-s', '--slave_name')
  parser.add_argument('-b', '--root_dir', default=DEFAULT_ROOT)
  parser.add_argument('-g', '--git_daemon', action='store_true',
                      help='Run the git daemon.')
  return parser.parse_args()


def main():
  args = parse_args()
  root_dir = args.root_dir
  slave_name = args.slave_name or ''

  t = None
  if args.git_daemon:
    print 'Starting Git Cookie Daemon...'
    t = threading.Thread(target=git_cookie_daemon.ensure_git_cookie_daemon)
    t.daemon = True
    t.start()

  swarming.start(slave_name, root_dir)


if __name__ == '__main__':
  sys.exit(main())
