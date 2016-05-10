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
  print """\nUsage: %s <action> [<test names>] [<expect_tests options>]

  where <action> is one of: list, test, train, debug.

  Examples:
  Run all tests:
    ./test.py test
  Run all tests in the infra package:
    ./test.py test infra
  Run all tests and generate an HTML report:
    ./test.py test infra --html-report /path/to/report/folder
  Run one given test in the infra package:
    ./test.py test infra/libs/git2/test:*testCommitBogus

  See expect_tests documentation for more details
  """ % sys.argv[0]


INFRA_ROOT = os.path.dirname(os.path.abspath(__file__))

# Whitelist of packages to test on Windows.
WIN_ENABLED_PACKAGES = [
  'infra/libs/buildbot',
  'infra/libs/decorators',
  'infra/libs/gitiles',
  'infra/libs/process_invocation',
  'infra/libs/service_utils',
  'infra/libs/state_machine',

  'infra/services/service_manager',
  'infra/services/sysmon',

  'infra_libs/event_mon',
  'infra_libs/infra_types',
  'infra_libs/logs',
  'infra_libs/time_functions',
  'infra_libs/ts_mon',

  'infra_libs:infra_libs.test.*',
]


# Parse command-line arguments
if len(sys.argv) == 1:
  usage()
  sys.exit(1)
else:
  if not sys.argv[1] in ('list', 'train', 'test', 'debug'):
    usage()
    sys.exit(1)

if sys.platform == 'win32':
  python_bin = os.path.join('ENV', 'Scripts', 'python')
  expect_tests_path = os.path.join('ENV', 'Scripts', 'expect_tests')
else:
  python_bin = os.path.join('ENV', 'bin', 'python')
  expect_tests_path = os.path.join('ENV', 'bin', 'expect_tests')

command = sys.argv[1]
args = sys.argv[2:]

modules = []
flags = []
for arg in args:
  if arg.startswith('-'):
    flags.append(arg)
    continue
  if flags:
    flags.append(arg)
  else:
    modules.append(arg)

# Set up default list of packages/directories if none have been provided.
if not modules:
  if sys.platform == 'win32':
    modules.extend(WIN_ENABLED_PACKAGES)
  else:
    modules.extend(['infra', 'infra_libs'])  # TODO(pgervais): add 'test/'
  appengine_dir = os.path.join(INFRA_ROOT, 'appengine')
  if sys.platform != 'win32' and os.path.isdir(appengine_dir):
    modules.extend(['appengine_module'])
    appengine_dirs = [
      os.path.join('appengine', d)
      for d in os.listdir(appengine_dir)
    ]
    # Use relative paths to shorten the command-line
    modules.extend(itertools.chain(
      [d for d in appengine_dirs if os.path.isfile(os.path.join(d, 'app.yaml'))]
    ))

os.environ['PYTHONPATH'] = ''
os.chdir(INFRA_ROOT)
if '--help' not in flags and '-h' not in flags:
  subprocess.check_call(
      [python_bin, os.path.join('bootstrap', 'remove_orphaned_pycs.py')])
else:
  usage()
  sys.exit(subprocess.call([python_bin, expect_tests_path, command, '--help']))

if sys.platform == 'win32' and '--force-coverage' not in flags:
  flags.append('--no-coverage')

exit_code = 0
failed_modules = []
for module in modules:
  print 'Running %s...' % module
  module_flags = flags[:]
  module_flags.append('--coveragerc=%s' % os.path.join(
      INFRA_ROOT, module, '.coveragerc'))
  module_flags.append('--html-report-subdir=%s' % module)
  cmd = [python_bin, expect_tests_path, command, module] + module_flags
  module_exit_code = subprocess.call(cmd)
  exit_code = module_exit_code or exit_code
  if module_exit_code:
    failed_modules.append(module)

if exit_code:
  print 'Tests failed in modules:\n  %s' % '\n  '.join(failed_modules)
  if '--html-report' not in flags:
    print '\nFor detailed coverage report and per-line branch coverage,'
    print 'rerun with --html-report <dir>'
else:
  print 'All tests passed.'

sys.exit(exit_code)
