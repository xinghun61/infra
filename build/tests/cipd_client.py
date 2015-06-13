# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test cipd_client.cipd package by running 'cipd help'."""

import subprocess
import sys
import os


# .exe on Windows.
EXE_SUFFIX = '.exe' if sys.platform == 'win32' else ''


def main():
  cipd = os.path.join(os.getcwd(), 'cipd' + EXE_SUFFIX)
  return subprocess.call([cipd, 'help'], executable=cipd)


if __name__ == '__main__':
  sys.exit(main())
