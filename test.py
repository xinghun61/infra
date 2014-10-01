#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Convenience script for (cd [infra] && ENV/bin/expect_tests "$@")"""

assert __name__ == '__main__'

import itertools
import os
import sys
import subprocess
import imp


def usage():
  print """\nUsage: %s <action> [<expect_tests options>] [<test names>]

  where <action> is one of: list, test, train, debug.

  Examples:
  Run all tests:
    ./test.py test
  Run all tests in the infra package:
    ./test.py test --package infra
  Run one given test in the infra package:
    ./test.py test --package infra \
        infra.libs.git2.test.ref_test.TestRef.testCommitBogus

  See expect_tests documentation for more details

  If no arguments are provided, run all tests in all packages.
  """ % sys.argv[0]
  sys.exit(1)


# FIXME: We should share this logic with PRESUBMIT.py
def appengine_library_paths(appengine_env_path):  # pragma: no cover
  # AppEngine has a wrapper_util module which knows where the various
  # appengine libraries are stored inside the SDK. All AppEngine scripts
  # 'import wrapper_util' and then call its various methods to get those
  # paths to fix their sys.path. Since AppEngine isn't in our sys.path yet
  # we use imp.load_source to load wrapper_util from an absolute path
  # and then call its methods to get all the paths to the AppEngine-provided
  # libraries to add to sys.path when calling expect_tests.
  wrapper_util_path = os.path.join(appengine_env_path,
      'wrapper_util.py')
  wrapper_util = imp.load_source('wrapper_util', wrapper_util_path)
  wrapper_util_paths = wrapper_util.Paths(appengine_env_path)
  appengine_lib_paths = wrapper_util_paths.script_paths('dev_appserver.py')
  # Unclear if v2_extra_paths is correct here, it contains endpoints
  # and protorpc which several apps seem to depend on.
  return appengine_lib_paths + wrapper_util_paths.v2_extra_paths


# Set up appengine path.
INFRA_ROOT = os.path.dirname(os.path.abspath(__file__))
ABOVE_INFRA_ROOT = os.path.dirname(INFRA_ROOT)
APPENGINE_ENV_PATH = os.path.join(ABOVE_INFRA_ROOT, 'google_appengine')

appengine_paths = appengine_library_paths(APPENGINE_ENV_PATH)
os.environ['PYTHONPATH'] += (os.path.pathsep +
      os.path.pathsep.join(appengine_paths).encode('utf8'))

# Parse command-line arguments
if len(sys.argv) == 1:
  args = ['test']
else:
  if not sys.argv[1] in ('list', 'train', 'test', 'debug'):
    usage()
  args = [sys.argv[1]]


# Set up default list of packages/directories if none have been provided.
if '--package' not in sys.argv and '--directory' not in sys.argv:
  args.extend(['--package', 'infra', '--package', 'test'])
  appengine_dirs = [os.path.join('appengine', d)
                    for d in os.listdir(os.path.join(INFRA_ROOT, 'appengine'))]
  appengine_dirs.extend([os.path.join('appengine_apps', d)
                         for d in os.listdir(os.path.join(INFRA_ROOT,
                                                          'appengine_apps'))])
  # Use relative paths to shorten the command-line
  args.extend(itertools.chain(*[
    ('--directory', d)
    for d in appengine_dirs
    if os.path.isfile(os.path.join(d, 'app.yaml'))])
              )
else:
  args = sys.argv[1:]

os.chdir(INFRA_ROOT)
subprocess.check_call(os.path.join('bootstrap', 'remove_orphaned_pycs.py'))
path = os.path.join('ENV', 'bin', 'expect_tests')
os.execv(path, [path] + args)
