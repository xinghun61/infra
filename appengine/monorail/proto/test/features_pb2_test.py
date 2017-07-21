# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for features_pb2 functions."""

import unittest

from proto import features_pb2


class FeaturesPb2Test(unittest.TestCase):

  def testMakeHotlist_Defaults(self):
    hotlist = features_pb2.MakeHotlist('summer-issues')
    self.assertEqual('summer-issues', hotlist.name)
    self.assertEqual([], hotlist.items)

  def testMakeHotlist_Everything(self):
    ts = 20011111111111
    hotlist = features_pb2.MakeHotlist(
        'summer-issues', [(1000, 1, 444L, ts, ''), (1001, 2, 333L, ts, ''),
                          (1009, None, None, ts, '')],
        description='desc')
    self.assertEqual('summer-issues', hotlist.name)
    self.assertEqual(
        [features_pb2.MakeHotlistItem(
            1000, rank=1, adder_id=444L, date_added=ts, note=''),
         features_pb2.MakeHotlistItem(
             1001, rank=2, adder_id=333L, date_added=ts, note=''),
         features_pb2.MakeHotlistItem(1009, date_added=ts, note=''),
         ],
        hotlist.items)
    self.assertEqual('desc', hotlist.description)

  def testMakeHotlistItem(self):
    ts = 20011111111111
    item_1 = features_pb2.MakeHotlistItem(
        1000, rank=1, adder_id=111L, date_added=ts, note='short note')
    self.assertEqual(1000, item_1.issue_id)
    self.assertEqual(1, item_1.rank)
    self.assertEqual(111L, item_1.adder_id)
    self.assertEqual(ts, item_1.date_added)
    self.assertEqual('short note', item_1.note)

    item_2 = features_pb2.MakeHotlistItem(1001)
    self.assertEqual(1001, item_2.issue_id)
    self.assertEqual(None, item_2.rank)
    self.assertEqual(None, item_2.adder_id)
    self.assertEqual('', item_2.note)
    self.assertEqual(features_pb2.ADDED_TS_FEATURE_LAUNCH_TS, item_2.date_added)
