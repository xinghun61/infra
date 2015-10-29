#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Convenience script for expect_tests"""

assert __name__ == '__main__'

import itertools
import os
import subprocess
import sys


def usage():
  print """\nUsage: %s <action> [<expect_tests options>] [<test names>]

  where <action> is one of: list, test, train, debug.

  Examples:
  Run all tests:
    ./test.py test
  Run all tests in the infra package:
    ./test.py test infra
  Run one given test in the infra package:
    ./test.py test infra/libs/git2/test:*testCommitBogus

  See expect_tests documentation for more details
  """ % sys.argv[0]
  sys.exit(1)


INFRA_ROOT = os.path.dirname(os.path.abspath(__file__))

# Whitelist of packages to test on Windows.
WIN_ENABLED_PACKAGES = [
  'infra/libs/buildbot',
  'infra/libs/decorators',
  'infra/libs/gitiles',
  'infra/libs/process_invocation',
  'infra/libs/service_utils',
  'infra/libs/state_machine',
  'infra/libs/time_functions',

  'infra/services/service_manager',
  'infra/services/sysmon',

  'infra_libs/event_mon',
  'infra_libs/infra_types',
  'infra_libs/logs',
  'infra_libs/ts_mon',

  'infra_libs:infra_libs.test.*',
]


# Parse command-line arguments
if len(sys.argv) == 1:
  usage()
else:
  if not sys.argv[1] in ('list', 'train', 'test', 'debug'):
    usage()

if sys.platform == 'win32':
  python_bin = os.path.join('ENV', 'Scripts', 'python')
  expect_tests_path = os.path.join('ENV', 'Scripts', 'expect_tests')
else:
  python_bin = os.path.join('ENV', 'bin', 'python')
  expect_tests_path = os.path.join('ENV', 'bin', 'expect_tests')

args = sys.argv[1:]

# Set up default list of packages/directories if none have been provided.
if all([arg.startswith('--') for arg in sys.argv[2:]]):
  if sys.platform == 'win32':
    args.extend(WIN_ENABLED_PACKAGES)
  else:
    args.extend(['infra', 'infra_libs'])  # TODO(pgervais): add 'test/'
  appengine_dir = os.path.join(INFRA_ROOT, 'appengine')
  if sys.platform != 'win32' and os.path.isdir(appengine_dir):
    appengine_dirs = [
      os.path.join('appengine', d)
      for d in os.listdir(appengine_dir)
    ]
    # Use relative paths to shorten the command-line
    args.extend(itertools.chain(
      [d for d in appengine_dirs if os.path.isfile(os.path.join(d, 'app.yaml'))]
    ))

os.environ['PYTHONPATH'] = ''
os.chdir(INFRA_ROOT)
if '--help' not in sys.argv and '-h' not in sys.argv:
  subprocess.check_call(
      [python_bin, os.path.join('bootstrap', 'remove_orphaned_pycs.py')])
if sys.platform == 'win32' and '--force-coverage' not in args:
  args.append('--no-coverage')
sys.exit(subprocess.call([python_bin, expect_tests_path] + args))
