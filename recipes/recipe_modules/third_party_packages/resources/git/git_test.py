# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import subprocess
import tempfile
import unittest


class TestGit(unittest.TestCase):

  # Public repository that uses HTTPS.
  HTTPS_REPO_URL = 'https://chromium.googlesource.com/infra/infra'

  @classmethod
  def setUpClass(cls):
    cls._cipd_package = os.environ['GIT_TEST_CIPD_PACKAGE']
    cls._is_windows = os.name == 'nt'
    cls._exe_suffix = '.exe' if cls._is_windows else ''

    cls.tdir = tempfile.mkdtemp(dir=os.getcwd(), suffix='test_git')

    cls.pkg_dir = os.path.join(cls.tdir, 'install')
    subprocess.check_call([
        'cipd', 'pkg-deploy', cls._cipd_package, '-root', cls.pkg_dir],
        shell=cls._is_windows)
    cls.bin_dir = os.path.join(cls.pkg_dir, 'bin')

  @classmethod
  def tearDownClass(cls):
    # If we fail to delete, that's fine since we're within the workdir, which
    # gets purged with each build.
    shutil.rmtree(cls.tdir, ignore_errors=True)

  def setUp(self):
    self.workdir = tempfile.mkdtemp(dir=self.tdir) 

  def test_version_from_relpath(self):
    rv = subprocess.call(['git', 'version'],
        cwd=self.bin_dir, shell=self._is_windows)
    self.assertEqual(rv, 0)

  def test_clone_from_relpath(self):
    git = os.path.join('install', 'bin', 'git' + self._exe_suffix)
    dst = os.path.join(self.workdir, 'repo')
    rv = subprocess.call([git, 'clone', self.HTTPS_REPO_URL, dst],
        cwd=self.tdir, shell=self._is_windows)
    self.assertEqual(rv, 0)

  def test_clone_from_abspath(self):
    git = os.path.join(self.bin_dir, 'git' + self._exe_suffix)
    dst = os.path.join(self.workdir, 'repo')
    rv = subprocess.call([git, 'clone', self.HTTPS_REPO_URL, dst],
        cwd=self.tdir, shell=self._is_windows)
    self.assertEqual(rv, 0)

  def test_clone_from_indirect_path(self):
    env = os.environ.copy()
    dst = os.path.join(self.workdir, 'repo')
    env['PATH'] = '%s%s%s' % (self.bin_dir, os.pathsep, env.get('PATH', ''))

    rv = subprocess.call(['git', 'clone', self.HTTPS_REPO_URL, dst],
                         cwd=self.tdir, env=env, shell=self._is_windows)
    self.assertEqual(rv, 0)


if __name__ == '__main__':
  unittest.main()
