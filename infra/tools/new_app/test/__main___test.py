# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import tempfile
import unittest

from contextlib import contextmanager

import mock

import infra.tools.new_app.__main__ as new_app


@contextmanager
def temporary_dir(basedir=None):
  """Create a temporary directory, and delete it when done."""
  dirname = tempfile.mkdtemp(dir=basedir)
  yield dirname
  shutil.rmtree(dirname)


class NewGaeTest(unittest.TestCase):

  @mock.patch('infra.tools.new_app.__main__.create_app')
  def test_main(self, _create_app):
    # Smoke test for main().
    argv = ['test_app']
    new_app.main(argv)
    _create_app.assert_called_with(os.path.join(
        new_app.APPENGINE_DIR, 'test_app'))

  def test_create_app(self):
    with temporary_dir() as dir_name:
      app_dir = os.path.join(dir_name, 'test_app')
      # Brand new app, must succeed.
      self.assertIsNone(new_app.create_app(app_dir))
      self.assertTrue(os.path.isfile(os.path.join(app_dir, 'app.yaml')))
      # Creating the same app twice must fail.
      self.assertEqual(new_app.create_app(app_dir), 1)
