# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""List and cat logs in the infra cloud.

Commands:
  list                  Lists all log types
  list <log>            Lists all machines that write this log
  cat <log>             Prints a log from all machines
  cat <log> <machine>   Prints a log from one machine
  master <master name>  Prints a log from a master.  This is an alias for
                        cit log cat master_twistd_log master.<master name>
"""
import logging
import sys

from infra.tools.log import log
from infra_libs import app


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


class Log(app.BaseApplication):
  DESCRIPTION = sys.modules['__main__'].__doc__
  PROG_NAME = 'log'
  USES_STANDARD_LOGGING = False
  USES_TS_MON = False

  def add_argparse_options(self, parser):
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

    def error_handler(message):  # pragma: no cover
      parser.print_help()
      sys.stderr.write('\nerror: %s\n' % message)
      sys.exit(2)
    parser.error = error_handler

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
    elif args.command == 'help':  # pragma: no cover
      self.parser.print_help()
    elif args.command == 'master':  # pragma: no cover
      if not args.target:
        self.parser.error('Missing master name')
      master = args.target[0]
      if not master.startswith('master.'):
        master = 'master.' + master
      return cl.cat(['master_twistd_log', master])
    else:  # pragma: no cover
      self.parser.error('Unkown command: %s' % args.command)


if __name__ == '__main__':
  Log().run()
