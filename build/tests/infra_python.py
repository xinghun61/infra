# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test infra_python.cipd package by running all python tests from there."""

import subprocess
import sys


def main():
  return subprocess.call(
      ['python', 'test.py', 'test', '--no-coverage'], executable=sys.executable)


if __name__ == '__main__':
  sys.exit(main())
