# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test authutil.cipd package by running 'authutil help'."""

import subprocess
import sys
import os


# .exe on Windows.
EXE_SUFFIX = '.exe' if sys.platform == 'win32' else ''


def main():
  authutil = os.path.join(os.getcwd(), 'authutil' + EXE_SUFFIX)
  return subprocess.call([authutil, 'help'], executable=authutil)


if __name__ == '__main__':
  sys.exit(main())
