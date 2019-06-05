# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for features bizobj functions."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import features_pb2
from features import features_bizobj
from testing import fake

class FeaturesBizobjTest(unittest.TestCase):

  def setUp(self):
    self.local_ids = [1L, 2L, 3L, 4L, 5L]
    self.issues = [fake.MakeTestIssue(1000, local_id, '', 'New', 111)
                   for local_id in self.local_ids]
    self.hotlistitems = [features_pb2.MakeHotlistItem(
        issue.issue_id, rank=rank*10, adder_id=111, date_added=3) for
                           rank, issue in enumerate(self.issues)]
    self.iids = [item.issue_id for item in self.hotlistitems]

  def testIssueIsInHotlist(self):
    hotlist = features_pb2.Hotlist(items=self.hotlistitems)
    for issue in self.issues:
      self.assertTrue(features_bizobj.IssueIsInHotlist(hotlist, issue.issue_id))

    self.assertFalse(features_bizobj.IssueIsInHotlist(
        hotlist, fake.MakeTestIssue(1000, 9L, '', 'New', 111)))

  def testSplitHotlistIssueRanks(self):
    iid_rank_tuples = [(issue.issue_id, issue.rank)
                       for issue in self.hotlistitems]
    iid_rank_tuples.reverse()
    ret = features_bizobj.SplitHotlistIssueRanks(
        100003, False, iid_rank_tuples)
    self.assertEqual(ret, (iid_rank_tuples[:2], iid_rank_tuples[2:]))

    iid_rank_tuples.reverse()
    ret = features_bizobj.SplitHotlistIssueRanks(
        100003, True, iid_rank_tuples)
    self.assertEqual(ret, (iid_rank_tuples[:3], iid_rank_tuples[3:]))

    # target issue not found
    first_pairs, second_pairs = features_bizobj.SplitHotlistIssueRanks(
        100009, True, iid_rank_tuples)
    self.assertEqual(iid_rank_tuples, first_pairs)
    self.assertEqual(second_pairs, [])

  def testGetOwnerIds(self):
    hotlist = features_pb2.Hotlist(owner_ids=[111])
    self.assertEqual(features_bizobj.GetOwnerIds(hotlist), [111])

  def testUsersOwnersOfHotlists_Empty(self):
    self.assertEqual(set(), features_bizobj.UsersOwnersOfHotlists([]))

  def testUsersOwnersOfHotlists_Normal(self):
    hotlist1 = features_pb2.Hotlist(
        owner_ids=[111, 222], editor_ids=[333, 444, 555],
        follower_ids=[123])
    hotlist2 = features_pb2.Hotlist(
        owner_ids=[111], editor_ids=[222, 123])
    self.assertEqual(set([111, 222]),
                     features_bizobj.UsersOwnersOfHotlists([hotlist1,
                                                            hotlist2]))

  def testUsersInvolvedInHotlists_Empty(self):
    self.assertEqual(set(), features_bizobj.UsersInvolvedInHotlists([]))

  def testUsersInvolvedInHotlists_Normal(self):
    hotlist1 = features_pb2.Hotlist(
        owner_ids=[111, 222], editor_ids=[333, 444, 555],
        follower_ids=[123])
    hotlist2 = features_pb2.Hotlist(
        owner_ids=[111], editor_ids=[222, 123])
    self.assertEqual(set([111, 222, 333, 444, 555, 123]),
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
        self.issues[2], self.iids)
    self.assertEqual(prev_iid, self.hotlistitems[1].issue_id)
    self.assertEqual(index, 2)
    self.assertEqual(next_iid, self.hotlistitems[3].issue_id)

    # end of list
    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[4], self.iids)
    self.assertEqual(prev_iid, self.hotlistitems[3].issue_id)
    self.assertEqual(index, 4)
    self.assertEqual(next_iid, None)

    # beginning of list
    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[0], self.iids)
    self.assertEqual(prev_iid, None)
    self.assertEqual(index, 0)
    self.assertEqual(next_iid, self.hotlistitems[1].issue_id)

    # one item in list
    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[2], [self.iids[2]])
    self.assertEqual(prev_iid, None)
    self.assertEqual(index, 0)
    self.assertEqual(next_iid, None)

    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[2], [self.iids[3]])
    self.assertEqual(prev_iid, None)
    self.assertEqual(index, None)
    self.assertEqual(next_iid, None)

    #none
    prev_iid, index, next_iid = features_bizobj.DetermineHotlistIssuePosition(
        self.issues[2], [])
    self.assertEqual(prev_iid, None)
    self.assertEqual(index, None)
    self.assertEqual(next_iid, None)
