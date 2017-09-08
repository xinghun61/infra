#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This bootstrap is run using the local system's Python. Its job is to set up
the Python environment to operate like the build Python, and then run a
Python subprocess in that environment.

We do it this way because, by the time we're run, several modules (notably
"sysconfig") have already been initialized with our host Python's parameters.
"""

import argparse
import os
import subprocess
import sys


def _get_build_dir(root):
  with open(os.path.join(root, 'pybuilddir.txt')) as fd:
    return fd.read().strip()


def main(argv):
  def _arg_abspath(v):
    return os.path.abspath(v)

  parser = argparse.ArgumentParser()
  parser.add_argument('--root', type=_arg_abspath,
      help='Root directory of the build Python interpreter.')
  parser.add_argument('args', nargs=argparse.REMAINDER, default=[],
      help='Arguments to forward to the bootstrapped environment.')
  args = parser.parse_args(argv)

  # Read "pybuilddir.txt" to find the build directory, which contains the
  # build-specific system configuration data.
  pybuilddir = _get_build_dir(args.root)

  # Set up our PYTHONPATH to prefer packages in the build directories.
  env = os.environ.copy()
  env.update({
    # This is used by "sysconfig" to override the project base, which is, in
    # turn, used to determine pathing used by "sysconfig".
    '_PYTHON_PROJECT_BASE': args.root,

    # This uses the Python-under-build's package set and configuration.
    'PYTHONPATH': os.pathsep.join([
      args.root,
      os.path.join(args.root, 'Lib'),
      os.path.join(args.root, pybuilddir),
    ] + sys.path),
  })
  return subprocess.call(
      [sys.executable, '-s', '-S'] + args.args,
      env=env,
      cwd=args.root,
  )


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
