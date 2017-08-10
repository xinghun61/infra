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
    cls._exe_suffix = '.exe' if os.name == 'nt' else ''

  def setUp(self):
    self.tdir = tempfile.mkdtemp(dir=os.getcwd(), suffix='test_git')

    self.pkg_dir = os.path.join(self.tdir, 'install')
    subprocess.check_call([
      'cipd', 'pkg-deploy', self._cipd_package, '-root', self.pkg_dir])
    self.bin_dir = os.path.join(self.pkg_dir, 'bin')

  def tearDown(self):
    # If we fail to delete, that's fine since we're within the workdir, which
    # gets purged with each build.
    shutil.rmtree(self.tdir, ignore_errors=True)

  def test_version_from_relpath(self):
    rv = subprocess.call(['git', 'version'], cwd=self.bin_dir)
    self.assertEqual(rv, 0)

  def test_clone_from_relpath(self):
    git = os.path.join('install', 'bin', 'git' + self._exe_suffix)
    rv = subprocess.call([git, 'clone', self.HTTPS_REPO_URL], cwd=self.tdir)
    self.assertEqual(rv, 0)

  def test_clone_from_abspath(self):
    git = os.path.join(self.bin_dir, 'git' + self._exe_suffix)
    rv = subprocess.call([git, 'clone', self.HTTPS_REPO_URL], cwd=self.tdir)
    self.assertEqual(rv, 0)

  def test_clone_from_indirect_path(self):
    env = os.environ.copy()
    env['PATH'] = '%s%s%s' % (self.bin_dir, os.pathsep, env.get('PATH', ''))

    rv = subprocess.call(['git', 'clone', self.HTTPS_REPO_URL],
                         cwd=self.tdir, env=env)
    self.assertEqual(rv, 0)


if __name__ == '__main__':
  unittest.main()
