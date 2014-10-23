# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from appengine_module.chromium_status import commit_queue


class TestOrdinalNumbers(unittest.TestCase):
  def test_small_numbers(self):
    self.assertEqual(commit_queue.ordinal_number(1), '1st')
    self.assertEqual(commit_queue.ordinal_number(2), '2nd')
    self.assertEqual(commit_queue.ordinal_number(3), '3rd')
    self.assertEqual(commit_queue.ordinal_number(4), '4th')
    self.assertEqual(commit_queue.ordinal_number(5), '5th')
    self.assertEqual(commit_queue.ordinal_number(6), '6th')
    self.assertEqual(commit_queue.ordinal_number(7), '7th')
    self.assertEqual(commit_queue.ordinal_number(8), '8th')
    self.assertEqual(commit_queue.ordinal_number(9), '9th')
    self.assertEqual(commit_queue.ordinal_number(10), '10th')

  def test_large_numbers(self):
    self.assertEqual(commit_queue.ordinal_number(11), '11th')
    self.assertEqual(commit_queue.ordinal_number(12), '12th')
    self.assertEqual(commit_queue.ordinal_number(13), '13th')
    self.assertEqual(commit_queue.ordinal_number(14), '14th')
    self.assertEqual(commit_queue.ordinal_number(21), '21st')
    self.assertEqual(commit_queue.ordinal_number(42), '42nd')
    self.assertEqual(commit_queue.ordinal_number(183), '183rd')
    self.assertEqual(commit_queue.ordinal_number(1011), '1011th')
