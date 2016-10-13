# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for features bizobj functions."""

import unittest

from proto import features_pb2
from features import features_bizobj


class FeaturesBizobjTest(unittest.TestCase):

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
