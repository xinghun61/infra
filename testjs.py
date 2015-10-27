#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Top-level Javascript test runners for Infra."""


import os
import subprocess
import sys


THIS_DIR = os.path.dirname(os.path.abspath(__file__))

KARMA_PROJECTS = [
  'appengine/chromium_cq_status',
  'appengine/chromium_rietveld/new_static',
]


def main():
  run_py = os.path.join(THIS_DIR, 'run.py')
  cmd = [sys.executable, run_py, 'infra.tools.testjs']
  cmd.extend([os.path.join(THIS_DIR, project) for project in KARMA_PROJECTS])
  return subprocess.call(cmd)


if __name__ == '__main__':
  sys.exit(main())
