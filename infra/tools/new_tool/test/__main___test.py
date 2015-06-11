# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import infra.tools.new_tool.__main__ as new_tool_main
import infra_libs


class TestMain(unittest.TestCase):
  def test_run_main(self):
    with infra_libs.temporary_directory(prefix='new-tool-test-') as tempdir:
      new_tool_main.main(['whatever_tool', '--base-dir', tempdir])
      self.assertTrue(os.path.isdir(os.path.join(tempdir, 'whatever_tool')))
