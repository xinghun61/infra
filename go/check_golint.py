#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs golint for given packages, returns non zero code if errors are detected.

Intended to be used from a presubmit check. It's necessary since golint doesn't
return non zero exit code ever. Expects golint to be in PATH (use ./env.py to
set this up).
"""

import subprocess
import sys


def main(args):
  proc = subprocess.Popen(
      ['golint'] + args,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT)
  out = proc.communicate()[0].strip()
  if out or proc.returncode:
    print out or 'Unrecognized error'
    return proc.returncode or 1
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
