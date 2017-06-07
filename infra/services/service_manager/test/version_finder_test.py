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
    self.cipd_version_file = os.path.join(self.path, 'version-file')
    self.config = {
        'cipd_version_file': self.cipd_version_file,
    }

  def tearDown(self):
    shutil.rmtree(self.path)

  def test_empty_directory(self):
    self.assertEqual({}, version_finder.find_version(self.config))

  def test_cipd_version_file(self):
    with open(self.cipd_version_file, 'w') as fh:
      fh.write('{"package_name": "foo", "instance_id": "bar"}')

    self.assertEqual({'cipd_version_file': {
        'package_name': 'foo',
        'instance_id': 'bar',
    }}, version_finder.find_version(self.config))

  def test_explicit_cipd_version_file_does_not_exist(self):
    self.config['cipd_version_file'] = os.path.join(self.path, 'foo')
    self.assertEqual({}, version_finder.find_version(self.config))

  def test_explicit_cipd_version_file_empty_string(self):
    self.config['cipd_version_file'] = ''
    self.assertEqual({}, version_finder.find_version(self.config))
