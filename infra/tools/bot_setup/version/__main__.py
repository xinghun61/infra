# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Returns the canonical version of bot setup scripts for hostname and image."""

import argparse
import sys


from infra.tools.bot_setup.version import version


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument('--slave_name', '--slave-name')
  parser.add_argument('--image_name', '--image-name')

  return parser.parse_args()


def main():
  args = parse_args()
  print version.get_version(args.slave_name, args.image_name)

if __name__ == '__main__':
  sys.exit(main())
