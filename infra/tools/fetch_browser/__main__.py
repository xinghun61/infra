# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Fetch a copy of a browser to some directory

Example invocation:
./run.py infra.tools.fetch_browser [chrome|firefox]
"""
# This file is untested, keep as little code as possible in there.

import argparse
import json
import logging
import os
import sys

from infra.tools.fetch_browser import fetch_browser
import infra_libs.logs


# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def main(argv):
  parser = argparse.ArgumentParser(
    prog="fetch_browser",
    description=sys.modules['__main__'].__doc__,
    formatter_class=argparse.RawTextHelpFormatter)

  fetch_browser.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser)
  args = parser.parse_args(argv)
  infra_libs.logs.process_argparse_options(args)

  # Do more processing here
  LOGGER.info('Fetch_browser starting.')

  browser = args.browser[0]
  cache_dir = os.path.abspath(os.path.expanduser(args.cache_dir))
  result = fetch_browser.run(browser, cache_dir, args.version, args.platform)
  if args.output_json:
    with open(args.output_json, 'w') as f:
      json.dump(result, f)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
