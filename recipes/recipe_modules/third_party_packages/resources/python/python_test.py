# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import subprocess
import tempfile
import unittest


class TestPython(unittest.TestCase):

  # Public repository that uses HTTPS.
  HTTPS_REPO_URL = 'https://chromium.googlesource.com/infra/infra'

  @classmethod
  def setUpClass(cls):
    cls._cipd_package = os.environ['PYTHON_TEST_CIPD_PACKAGE']
    cls._is_windows = os.name == 'nt'
    cls._exe_suffix = '.exe' if cls._is_windows else ''

    cls.tdir = tempfile.mkdtemp(dir=os.getcwd(), suffix='test_python')

    cls.pkg_dir = os.path.join(cls.tdir, 'install')
    subprocess.check_call([
      'cipd', 'pkg-deploy', cls._cipd_package, '-root', cls.pkg_dir],
      shell=cls._is_windows)
    cls.python = os.path.join(cls.pkg_dir, 'bin', 'python' + cls._exe_suffix)

  @classmethod
  def tearDownClass(cls):
    # If we fail to delete, that's fine since we're within the workdir, which
    # gets purged with each build.
    shutil.rmtree(cls.tdir, ignore_errors=True)

  def test_package_import(self):
    for pkg in (
        'ctypes', 'ssl', 'cStringIO', 'binascii', 'hashlib', 'sqlite3'):
      script = 'import %s; print %s' % (pkg, pkg)
      rv = subprocess.call([self.python, '-c', script])
      self.assertEqual(rv, 0)

  def test_use_https(self):
    script = 'import urllib; print urllib.urlretrieve("%s")' % (
        self.HTTPS_REPO_URL)
    rv = subprocess.call([self.python, '-c', script])
    self.assertEqual(rv, 0)

  def test_sqlite_version(self):
    script = (
        'import sqlite3; '
        'print ".".join(str(x) for x in sqlite3.sqlite_version_info)')
    proc = subprocess.Popen([self.python, '-c', script],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, _ = proc.communicate()
    self.assertEqual(proc.returncode, 0)
    self.assertEqual(stdout.strip(), '3.19.3') # Matches sqlite3 CIPD package.


if __name__ == '__main__':
  unittest.main()
