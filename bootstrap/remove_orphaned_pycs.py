#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys


def main():
  logging.basicConfig(level=logging.DEBUG)

  # This could take an argument, except gclient DEPS has no good way to pass
  # us an argument, and gclient getcwd() is ../ from our .gclient file. :(
  bootstrap_dir = os.path.dirname(os.path.abspath(__file__))
  infra_dir = os.path.dirname(bootstrap_dir)
  logging.debug("Cleaning orphaned *.pyc files from: %s" % infra_dir)

  for (dirpath, dirnames, filenames) in os.walk(infra_dir):
    for filename in filenames:
      path = os.path.join(infra_dir, dirpath, filename)
      if filename.endswith(".pyc") and filename[:-1] not in filenames:
        logging.info("Deleting orphan *.pyc file: %s" % path)
        os.remove(path)


if __name__ == '__main__':
  sys.exit(main())
