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

import infra_libs.logs

from . import dockerbuild


def main(argv):
  parser = argparse.ArgumentParser(
    prog="dockerbuild",
    description=sys.modules['__main__'].__doc__,
    formatter_class=argparse.RawTextHelpFormatter)

  dockerbuild.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser, default_level=logging.INFO)
  args = parser.parse_args(argv)
  infra_libs.logs.process_argparse_options(args)
  dockerbuild.run(args)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
