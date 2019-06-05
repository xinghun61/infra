# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit test for User Group helpers."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import user_pb2
from proto import usergroup_pb2
from sitewide import group_helpers


class GroupHelpersTest(unittest.TestCase):

  def testGroupVisibilityView(self):
    gvv_anyone = group_helpers.GroupVisibilityView(
        usergroup_pb2.MemberVisibility.ANYONE)
    gvv_members = group_helpers.GroupVisibilityView(
        usergroup_pb2.MemberVisibility.MEMBERS)
    gvv_owners = group_helpers.GroupVisibilityView(
        usergroup_pb2.MemberVisibility.OWNERS)
    self.assertEqual('Anyone on the Internet', gvv_anyone.name)
    self.assertEqual('Group Members', gvv_members.name)
    self.assertEqual('Group Owners', gvv_owners.name)

  def testGroupMemberView(self):
    user = user_pb2.MakeUser(1L, email='test@example.com')
    gmv = group_helpers.GroupMemberView(user, 888, 'member')
    self.assertEqual(888, gmv.group_id)
    self.assertEqual('member', gmv.role)

  def testBuildUserGroupVisibilityOptions(self):
    vis_views = group_helpers.BuildUserGroupVisibilityOptions()
    self.assertEqual(3, len(vis_views))

  def testGroupTypeView(self):
    gt_cia = group_helpers.GroupTypeView(
        usergroup_pb2.GroupType.CHROME_INFRA_AUTH)
    gt_mdb = group_helpers.GroupTypeView(
        usergroup_pb2.GroupType.MDB)
    self.assertEqual('Chrome-infra-auth', gt_cia.name)
    self.assertEqual('MDB', gt_mdb.name)

  def testBuildUserGroupTypeOptions(self):
    group_types = group_helpers.BuildUserGroupTypeOptions()
    self.assertEqual(4, len(group_types))
