# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Update the Git Cache that bot_update downloads from.

Example invocation:
./run.py infra.tools.cache_updater --shard-total 5 --shard-index 2
"""
# This file is untested, keep as little code as possible in there.

import argparse
import logging
import sys

from infra.services.cache_updater import cache_updater
import infra_libs.logs


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


def main(argv):
  parser = argparse.ArgumentParser(
    prog="cache_updater",
    description=sys.modules['__main__'].__doc__,
    formatter_class=argparse.RawTextHelpFormatter)

  cache_updater.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser)
  args = cache_updater.parse_args(parser, argv)
  infra_libs.logs.process_argparse_options(args)

  # Do more processing here
  LOGGER.info('Cache_updater starting.')

  cache_updater.run(args.cache_dir, args.shard_index, args.shard_total)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
