# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

import infra.tools.docgen.__main__ as docgen_main


class DocgenTest(unittest.TestCase):
  @mock.patch('subprocess.check_call')
  @mock.patch('shutil.rmtree')
  def test_docgen_default_smoke(self, _check_call, _rmtree):
    argv = []
    self.assertIn(docgen_main.main(argv), (0, None))

  @mock.patch('subprocess.check_call')
  @mock.patch('shutil.rmtree')
  def test_docgen_clean_smoke(self, _check_call, _rmtree):
    argv = ['clean']
    self.assertIn(docgen_main.main(argv), (0, None))

  @mock.patch('subprocess.check_call')
  @mock.patch('shutil.rmtree')
  def test_docgen_run_smoke(self, _check_call, _rmtree):
    argv = ['run']
    self.assertIn(docgen_main.main(argv), (0, None))
