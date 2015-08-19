# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""dumpthis: scp to your machine from anywhere and pronto!

Example invocation:

    ./run.py infra.tools.dumpthis some.log

See README.md for more.
"""
# This file is untested, keep as little code as possible in there.

import argparse
import logging
import os
import sys

from infra.tools.dumpthis import dumpthis
import infra_libs.logs


def main(argv):
  parser = argparse.ArgumentParser(
    prog="dumpthis",
    description=sys.modules['__main__'].__doc__,
    formatter_class=argparse.RawTextHelpFormatter)

  dumpthis.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser)
  args = parser.parse_args(argv)
  infra_libs.logs.process_argparse_options(args)
  dumpthis.run(args.bucket, args.src)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
