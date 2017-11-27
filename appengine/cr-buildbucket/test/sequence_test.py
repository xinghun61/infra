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

  def test_set_next_number(self):
    sequence.set_next('a', 1)
    sequence.set_next('a', 1)
    sequence.set_next('a', 2)
    with self.assertRaises(ValueError):
      sequence.set_next('a', 1)
    sequence.set_next('b', 1)

  def test_try_return_async(self):
    self.assertTrue(sequence.try_return_async('a', 1).get_result())
    self.assertEqual(sequence.generate_async('a', 1).get_result(), 1)
    self.assertEqual(sequence.generate_async('a', 1).get_result(), 2)
    self.assertFalse(sequence.try_return_async('a', 1).get_result())
    self.assertTrue(sequence.try_return_async('a', 2).get_result())
