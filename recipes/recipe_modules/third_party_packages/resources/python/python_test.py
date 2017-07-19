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
    cls._exe_suffix = '.exe' if os.name == 'nt' else ''

  def setUp(self):
    self.tdir = tempfile.mkdtemp(suffix='test_python')

    self.pkg_dir = os.path.join(self.tdir, 'install')
    subprocess.check_call([
      'cipd', 'pkg-deploy', self._cipd_package, '-root', self.pkg_dir])
    self.python = os.path.join(self.pkg_dir, 'bin', 'python' + self._exe_suffix)

  def tearDown(self):
    shutil.rmtree(self.tdir)

  def test_package_import(self):
    for pkg in (
        'ctypes', 'ssl', 'cStringIO', 'binascii', 'hashlib'):
      script = 'import %s; print %s' % (pkg, pkg)
      rv = subprocess.call([self.python, '-c', script])
      self.assertEqual(rv, 0)

  def test_use_https(self):
    script = 'import urllib; print urllib.urlretrieve("%s")' % (
        self.HTTPS_REPO_URL)
    rv = subprocess.call([self.python, '-c', script])
    self.assertEqual(rv, 0)


if __name__ == '__main__':
  unittest.main()
