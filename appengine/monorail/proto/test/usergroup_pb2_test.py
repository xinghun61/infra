# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for usergroup_pb2 functions."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import usergroup_pb2


class UserGroupPb2Test(unittest.TestCase):

  def testMakeSettings_Defaults(self):
    usergroup = usergroup_pb2.MakeSettings('anyone')
    self.assertEqual(
        usergroup_pb2.MemberVisibility.ANYONE,
        usergroup.who_can_view_members)
    self.assertIsNone(usergroup.ext_group_type)
    self.assertEqual(0, usergroup.last_sync_time)
    self.assertEqual([], usergroup.friend_projects)

  def testMakeSettings_Everything(self):
    usergroup = usergroup_pb2.MakeSettings(
        'Members', ext_group_type_str='mdb',
        last_sync_time=1234567890, friend_projects=[789])
    self.assertEqual(
        usergroup_pb2.MemberVisibility.MEMBERS,
        usergroup.who_can_view_members)
    self.assertEqual(usergroup_pb2.GroupType.MDB, usergroup.ext_group_type)
    self.assertEqual(1234567890, usergroup.last_sync_time)
    self.assertEqual([789], usergroup.friend_projects)
