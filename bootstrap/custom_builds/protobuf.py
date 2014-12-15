# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import sys


def Build(source_path, wheelhouse_path):
  # First, have to compile the protoc executable. Note that this
  # 1) only runs on unix-like systems, and
  # 2) requires autoconf and libtool to be installed (e.g. via apt-get).
  subprocess.check_call(['./autogen.sh'], cwd=source_path)
  subprocess.check_call(['./configure'], cwd=source_path)
  subprocess.check_call(['make'], cwd=source_path)

  # Now that we have <source_path>/src/protoc, we can build the python package.
  cwd = os.path.join(source_path, 'python')
  subprocess.check_call(
      ['python', 'setup.py', 'bdist_wheel', '--dist-dir', wheelhouse_path],
      cwd=cwd)
