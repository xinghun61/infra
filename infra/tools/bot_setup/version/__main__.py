# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Returns the canonical version of bot setup scripts for hostname and image."""

import argparse
import sys


DISABLED_BUILDERS = [
    'test_disabled_slave'
]


class BuilderDisabled(Exception):
  """This is raised when a builder should be disabled.

  By raising an exeception, the startup sequence becomes interrupted.
  """
  pass


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument('--slave_name')
  parser.add_argument('--image_name')

  return parser.parse_args()


def main():
  args = parse_args()
  if args.slave_name and args.slave_name in DISABLED_BUILDERS:
    raise BuilderDisabled()
  print 'origin/master'

if __name__ == '__main__':
  sys.exit(main())
