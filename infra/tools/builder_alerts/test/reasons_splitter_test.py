# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
from infra.tools.builder_alerts import reasons_splitter


class SplitterTests(unittest.TestCase):
  def handles_step_test(self):
    name_tests = [
      ('compile', CompileSplitter),
      ('webkit_tests', LayoutTestsSplitter),
      ('androidwebview_instrumentation_tests', JUnitSplitter),
      ('foo_test', GTestSplitter),
    ]
    for step_name, expected_class in name_tests:
      step = {
        'name': step_name
      }
      splitter = splitter_for_step(step)
      if expected_class is None:
        self.assertEqual(splitter, None)
      else:
        self.assertEqual(splitter.__class__, expected_class)

