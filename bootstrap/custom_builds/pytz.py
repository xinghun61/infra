# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess


def Build(source_path, wheelhouse_path):
  subprocess.check_call(
      ['make', 'CFLAGS=-DSTD_INSPIRED', 'build'], cwd=source_path)

  path = os.path.join(source_path, 'build', 'dist')
  subprocess.check_call(
      ['python', 'setup.py', 'bdist_wheel', '--dist-dir', wheelhouse_path],
      cwd=path)
