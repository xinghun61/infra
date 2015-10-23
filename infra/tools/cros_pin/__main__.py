#!/usr/bin/python
# Copyright 2014 Google Inc. All Rights Reserved.
# pylint: disable=F0401

"""CrOS pin management/update tool."""


import argparse
import datetime
import sys

import infra_libs.logs

from infra.tools.cros_pin import cros_pin


def main(argv):
  parser = argparse.ArgumentParser(
      prog='cros-pin',
      description=sys.modules['__main__'].__doc__)
  infra_libs.logs.add_argparse_options(parser)
  cros_pin.add_argparse_options(parser)

  args = parser.parse_args(argv)
  infra_libs.logs.process_argparse_options(args)

  # Execute our subcommand (configured by cros_pin.add_argparse_options).
  return args.func(args)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
