# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Runs javascript tests.

Example invocation:
./run.py infra.tools.testjs <root path>
"""
# This file is untested, keep as little code as possible in there.

import argparse
import logging
import os
import sys

from infra.tools.testjs import testjs
from infra.tools.fetch_browser import fetch_browser
import infra_libs.logs


# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def main(argv):
  parser = argparse.ArgumentParser(
    prog="testjs",
    description=sys.modules['__main__'].__doc__,
    formatter_class=argparse.RawTextHelpFormatter)

  testjs.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser)
  args = parser.parse_args(argv)
  infra_libs.logs.process_argparse_options(args)

  # Do more processing here
  LOGGER.info('Testjs starting.')

  LOGGER.info('Fetching Chrome...')
  cache_dir = os.path.expanduser('~/.cached_browsers')
  chrome, _ = fetch_browser.run(
      'chrome', cache_dir, sys.platform, '46.0.2490.86')

  if sys.platform == 'linux2':
    with testjs.get_display() as display:
      for target in args.target:
        LOGGER.info('Running karma for %s', target)
        testjs.test_karma(target, chrome, display)
  else:
    for target in args.target:
      LOGGER.info('Running karma for %s', target)
      testjs.test_karma(target, chrome, None)



if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
