# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Sets up and starts a Chrome slave."""

import argparse
import re
import sys


# pylint: disable=F0401
from infra.tools.bot_setup.start import chrome
from infra.tools.bot_setup.start import swarming


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument('-s', '--slave_name')
  parser.add_argument('-b', '--root_dir', default='/b')
  parser.add_argument('-d', '--depot_tools')
  parser.add_argument('-p', '--password_file')
  return parser.parse_args()


def main():
  args = parse_args()
  root_dir = args.root_dir
  depot_tools = args.depot_tools
  password_file = args.password_file
  slave_name = args.slave_name

  if re.match(r'^swarm.*', slave_name):
    swarming.start(slave_name, root_dir)
  else:
    chrome.start(root_dir, depot_tools, password_file)



if __name__ == '__main__':
  sys.exit(main())
