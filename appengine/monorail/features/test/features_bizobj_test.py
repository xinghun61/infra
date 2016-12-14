# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for features bizobj functions."""

import unittest

from proto import features_pb2
from features import features_bizobj
from testing import fake

class FeaturesBizobjTest(unittest.TestCase):

  def setUp(self):
    self.local_ids = [1L, 2L, 3L, 4L, 5L]
    self.issues = [fake.MakeTestIssue(1000, local_id, '', 'New', 111L)
                   for local_id in self.local_ids]
    self.iid_rank_pairs = [features_pb2.MakeHotlistIssue(
        issue.issue_id, rank=rank*10) for rank, issue in enumerate(self.issues)]
    self.iid_rank_tuples = [(pair.issue_id, pair.rank) for pair
                            in self.iid_rank_pairs]

  def testIssueIsInHotlist(self):
    hotlist = features_pb2.Hotlist(iid_rank_pairs=self.iid_rank_pairs)
    for issue in self.issues:
      self.assertTrue(features_bizobj.IssueIsInHotlist(hotlist, issue.issue_id))

    self.assertFalse(features_bizobj.IssueIsInHotlist(
        hotlist, fake.MakeTestIssue(1000, 9L, '', 'New', 111L)))

  def testSplitHotlistIssueRanks(self):
    iid_rank_tuples = [(issue.issue_id, issue.rank)
                       for issue in self.iid_rank_pairs]
    iid_rank_tuples.reverse()
    ret = features_bizobj.SplitHotlistIssueRanks(
        100003L, False, iid_rank_tuples)
    self.assertEqual(ret, (iid_rank_tuples[:2], iid_rank_tuples[2:]))

    iid_rank_tuples.reverse()
    ret = features_bizobj.SplitHotlistIssueRanks(
        100003L, True, iid_rank_tuples)
    self.assertEqual(ret, (iid_rank_tuples[:3], iid_rank_tuples[3:]))

    # target issue not found
    first_pairs, second_pairs = features_bizobj.SplitHotlistIssueRanks(
        100009L, True, iid_rank_tuples)
    self.assertEqual(iid_rank_tuples, first_pairs)
    self.assertEqual(second_pairs, [])

  def testUsersInvolvedInHotlists_Empty(self):
    self.assertEqual(set(), features_bizobj.UsersInvolvedInHotlists([]))

  def testUsersInvolvedInHotlists_Normal(self):
    hotlist1 = features_pb2.Hotlist(
        owner_ids=[111L, 222L], editor_ids=[333L, 444L, 555L],
        follower_ids=[123L])
    hotlist2 = features_pb2.Hotlist(
        owner_ids=[111L], editor_ids=[222L, 123L])
    self.assertEqual(set([111L, 222L, 333L, 444L, 555L, 123L]),
                     features_bizobj.UsersInvolvedInHotlists([hotlist1,
                                                              hotlist2]))

  def testUserIsInHotlist(self):
    h = features_pb2.Hotlist()
    self.assertFalse(features_bizobj.UserIsInHotlist(h, {9}))
    self.assertFalse(features_bizobj.UserIsInHotlist(h, set()))

    h.owner_ids.extend([1, 2, 3])
    h.editor_ids.extend([4, 5, 6])
    h.follower_ids.extend([7, 8, 9])
    self.assertTrue(features_bizobj.UserIsInHotlist(h, {1}))
    self.assertTrue(features_bizobj.UserIsInHotlist(h, {4}))
    self.assertTrue(features_bizobj.UserIsInHotlist(h, {7}))
    self.assertFalse(features_bizobj.UserIsInHotlist(h, {10}))

    # Membership via group membership
    self.assertTrue(features_bizobj.UserIsInHotlist(h, {10, 4}))

    # Membership via several group memberships
    self.assertTrue(features_bizobj.UserIsInHotlist(h, {1, 4}))

    # Several irrelevant group memberships
    self.assertFalse(features_bizobj.UserIsInHotlist(h, {10, 11, 12}))

  def testDetermineHotlistIssuePosition(self):
    # normal
    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[2], self.iid_rank_tuples)
    self.assertEqual(prev_iid, self.iid_rank_pairs[1].issue_id)
    self.assertEqual(index, 2)
    self.assertEqual(next_iid, self.iid_rank_pairs[3].issue_id)

    # end of list
    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[4], self.iid_rank_tuples)
    self.assertEqual(prev_iid, self.iid_rank_pairs[3].issue_id)
    self.assertEqual(index, 4)
    self.assertEqual(next_iid, None)

    # beginning of list
    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[0], self.iid_rank_tuples)
    self.assertEqual(prev_iid, None)
    self.assertEqual(index, 0)
    self.assertEqual(next_iid, self.iid_rank_pairs[1].issue_id)

    # one item in list
    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[2], [self.iid_rank_tuples[2]])
    self.assertEqual(prev_iid, None)
    self.assertEqual(index, 0)
    self.assertEqual(next_iid, None)

    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[2], [self.iid_rank_tuples[3]])
    self.assertEqual(prev_iid, None)
    self.assertEqual(index, None)
    self.assertEqual(next_iid, None)

    #none
    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[2], [])
    self.assertEqual(prev_iid, None)
    self.assertEqual(index, None)
    self.assertEqual(next_iid, None)
