# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""List and cat logs in the infra cloud

Example invocation:
cit log list
cit log list bootstrap
cit log cat bootstrap
cit log cat bootstrap slave123-c4
"""
import argparse
import logging
import sys

from infra.tools.log import log
import infra_libs


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


class Log(infra_libs.BaseApplication):
  DESCRIPTION = sys.modules['__main__'].__doc__
  PROG_NAME = 'log'

  def add_argparse_options(self, parser):
    # This is actually covered, but python coverage is confused.
    super(Log, self).add_argparse_options(parser)
    parser.add_argument('--project', '-p', default=log.PROJECT_ID)
    parser.add_argument('--service', '-s', default=log.SERVICE_NAME)
    parser.add_argument('--limit', '-l', type=int, default=20000)
    parser.add_argument(
        '--from', dest='days_from', type=int, default=2,
        help='Get logs from this many days ago.')
    parser.add_argument(
        '--until', default=0, type=int, help='Number of days to look until.')
    parser.add_argument('command', help='')
    parser.add_argument('target', nargs='*', help='', default=None)

  def main(self, args):
    if args.command == 'auth':  # pragma: no cover
      log.LogQuery._auth()
      return

    cl = log.LogQuery(
        args.project, args.service, args.limit, -args.days_from, -args.until)
    cl._actually_init()

    if args.command == 'list':  # pragma: no branch
      if len(args.target) == 1:  # pragma: no cover
        return cl.list_logs(args.target[0])
      elif len(args.target) == 0:
        return cl.list_logs(None)
      else:  # pragma: no cover
        print 'Invalid number of targets for list (expected 0 or 1)'
    elif args.command == 'cat':  # pragma: no cover
      return cl.cat(args.target)
    else:  # pragma: no cover
      print 'Unkown command: %s' % args.command


if __name__ == '__main__':
  Log().run()
