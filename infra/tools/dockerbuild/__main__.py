# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""dockerbuild: use Docker images to cross-compile and build Python wheels.

DockerBuild contains scripts to build cross-compiling Docker images reproducibly
and use them to build Python wheels and perform arbitrary cross-compiling
builds.

Read more about it at:
https://chromium.googlesource.com/infra/infra/+/master/infra/tools/dockerbuild
"""
# This file is untested, keep as little code as possible in there.

import argparse
import logging
import os
import sys

from . import dockerbuild


def add_logging_options(parser):
  """Adds logging related options to an argparse.ArgumentParser.

  This is cribbed from infra_lib because depending on infra_lib.logs pulls in
  an entire galaxy of ts_mon dependencies that we don't use. Doing it this
  way allows dockerbuild to be used with bog-standard Python and no external
  dependencies.
  """

  parser = parser.add_argument_group('Logging Options')
  g = parser.add_mutually_exclusive_group()
  g.set_defaults(log_level=logging.INFO)
  g.add_argument('--logs-quiet', '--quiet',
                 action='store_const', const=logging.ERROR,
                 dest='log_level', help='Make the output quieter (ERROR).')
  g.add_argument('--logs-warning', '--warning',
                 action='store_const', const=logging.WARNING,
                 dest='log_level',
                 help='Set the output to an average verbosity (WARNING).')
  g.add_argument('--logs-verbose', '--verbose',
                 action='store_const', const=logging.INFO,
                 dest='log_level', help='Make the output louder (INFO).')
  g.add_argument('--logs-debug', '--debug',
                 action='store_const', const=logging.DEBUG,
                 dest='log_level', help='Make the output really loud (DEBUG).')


def main(argv):
  parser = argparse.ArgumentParser(
    prog="dockerbuild",
    description=sys.modules['__main__'].__doc__,
    formatter_class=argparse.RawTextHelpFormatter)

  dockerbuild.add_argparse_options(parser)
  add_logging_options(parser)
  args = parser.parse_args(argv)

  logging.basicConfig(level=args.log_level)

  dockerbuild.run(args)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
