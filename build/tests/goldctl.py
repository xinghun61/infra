# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test packaged goldctl can start by running 'goldctl help'."""

import subprocess
import sys
import os


EXE_SUFFIX = '.exe' if sys.platform == 'win32' else ''


def main():
  goldctl = os.path.join(os.getcwd(), 'goldctl' + EXE_SUFFIX)
  return subprocess.call([goldctl, 'help'], executable=goldctl)


if __name__ == '__main__':
  sys.exit(main())
