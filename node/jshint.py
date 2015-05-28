#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Run node-jshint."""

import argparse
import os
import subprocess
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
NODE = os.path.join(THIS_DIR, 'node.py')
JSHINT = os.path.join(THIS_DIR, 'node_modules', '.bin', 'jshint')

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('cmd', nargs='*')

  args = parser.parse_args()
  cmd = [sys.executable, NODE, '--', JSHINT]
  return subprocess.call(cmd + args.cmd)


if __name__ == '__main__':
  sys.exit(main())
