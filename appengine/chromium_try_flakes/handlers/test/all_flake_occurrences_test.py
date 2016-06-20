# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from handlers import all_flake_occurrences


class TestAllFlakeOccurrences(testing.AppengineTestCase):
  def test_filter_none(self):
    self.assertEqual([1, 2], all_flake_occurrences.filterNone([1, None, 2]))

  def test_is_webkit_name(self):
    self.assertFalse(all_flake_occurrences._is_webkit_test_name('foo'))
    self.assertFalse(all_flake_occurrences._is_webkit_test_name('Foo.Bar'))
    self.assertFalse(all_flake_occurrences._is_webkit_test_name('Foo.Bar/1'))
    self.assertFalse(all_flake_occurrences._is_webkit_test_name('Foo.Bar/One'))
    self.assertTrue(all_flake_occurrences._is_webkit_test_name('foo/bar.html'))
    self.assertTrue(all_flake_occurrences._is_webkit_test_name('foo/bar.svg'))
