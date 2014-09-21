#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Checks that specified Go files are properly formatted (using gofmt).

Intended to be used from a presubmit check. Reads list of paths from stdin.
Expects go toolset to be in PATH (use ./env.py to set this up).
"""

import os
import subprocess
import sys


WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))


def check_file(path, verbose):
  proc = subprocess.Popen(
      ['gofmt', '-d', path],
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE)
  out, err = proc.communicate()
  if proc.returncode:
    print err,
    return False
  if out:
    if verbose:
      print out,
    return False
  return True


def main(args):
  verbose = '--verbose' in args
  bad = []
  for path in sys.stdin:
    path = path.rstrip()
    if path and not check_file(path, verbose):
      bad.append(path)
  if bad:
    root = WORKSPACE_ROOT.rstrip(os.sep) + os.sep
    print 'Badly formated Go files:'
    for p in bad:
      if p.startswith(root):
        p = p[len(root):]
      print '  %s' % p
    print
    print 'Consider running \'go fmt infra/...\''
  return 0 if not bad else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
