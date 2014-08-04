# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra.tools.builder_alerts import reasons_splitter


class SplitterTests(unittest.TestCase):
  def test_handles_step(self):
    name_tests = [
      ('compile', reasons_splitter.CompileSplitter),
      ('webkit_tests', reasons_splitter.LayoutTestsSplitter),
      ('androidwebview_instrumentation_tests', reasons_splitter.JUnitSplitter),
      ('foo_tests', reasons_splitter.GTestSplitter),
      ('foo_test', None),
    ]
    for step_name, expected_class in name_tests:
      splitter = reasons_splitter.splitter_for_step({'name': step_name})
      if expected_class is None:
        self.assertIsNone(splitter)
      else:
        self.assertEqual(splitter.__class__, expected_class)
