# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import tempfile
import unittest

from infra.services.service_manager import version_finder


class VersionFinderTest(unittest.TestCase):

  def setUp(self):
    self.path = tempfile.mkdtemp()
    self.config = {
        'root_directory': self.path,
    }

  def tearDown(self):
    shutil.rmtree(self.path)

  def test_empty_directory(self):
    self.assertEqual({}, version_finder.find_version(self.config))

  def test_missing_directory(self):
    self.assertEqual({}, version_finder.find_version({
        'root_directory': '/does/not/exist',
    }))

  def test_cipd_packages(self):
    foo_pkg = os.path.join(self.path, '.cipd', 'pkgs', 'foo')
    os.makedirs(foo_pkg)
    os.symlink('12345', os.path.join(foo_pkg, '_current'))

    self.assertEqual(
        {'cipd': {'foo': '12345'}},
        version_finder.find_version(self.config))

  def test_cipd_empty_directory(self):
    pkgs = os.path.join(self.path, '.cipd', 'pkgs')
    os.makedirs(pkgs)

    self.assertEqual({'cipd': {}}, version_finder.find_version(self.config))

  def test_cipd_non_symlinks(self):
    pkgs = os.path.join(self.path, '.cipd', 'pkgs')
    foo_pkg = os.path.join(pkgs, 'foo_pkg')
    bar_pkg = os.path.join(pkgs, 'bar_pkg')

    for path in (foo_pkg, bar_pkg):
      os.makedirs(path)

    with open(os.path.join(foo_pkg, '_current'), 'w') as fh:
      fh.write('12345')

    os.mkdir(os.path.join(bar_pkg, '_current'))

    self.assertEqual({'cipd': {}}, version_finder.find_version(self.config))
