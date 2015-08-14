# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Fetch_browser."""

import logging
import os
import random
import sys
import time

from infra.tools.fetch_browser import chrome
from infra_libs.utils import rmtree


# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


BROWSERS = {
  'chrome': {
    'target': chrome.fetch_chrome,
    'default_version': 'stable'
  },
}


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument(
      'browser', type=str, nargs=1, help='The browser to download, supported '
      'browsers include: %s' % str(BROWSERS.keys()))
  parser.add_argument('--cache-dir', '-c', default='~/.cached_browsers')
  parser.add_argument('--version', '-v')
  parser.add_argument('--output-json', '-o')
  parser.add_argument('--platform', '-p', default=sys.platform)


def garbage_collect(cache_dir):
  """Delete any directories that's been around for longer than ~30 days."""
  jitter = random.randrange(60 * 60 * 24)
  month_ago = time.time() - (60 * 60 * 24 * 30) + jitter
  for filename in os.listdir(cache_dir):
    full_filename = os.path.join(cache_dir, filename)
    if (os.path.isdir(full_filename) and
        os.path.getmtime(full_filename) < month_ago):
        LOGGER.info('Deleting %s for 30 day eviction.' % full_filename)
        rmtree(full_filename)


def run(browser, cache_dir, version=None):  # pragma: no cover
  if browser not in BROWSERS:
    LOGGER.exception('Unsupported browser %s' % browser)

  if not os.path.isdir(cache_dir):
    LOGGER.info('%s not found, creating.' % cache_dir)
    os.makedirs(cache_dir)
  else:
    garbage_collect(cache_dir)

  browser_info = BROWSERS[browser]
  fetcher = browser_info['target']
  version = version or browser_info['default_version']
  LOGGER.info('Fetching %s at version %s' % (browser, version))
  installed_path, installed_version = fetcher(cache_dir, version)
  print 'Successfully fetched %s into %s at version %s' % (
      browser, installed_path, installed_version)
  return installed_path, installed_version
