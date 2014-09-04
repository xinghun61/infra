#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Convenience script for (cd [infra] && ENV/bin/expect_tests "$@")"""

assert __name__ == '__main__'

import os
import sys
import subprocess
import imp


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


INFRA_ROOT = os.path.dirname(os.path.abspath(__file__))
ABOVE_INFRA_ROOT = os.path.dirname(INFRA_ROOT)
APPENGINE_ENV_PATH = os.path.join(ABOVE_INFRA_ROOT, 'google_appengine')

appengine_paths = appengine_library_paths(APPENGINE_ENV_PATH)
os.environ['PYTHONPATH'] += (os.path.pathsep +
      os.path.pathsep.join(appengine_paths).encode('utf8'))

os.chdir(INFRA_ROOT)
path = os.path.join('ENV', 'bin', 'expect_tests')
subprocess.check_call(os.path.join('bootstrap', 'remove_orphaned_pycs.py'))
os.execv(path, [path] + sys.argv[1:])
