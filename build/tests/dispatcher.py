# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test dispatcher.cipd package by running 'dispatcher -h'."""

import subprocess
import sys
import os


# .exe on Windows.
EXE_SUFFIX = '.exe' if sys.platform == 'win32' else ''


def main():
  dispatcher = os.path.join(os.getcwd(), 'dispatcher' + EXE_SUFFIX)
  ok = subprocess.call([dispatcher, '-h'], executable=dispatcher) == 2
  return 0 if ok else 1


if __name__ == '__main__':
  sys.exit(main())
