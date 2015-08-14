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

  def test_cipd_version_file(self):
    with open(os.path.join(self.path, 'CIPD_VERSION.json'), 'w') as fh:
      fh.write('{"package_name": "foo", "instance_id": "bar"}')

    self.assertEqual({'cipd_version_file': {
        'package_name': 'foo',
        'instance_id': 'bar',
    }}, version_finder.find_version(self.config))
