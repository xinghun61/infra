# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

# NOTE: Do not use "from ... import __main__", else __name__ == "__main__" will
# be True and the script will execute on import.
import infra.tools.docgen.__main__ as docgen_main


class DocgenTest(unittest.TestCase):
  @mock.patch('subprocess.check_call')
  @mock.patch('shutil.rmtree')
  def test_docgen_default_smoke(self, _rmtree, _check_call):
    argv = []
    self.assertIn(docgen_main.main(argv), (0, None))

  @mock.patch('subprocess.check_call')
  @mock.patch('shutil.rmtree')
  def test_docgen_clean_smoke(self, _rmtree, _check_call):
    argv = ['clean']
    self.assertIn(docgen_main.main(argv), (0, None))

  @mock.patch('subprocess.check_call')
  @mock.patch('shutil.rmtree')
  def test_docgen_run_smoke(self, _rmtree, _check_call):
    argv = ['run']
    self.assertIn(docgen_main.main(argv), (0, None))

  @mock.patch('subprocess.check_call')
  @mock.patch('shutil.rmtree')
  @mock.patch('glob.glob')
  def test_docgen_hooks(self, glob, _rmtree, _check_call):
    glob.return_value = ['testhook.py']

    argv = ['run']
    self.assertIn(docgen_main.main(argv), (0, None))
    self.assertTrue(glob.called)

  @mock.patch('subprocess.check_call')
  @mock.patch('shutil.rmtree')
  def test_docgen_external(self, _check_call, _rmtree):
    argv = ['--root', '/path/to/root', '--base', 'testbase', 'run']
    self.assertIn(docgen_main.main(argv), (0, None))
