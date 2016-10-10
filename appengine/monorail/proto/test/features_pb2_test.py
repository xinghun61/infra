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
    self.assertEqual([], hotlist.iid_rank_pairs)

  def testMakeHotlist_Everything(self):
    hotlist = features_pb2.MakeHotlist(
        'summer-issues', [(1000, 1), (1001, 2), (1009, None)],
        description='desc')
    self.assertEqual('summer-issues', hotlist.name)
    self.assertEqual(
        [features_pb2.MakeHotlistIssue(1000, rank=1),
         features_pb2.MakeHotlistIssue(1001, rank=2),
         features_pb2.MakeHotlistIssue(1009),
         ],
        hotlist.iid_rank_pairs)
    self.assertEqual('desc', hotlist.description)

  def testMakeHotlistIssue(self):
    pair_1 = features_pb2.MakeHotlistIssue(1000, rank=1)
    self.assertEqual(1000, pair_1.issue_id)
    self.assertEqual(1, pair_1.rank)

    pair_2 = features_pb2.MakeHotlistIssue(1001)
    self.assertEqual(1001, pair_2.issue_id)
    self.assertEqual(None, pair_2.rank)
