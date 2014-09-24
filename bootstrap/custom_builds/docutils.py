# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import sys


def Build(source_path, wheelhouse_path):
  assert hasattr(sys, 'real_prefix'), 'virtualenv must be activate'
  pip_path = os.path.join(sys.prefix, 'bin', 'pip')
  subprocess.check_call([pip_path, 'wheel', '-w', wheelhouse_path,
                         '--no-deps', './docutils'],
    cwd=source_path)
