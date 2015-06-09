# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool-specific testable functions for antibody."""

import argparse
import unittest

from infra.tools.antibody import antibody


class MyTest(unittest.TestCase):
  def test_arguments(self):
    parser = argparse.ArgumentParser()
    antibody.add_argparse_options(parser)
    args = parser.parse_args(['--my-argument', 'value'])
    self.assertEqual(args.my_argument, 'value')

## expect_tests style: the test method returns a value (expectation)
## that is stored when run in 'train' mode, and compared to in 'test' mode.
## If the stored and returned values do not match, the test fails.
##
##   def test_my_first_test_with_expectation(self):
##     # Use hash() here to make sure the test fails in any case.
##     return hash(MyTest)
