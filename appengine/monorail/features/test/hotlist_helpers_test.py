# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for helpers module."""

import unittest

from features import hotlist_helpers
from proto import features_pb2

class HelpersUnitTest(unittest.TestCase):

  def testMembersWithoutGivenIDs(self):
    h = features_pb2.Hotlist()
    owners, editors, followers = hotlist_helpers.MembersWithoutGivenIDs(
        h, set())
    # Check lists are empty
    self.assertFalse(owners)
    self.assertFalse(editors)
    self.assertFalse(followers)

    h.owner_ids.extend([1, 2, 3])
    h.editor_ids.extend([4, 5, 6])
    h.follower_ids.extend([7, 8, 9])
    owners, editors, followers = hotlist_helpers.MembersWithoutGivenIDs(
        h, {10, 11, 12})
    self.assertEqual(h.owner_ids, owners)
    self.assertEqual(h.editor_ids, editors)
    self.assertEqual(h.follower_ids, followers)

    owners, editors, followers = hotlist_helpers.MembersWithoutGivenIDs(
        h, set())
    self.assertEqual(h.owner_ids, owners)
    self.assertEqual(h.editor_ids, editors)
    self.assertEqual(h.follower_ids, followers)

    owners, editors, followers = hotlist_helpers.MembersWithoutGivenIDs(
        h, {1, 4, 7})
    self.assertEqual([2, 3], owners)
    self.assertEqual([5, 6], editors)
    self.assertEqual([8, 9], followers)

  def testMembersWithGivenIDs(self):
    h = features_pb2.Hotlist()

    # empty GivenIDs give empty member lists from originally empty member lists
    owners, editors, followers = hotlist_helpers.MembersWithGivenIDs(
        h, set(), 'follower')
    self.assertFalse(owners)
    self.assertFalse(editors)
    self.assertFalse(followers)

    # empty GivenIDs return original non-empty member lists
    h.owner_ids.extend([1, 2, 3])
    h.editor_ids.extend([4, 5, 6])
    h.follower_ids.extend([7, 8, 9])
    owners, editors, followers = hotlist_helpers.MembersWithGivenIDs(
        h, set(), 'editor')
    self.assertEqual(owners, h.owner_ids)
    self.assertEqual(editors, h.editor_ids)
    self.assertEqual(followers, h.follower_ids)

    # non-member GivenIDs return updated member lists
    owners, editors, followers = hotlist_helpers.MembersWithGivenIDs(
        h, {10, 11, 12}, 'owner')
    self.assertEqual(owners, [1, 2, 3, 10, 11, 12])
    self.assertEqual(editors, [4, 5, 6])
    self.assertEqual(followers, [7, 8, 9])

    # member GivenIDs return updated member lists
    owners, editors, followers = hotlist_helpers.MembersWithGivenIDs(
        h, {1, 4, 7}, 'editor')
    self.assertEqual(owners, [2, 3])
    self.assertEqual(editors, [5, 6, 1, 4, 7])
    self.assertEqual(followers, [8, 9])
