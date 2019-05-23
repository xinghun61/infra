# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import unittest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(THIS_DIR, '..', 'standalone.vpython')
TESTDATA = os.path.join(THIS_DIR, 'testdata')


class TestSmoke(unittest.TestCase):
  """Verifies some important wheels are actually usable.

  Assumes 'vpython' is in PATH.
  """

  def test_check_requests(self):
    code, out = run_vpython(os.path.join(TESTDATA, 'check_requests.py'))
    if code:
      self.fail(out)


def run_vpython(script):
  """Runs the given script through vpython.

  Returns:
    (exit code, combined stdout+stderr).
  """
  env = escape_virtual_env(os.environ)
  env['PYTHONDONTWRITEBYTECODE'] = '1'
  proc = subprocess.Popen(
      ['vpython', '-vpython-spec', SPEC, script],
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT)
  out, _ = proc.communicate()
  return proc.returncode, out


def escape_virtual_env(environ):
  """Returns a copy of environ which is free of a virtualenv references."""
  environ = environ.copy()
  venv = environ.pop('VIRTUAL_ENV', None)
  if venv:
    path = environ['PATH'].split(os.pathsep)
    path = [p for p in path if not p.startswith(venv+os.sep)]
    environ['PATH'] = os.pathsep.join(path)
  return environ
