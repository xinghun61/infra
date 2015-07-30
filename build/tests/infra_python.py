# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test infra_python.cipd package by running all python tests from there."""

import json
import subprocess
import sys


def main():
  # Verify version file is deployed, print it.
  with open('CIPD_VERSION.json', 'r') as f:
    data = f.read()
  print 'CIPD_VERSION.json:'
  print data
  print
  version_info = json.loads(data)
  assert version_info['package_name'].startswith('infra/infra_python/')
  assert version_info['instance_id']

  # TODO(crbug.com/487485): expect_test + venv is broken on Windows.
  if sys.platform == 'win32':
    return 0

  return subprocess.call(
      ['python', 'test.py', 'test', '--no-coverage'], executable=sys.executable)


if __name__ == '__main__':
  sys.exit(main())
