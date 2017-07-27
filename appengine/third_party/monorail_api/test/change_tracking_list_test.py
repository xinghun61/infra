# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from monorail_api.change_tracking_list import ChangeTrackingList


class ChangeTrackingListTestCase(unittest.TestCase):
  def test_keeps_track_of_changes(self):
    crl = ChangeTrackingList(['a', 'b', 'c'])
    crl.append('d')
    crl.remove('b')

    self.assertTrue(crl.isChanged())
    self.assertEquals(crl.added, set(['d']))
    self.assertEquals(crl.removed, set(['b']))
    self.assertEquals(crl, ['a', 'c', 'd'])

  def test_resets_changes(self):
    crl = ChangeTrackingList(['a', 'b', 'c'])
    crl.append('d')
    crl.reset()
    self.assertFalse(crl.isChanged())

  def test_ignored_added_removed_elements(self):
    crl = ChangeTrackingList(['a', 'b', 'c'])
    crl.append('d')
    crl.remove('d')
    self.assertFalse(crl.isChanged())

    crl = ChangeTrackingList(['a', 'b', 'c'])
    crl.remove('b')
    crl.append('b')
    self.assertFalse(crl.isChanged())
