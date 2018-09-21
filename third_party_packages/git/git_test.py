# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

CIPD_PACKAGE_PATH = None

class TestGit(unittest.TestCase):

  # Public repository that uses HTTPS.
  #
  # This should be highly-available and reachable. As a bonus, it should also
  # be small in order to reduce testing time on slower networks.
  HTTPS_REPO_URL = (
      'https://chromium.googlesource.com/infra/testing/expect_tests')

  @classmethod
  def setUpClass(cls):
    cls._orig_environ = os.environ.copy()
    cls._is_windows = os.name == 'nt'
    cls._exe_suffix = '.exe' if cls._is_windows else ''

    cls.tdir = tempfile.mkdtemp(dir=os.getcwd(), suffix='test_git')

    cls.pkg_dir = os.path.join(cls.tdir, 'install')
    subprocess.check_call([
        'cipd', 'pkg-deploy', CIPD_PACKAGE_PATH, '-root', cls.pkg_dir],
        shell=cls._is_windows)
    cls.bin_dir = os.path.join(cls.pkg_dir, 'bin')

  @classmethod
  def tearDownClass(cls):
    # If we fail to delete, that's fine since we're within the workdir, which
    # gets purged with each build.
    shutil.rmtree(cls.tdir, ignore_errors=True)

  def setUp(self):
    self.workdir = tempfile.mkdtemp(dir=self.tdir)

    # Clear PATH so we don't pick up other Git instances when doing relative
    # path tests.
    os.environ = self._orig_environ.copy()
    os.environ['PATH'] = ''

  def tearDown(self):
    os.environ = self._orig_environ

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
    dst = os.path.join(self.workdir, 'repo')
    os.environ['PATH'] = self.bin_dir

    rv = subprocess.call(['git', 'clone', self.HTTPS_REPO_URL, dst],
                         cwd=self.tdir, shell=self._is_windows)
    self.assertEqual(rv, 0)

  def _setup_test_repo(self, git, path):
    def g(*cmd):
      subprocess.check_call([git, '-C', path] + list(cmd))
    g('init')
    g('config', 'user.name', 'test')
    g('config', 'user.email', 'test@example.com')

    with open(os.path.join(path, 'README'), 'w') as fd:
      fd.write('TEST DATA')
    g('add', '.')
    g('commit', '-m', 'Test data')

  def test_libpcre(self):
    git = os.path.join(self.bin_dir, 'git' + self._exe_suffix)
    self._setup_test_repo(git, self.workdir)

    rv = subprocess.call(
        [git, '--no-pager', 'log', '--perl-regexp', '--author', '^.*$'],
        cwd=self.workdir, shell=self._is_windows)
    self.assertEqual(rv, 0)


if __name__ == '__main__':
  platform = os.environ['_3PP_PLATFORM']
  tool_platform = os.environ['_3PP_TOOL_PLATFORM']
  if platform != tool_platform:
    print 'SKIPPING TESTS'
    print '  platform:', platform
    print '  tool_platform:', tool_platform
    sys.exit(0)

  # Scrape the cipd package out of argv
  CIPD_PACKAGE_PATH = sys.argv[1]
  sys.argv[1:2] = []

  unittest.main()
