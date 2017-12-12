# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This empty vpython spec prevents the test_handoff.py script from ever
# having a vpython spec, even if this repo eventually adds one.
# [VPYTHON:BEGIN]
# [VPYTHON:END]

try:
  import six
  raise Exception('Script A imported \'six\', but has an empty venv!')
except ImportError:
  pass

import os
import subprocess
import sys

print "I'm in script A"
sys.stdout.flush()

# this makes the `main_test.go` behave like vpython (instead of like a go test
# binary)
os.environ['_VPYTHON_MAIN_TEST_PASSTHROUGH'] = '1'
MY_DIR = os.path.dirname(os.path.abspath(__file__))
subprocess.check_call([
  sys.executable, os.path.join(MY_DIR, 'test_handoff.py.triggered')])
