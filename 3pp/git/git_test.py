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
    os.environ.pop('GIT_CONFIG_NOSYSTEM', None)

    cls._exe_suffix = '.exe' if os.name == 'nt' else ''

    cls.tdir = os.path.abspath(
      tempfile.mkdtemp(dir=os.getcwd(), suffix='test_git'))

    cls.pkg_dir = os.path.join(cls.tdir, 'install')
    subprocess.check_call([
      'cipd' + cls._exe_suffix,
      'pkg-deploy', CIPD_PACKAGE_PATH, '-root', cls.pkg_dir
    ])
    cls.bin_dir = os.path.join(cls.pkg_dir, 'bin')

  @classmethod
  def tearDownClass(cls):
    # If we fail to delete, that's fine since we're within the workdir, which
    # gets purged with each build.
    shutil.rmtree(cls.tdir, ignore_errors=True)

  def setUp(self):
    self.workdir = tempfile.mkdtemp(dir=self.tdir)

  def test_version_from_relpath(self):
    # in python 2.7, `cwd` doesn't change the lookup of executables, so we have
    # to use os.chdir.
    cwd = os.getcwd()
    try:
      os.chdir(self.bin_dir)
      out = subprocess.check_output(
        [os.path.join('.', 'git' + self._exe_suffix), 'version'])
    finally:
      os.chdir(cwd)
    self.assertIn(os.environ['_3PP_VERSION'], out)

  def test_clone_from_relpath(self):
    git = os.path.join('install', 'bin', 'git' + self._exe_suffix)
    # See test_version_from_relpath.
    cwd = os.getcwd()
    try:
      os.chdir(self.tdir)
      dst = os.path.join(self.workdir, 'repo')
      rv = subprocess.call([git, 'clone', self.HTTPS_REPO_URL, dst])
    finally:
      os.chdir(cwd)

    self.assertEqual(rv, 0)

  def test_clone_from_abspath(self):
    git = os.path.join(self.bin_dir, 'git' + self._exe_suffix)
    dst = os.path.join(self.workdir, 'repo')
    rv = subprocess.call([git, 'clone', self.HTTPS_REPO_URL, dst],
        cwd=self.tdir)
    self.assertEqual(rv, 0)

  def test_clone_from_indirect_path(self):
    dst = os.path.join(self.workdir, 'repo')

    ogPATH = os.environ['PATH']
    try:
      os.environ['PATH'] = self.bin_dir
      rv = subprocess.call(
        ['git' + self._exe_suffix, 'clone', self.HTTPS_REPO_URL, dst],
        cwd=self.tdir)
      self.assertEqual(rv, 0)
    finally:
      os.environ['PATH'] = ogPATH

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
        cwd=self.workdir)
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

  unittest.main(verbosity=2)
