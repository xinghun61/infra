#!/usr/bin/env vpython
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs all Go unit tests in a directory.

Expects Go toolset to be in PATH, GOPATH and GOROOT correctly set. Use ./env.py
to set them up.

Usage:
  test.py [root package path]

By default runs all tests for infra/*.
"""

# TODO(vadimsh): Get rid of this and call "go test ./..." directly from recipes.
# This file once had a much more complicated implementation that verified code
# coverage and allowed skipping tests per platform.

import errno
import os
import subprocess
import sys


def check_go_available():
  """Returns True if go executable is in the PATH."""
  try:
    subprocess.check_output(['go', 'version'], stderr=subprocess.STDOUT)
    return True
  except subprocess.CalledProcessError:
    return False
  except OSError as err:
    if err.errno == errno.ENOENT:
      return False


def clean_go_bin():
  """Removes all files in GOBIN.

  GOBIN is in PATH in our environment. There are some binaries there (like 'git'
  for gitwrapper), that get mistakenly picked up by the tests.
  """
  gobin = os.environ.get('GOBIN')
  if not gobin:
    return
  for p in os.listdir(gobin):
    os.remove(os.path.join(gobin, p))


def run_tests(package_root):
  """Runs 'go test <package_root>/...'.

  Returns:
    0 if all tests pass..
  """
  if not check_go_available():
    print 'Can\'t find Go executable in PATH.'
    print 'Use ./env.py python test.py'
    return 1
  clean_go_bin()
  proc = subprocess.Popen(['go', 'test', '%s/...' % package_root])
  proc.wait()
  return proc.returncode


def main(args):
  if not args:
    package_root = 'infra'
  elif len(args) == 1:
    package_root = args[0]
  else:
    print >> sys.stderr, sys.modules['__main__'].__doc__.strip()
    return 1
  return run_tests(package_root)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
