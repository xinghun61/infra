# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

import sequence


class SequenceTest(testing.AppengineTestCase):
  def test_generate_async(self):
    def gen(*args):
      return sequence.generate_async(*args).get_result()

    self.assertEqual(gen('a', 1), 1)
    self.assertEqual(gen('a', 2), 2)
    self.assertEqual(gen('b', 1), 1)
    self.assertEqual(gen('a', 1), 4)
