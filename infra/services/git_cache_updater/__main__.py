# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Updates the Git cache zips for a project.

Example invocation:
./run.py infra.tools.git_cache_updater --project <googlesource.com url>
"""
# This file is untested, keep as little code as possible in there.

import argparse
import logging
import sys

from infra.services.git_cache_updater import git_cache_updater
import infra_libs.logs


LOGGER = logging.getLogger(__name__)


def main(argv):
  parser = argparse.ArgumentParser(
    prog="git_cache_updater",
    description=sys.modules['__main__'].__doc__,
    formatter_class=argparse.RawTextHelpFormatter)

  git_cache_updater.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser)
  args = parser.parse_args(argv)
  infra_libs.logs.process_argparse_options(args)

  # Do more processing here
  LOGGER.info('Git_cache_updater starting.')

  git_cache_updater.run(args.project, args.work_dir)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
