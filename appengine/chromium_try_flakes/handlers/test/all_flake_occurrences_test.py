# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from handlers import all_flake_occurrences


class TestAllFlakeOccurrences(testing.AppengineTestCase):
  def test_filter_none(self):
    self.assertEqual([1, 2], all_flake_occurrences.filterNone([1, None, 2]))
