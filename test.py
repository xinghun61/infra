#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Convenience script for (cd [infra] && ENV/bin/expect_tests "$@")"""

assert __name__ == '__main__'

import os
import sys
import subprocess

path = os.path.join('ENV', 'bin', 'expect_tests')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.check_call(os.path.join('bootstrap', 'remove_orphaned_pycs.py'))
os.execv(path, [path] + sys.argv[1:])
