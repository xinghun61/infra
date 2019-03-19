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

  def test_migration(self):
    old_name = 'luci.chromium.try/linux'
    new_name = 'chromium/try/linux'
    sequence.NumberSequence(id=old_name, next_number=42).put()
    self.assertEqual(sequence.generate_async(new_name, 1).get_result(), 42)

    old = sequence.NumberSequence.get_by_id(old_name)
    new = sequence.NumberSequence.get_by_id(new_name)

    self.assertIsNone(old)
    self.assertEqual(new.next_number, 43)

    self.assertEqual(sequence.generate_async(new_name, 1).get_result(), 43)

  def test_migration_no_entity(self):
    new_name = 'chromium/try/linux'
    self.assertEqual(sequence.generate_async(new_name, 1).get_result(), 1)
