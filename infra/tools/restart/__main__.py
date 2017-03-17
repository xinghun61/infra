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

  if args.eod:
    parser.error('usage of "--eod" is deprecated, all restarts should be'
                 ' attended and during a trooper oncall shift')

  if args.minutes_in_future < 0:
    parser.error('--minutes-in-future must be nonnegative, use 0 for "now"')

  restart_time = restart.get_restart_time_delta(args.minutes_in_future)

  return restart.run(args.masters, args.masters_regex, restart_time,
                     args.rolling, args.reviewer, args.bug, args.force,
                     args.no_commit, args.desired_state, args.reason)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
