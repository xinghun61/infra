# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test luci-auth cipd package by running 'luci-auth help'."""

import subprocess
import sys
import os


# .exe on Windows.
EXE_SUFFIX = '.exe' if sys.platform == 'win32' else ''


def main():
  luci_auth = os.path.join(os.getcwd(), 'luci-auth' + EXE_SUFFIX)
  return subprocess.call([luci_auth, 'help'], executable=luci_auth)


if __name__ == '__main__':
  sys.exit(main())
