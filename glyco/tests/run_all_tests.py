# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs all tests scripts found under tests/.

Intended to be called by a continuous integration builder.
"""

import glob
import os
import subprocess
import sys


THIS_DIR = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
  test_failed = False
  for test_file in glob.glob(os.path.join(THIS_DIR, '*_test.py')):
    try:
      subprocess.check_call([sys.executable, test_file])
    except subprocess.CalledProcessError:
      print >> sys.stderr, 'Test script failed: %s\n' % test_file
      test_failed = True

  if test_failed:
    sys.exit(1)
  sys.exit(0)
