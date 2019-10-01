#!/usr/bin/env python
# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(vadimsh, crbug.com/835919): Remove this after Oct 10 2019.

import argparse
import logging
import os
import shutil
import sys


BOOTSTRAP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BOOTSTRAP_DIR)


def main():
  parser = argparse.ArgumentParser(prog='python -m %s' % __package__)
  parser.add_argument('-v', '--verbose', action='store_true')
  parser.add_argument(
      '-d', '--dest', default=os.path.dirname(BASE_DIR), help='Output')
  options = parser.parse_args()

  if options.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  base = os.path.abspath(options.dest)

  rmtree(os.path.join(base, 'google_appengine'))
  rmtree(os.path.join(base, 'go_appengine'))
  return 0


def rmtree(path):
  if not os.path.exists(path):
    return
  logging.info('Removing %s', path)
  shutil.rmtree(path, ignore_errors=True)


if __name__ == '__main__':
  sys.exit(main())
