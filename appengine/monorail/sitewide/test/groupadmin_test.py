# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit test for User Group admin servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import permissions
from proto import usergroup_pb2
from services import service_manager
from sitewide import groupadmin
from testing import fake
from testing import testing_helpers


class GrouAdminTest(unittest.TestCase):
  """Tests for the GroupAdmin servlet."""

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService())
    self.services.user.TestAddUser('a@example.com', 111)
    self.services.user.TestAddUser('b@example.com', 222)
    self.services.user.TestAddUser('c@example.com', 333)
    self.services.user.TestAddUser('group@example.com', 888)
    self.services.user.TestAddUser('importgroup@example.com', 999)
    self.services.usergroup.TestAddGroupSettings(888, 'group@example.com')
    self.services.usergroup.TestAddGroupSettings(
        999, 'importgroup@example.com', external_group_type='mdb')
    self.servlet = groupadmin.GroupAdmin(
        'req', 'res', services=self.services)
    self.mr = testing_helpers.MakeMonorailRequest()
    self.mr.viewed_username = 'group@example.com'
    self.mr.viewed_user_auth.user_id = 888

  def testAssertBasePermission(self):
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.GetPermissions(None, {}, None))
    mr.viewed_user_auth.user_id = 888
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, mr)
    self.services.usergroup.TestAddMembers(888, [111], 'owner')
    self.servlet.AssertBasePermission(self.mr)

  def testGatherPageData_Normal(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual('group@example.com', page_data['groupname'])
    self.assertEqual('Group Members', page_data['initial_visibility'].name)
    self.assertEqual(3, len(page_data['visibility_levels']))

  def testGatherPageData_Import(self):
    mr = testing_helpers.MakeMonorailRequest()
    mr.viewed_username = 'importgroup@example.com'
    mr.viewed_user_auth.user_id = 999
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual('importgroup@example.com', page_data['groupname'])
    self.assertTrue(page_data['import_group'])
    self.assertEqual('MDB', page_data['initial_group_type'].name)

  def testProcessFormData_Normal(self):
    post_data = fake.PostData(visibility='0')
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertIn('/g/group@example.com/groupadmin', url)
    group_settings = self.services.usergroup.GetGroupSettings(None, 888)
    self.assertEqual(usergroup_pb2.MemberVisibility.OWNERS,
                     group_settings.who_can_view_members)

  def testProcessFormData_Import(self):
    post_data = fake.PostData(
        group_type='1', import_group=['on'])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertIn('/g/group@example.com/groupadmin', url)
    group_settings = self.services.usergroup.GetGroupSettings(None, 888)
    self.assertEqual(usergroup_pb2.MemberVisibility.OWNERS,
                     group_settings.who_can_view_members)
    self.assertEqual(usergroup_pb2.GroupType.MDB,
                     group_settings.ext_group_type)
