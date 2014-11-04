# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
from infra.services.builder_alerts import string_helpers


class StringHelpersTest(unittest.TestCase):
  def test_re_range(self):
    self.assertEquals(string_helpers.re_range([3, 2, 1]), "1-3")
    self.assertEquals(string_helpers.re_range([1, 1]), "1, 1")
    self.assertEquals(string_helpers.re_range([1, 2, 2, 3]), "1-2, 2-3")

  def test_longest_substring(self):
    self.assertEquals(string_helpers.longest_substring('foo', 'bar'), '')
    self.assertEquals(string_helpers.longest_substring('foo', 'foo'), 'foo')
    self.assertEquals(string_helpers.longest_substring('aa', 'aaa'), 'aa')
    self.assertEquals(string_helpers.longest_substring('aaa', 'aa'), 'aa')
