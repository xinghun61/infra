# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test cloudtail.cipd package by running 'cloudtail help'."""

import subprocess
import sys
import os


# .exe on Windows.
EXE_SUFFIX = '.exe' if sys.platform == 'win32' else ''


def main():
  cloudtail = os.path.join(os.getcwd(), 'cloudtail' + EXE_SUFFIX)
  return subprocess.call([cloudtail, 'help'], executable=cloudtail)


if __name__ == '__main__':
  sys.exit(main())
