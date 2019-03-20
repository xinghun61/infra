# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import bbutil


class BBUtilTest(unittest.TestCase):
  """Base class for api.py tests."""

  def test_escape_markdown(self):
    text = '[*c*](_x_)\\'
    expected = r'\[\*c\*\]\(\_x\_\)\\'
    actual = bbutil.escape_markdown(text)
    self.assertEqual(expected, actual)
