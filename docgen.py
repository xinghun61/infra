#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Convenience script to generate documentation with Sphinx."""

assert __name__ == '__main__'

import os
import subprocess
import sys

INFRA_ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
  run_py = os.path.abspath(os.path.join(INFRA_ROOT, 'run.py'))
  args = [run_py, 'infra.tools.docgen'] + sys.argv[1:]
  return subprocess.call(args, cwd=INFRA_ROOT)


if __name__ == '__main__':
  sys.exit(main())
