# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import shutil
import subprocess
import tempfile
import unittest


PYTHON_TEST_CIPD_PACKAGE = None


class TestPython(unittest.TestCase):

  # Public repository that uses HTTPS.
  HTTPS_REPO_URL = 'https://chromium.googlesource.com/infra/infra'

  @classmethod
  def setUpClass(cls):
    cls._expected_version = os.environ['_3PP_VERSION']
    if '_3PP_PATCH_VERSION' in os.environ:
      cls._expected_version += '+' + os.environ['_3PP_PATCH_VERSION']
    cls._is_windows = os.name == 'nt'
    cls._exe_suffix = '.exe' if cls._is_windows else ''

    cls.tdir = tempfile.mkdtemp(dir=os.getcwd(), suffix='test_python')

    cls.pkg_dir = os.path.join(cls.tdir, 'install')
    subprocess.check_call([
      'cipd', 'pkg-deploy', PYTHON_TEST_CIPD_PACKAGE, '-root', cls.pkg_dir],
      shell=cls._is_windows)
    cls.python = os.path.join(cls.pkg_dir, 'bin', 'python3' + cls._exe_suffix)

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(cls.tdir, ignore_errors=True)

  def setUp(self):
    self.test_tdir = tempfile.mkdtemp(dir=self.tdir)
    self.env = os.environ.copy()

  def _write_file(self, content):
    fd = None
    try:
      fileno, path = tempfile.mkstemp(dir=self.test_tdir)
      fd = os.fdopen(fileno, 'w')
      fd.write(content)
      return path
    finally:
      if fd:
        fd.close()

  def test_version(self):
    output = subprocess.check_output(
        [self.python, '--version'],
        stderr=subprocess.STDOUT)
    self.assertTrue(output.startswith('Python '))
    self.assertEqual(output.lstrip('Python ').strip(), self._expected_version)

  def test_package_import(self):
    for pkg in (
        'ctypes', 'ssl', 'io', 'binascii', 'hashlib', 'sqlite3'):
      script = 'import %s; print(%s)' % (pkg, pkg)
      rv = subprocess.call([self.python, '-c', script])
      self.assertEqual(rv, 0, 'Could not import %r.' % (pkg,))

  def test_use_https(self):
    script = 'import urllib.request; print(urllib.request.urlopen("%s"))' % (
        self.HTTPS_REPO_URL)
    rv = subprocess.call([self.python, '-c', script])
    self.assertEqual(rv, 0)


if __name__ == '__main__':
  platform = os.environ['_3PP_PLATFORM']
  tool_platform = os.environ['_3PP_TOOL_PLATFORM']
  if 'windows' not in platform and platform != tool_platform:
    print 'SKIPPING TESTS'
    print '  platform:', platform
    print '  tool_platform:', tool_platform
    sys.exit(0)

  PYTHON_TEST_CIPD_PACKAGE = sys.argv[1]
  sys.argv.pop(1)
  unittest.main()
