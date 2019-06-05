# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.tracker.rerank_helpers."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from tracker import rerank_helpers


rerank_helpers.MAX_RANKING = 10


class Rerank_HelpersTest(unittest.TestCase):

  def testGetInsertRankings(self):
    lower = [(1, 0)]
    higher = [(2, 10)]
    moved_ids = [3]
    ret = rerank_helpers.GetInsertRankings(lower, higher, moved_ids)
    self.assertEqual(ret, [(3, 5)])

  def testGetInsertRankings_Below(self):
    lower = []
    higher = [(1, 2)]
    moved_ids = [2]
    ret = rerank_helpers.GetInsertRankings(lower, higher, moved_ids)
    self.assertEqual(ret, [(2, 1)])

  def testGetInsertRankings_Above(self):
    lower = [(1, 0)]
    higher = []
    moved_ids = [2]
    ret = rerank_helpers.GetInsertRankings(lower, higher, moved_ids)
    self.assertEqual(ret, [(2, 5)])

  def testGetInsertRankings_Multiple(self):
    lower = [(1, 0)]
    higher = [(2, 10)]
    moved_ids = [3,4,5]
    ret = rerank_helpers.GetInsertRankings(lower, higher, moved_ids)
    self.assertEqual(ret, [(3, 2), (4, 5), (5, 8)])

  def testGetInsertRankings_SplitLow(self):
    lower = [(1, 0), (2, 5)]
    higher = [(3, 6), (4, 10)]
    moved_ids = [5]
    ret = rerank_helpers.GetInsertRankings(lower, higher, moved_ids)
    self.assertEqual(ret, [(2, 2), (5, 5)])

  def testGetInsertRankings_SplitHigh(self):
    lower = [(1, 0), (2, 4)]
    higher = [(3, 5), (4, 10)]
    moved_ids = [5]
    ret = rerank_helpers.GetInsertRankings(lower, higher, moved_ids)
    self.assertEqual(ret, [(5, 6), (3, 9)])

  def testGetInsertRankings_NoLower(self):
    lower = []
    higher = [(1, 1)]
    moved_ids = [2]
    ret = rerank_helpers.GetInsertRankings(lower, higher, moved_ids)
    self.assertEqual(ret, [(2, 3), (1, 8)])

  def testGetInsertRankings_NoRoom(self):
    max_ranking, rerank_helpers.MAX_RANKING = rerank_helpers.MAX_RANKING, 1
    lower = [(1, 0)]
    higher = [(2, 1)]
    moved_ids = [3]
    ret = rerank_helpers.GetInsertRankings(lower, higher, moved_ids)
    self.assertIsNone(ret)
    rerank_helpers.MAX_RANKING = max_ranking
