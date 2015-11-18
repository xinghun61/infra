#!/usr/bin/python
# Copyright 2014 Google Inc. All Rights Reserved.
# pylint: disable=F0401

"""Restart a master via master-manager."""


import argparse
import datetime
import sys

import infra_libs.logs


from infra.tools.restart import restart


def main(argv):
  parser = argparse.ArgumentParser(
      prog='restart',
      description=sys.modules['__main__'].__doc__)
  infra_libs.logs.add_argparse_options(parser)
  restart.add_argparse_options(parser)
  args = parser.parse_args(argv)
  infra_libs.logs.process_argparse_options(args)

  if args.minutes_in_future < 0 and not args.eod:
    parser.error('minutes-in-future must be nonnegative, use 0 for "now", '
                 'or --eod')

  # 15 minutes is the default, so don't get hung up on that.
  if (args.minutes_in_future > 0 and args.minutes_in_future != 15) and args.eod:
    parser.error('minutes-in-future is mutually exclusive with --eod')

  if args.eod:
    restart_time = restart.get_restart_time_eod()
  else:
    restart_time = restart.get_restart_time_delta(args.minutes_in_future)

  return restart.run(args.masters, restart_time,
                     args.reviewer, args.bug, args.force, args.no_commit)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
