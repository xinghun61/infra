#!/usr/bin/python
# Copyright 2014 Google Inc. All Rights Reserved.
# pylint: disable=F0401

"""Restart a master via master-manager.  TBRs a random OWNER."""


import sys
import argparse


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

  return restart.run(sys.argv[1:])

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
