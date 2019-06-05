# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit test for User Group creation servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

import settings
from framework import permissions
from proto import site_pb2
from proto import usergroup_pb2
from services import service_manager
from sitewide import groupcreate
from testing import fake
from testing import testing_helpers


class GroupCreateTest(unittest.TestCase):
  """Tests for the GroupCreate servlet."""

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService())
    self.servlet = groupcreate.GroupCreate(
        'req', 'res', services=self.services)
    self.mr = testing_helpers.MakeMonorailRequest()

  def CheckAssertBasePermissions(
      self, restriction, expect_admin_ok, expect_nonadmin_ok):
    old_group_creation_restriction = settings.group_creation_restriction
    settings.group_creation_restriction = restriction

    # Anon users can never do it
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.GetPermissions(None, {}, None))
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, mr)

    mr = testing_helpers.MakeMonorailRequest()
    if expect_admin_ok:
      self.servlet.AssertBasePermission(mr)
    else:
      self.assertRaises(
          permissions.PermissionException,
          self.servlet.AssertBasePermission, mr)

    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.GetPermissions(mr.auth.user_pb, {111}, None))
    if expect_nonadmin_ok:
      self.servlet.AssertBasePermission(mr)
    else:
      self.assertRaises(
          permissions.PermissionException,
          self.servlet.AssertBasePermission, mr)

    settings.group_creation_restriction = old_group_creation_restriction

  def testAssertBasePermission(self):
    self.CheckAssertBasePermissions(
        site_pb2.UserTypeRestriction.ANYONE, True, True)
    self.CheckAssertBasePermissions(
        site_pb2.UserTypeRestriction.ADMIN_ONLY, True, False)
    self.CheckAssertBasePermissions(
        site_pb2.UserTypeRestriction.NO_ONE, False, False)

  def testGatherPageData(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual('', page_data['initial_name'])

  def testProcessFormData_Normal(self):
    post_data = fake.PostData(
        groupname=['group@example.com'], visibility='1')
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertIn('/g/3444127190/', url)
    group_id = self.services.user.LookupUserID('cnxn', 'group@example.com')
    group_settings = self.services.usergroup.GetGroupSettings('cnxn', group_id)
    self.assertIsNotNone(group_settings)
    members_after, owners_after = self.services.usergroup.LookupMembers(
        'cnxn', [group_id])
    self.assertEqual(0, len(members_after[group_id] + owners_after[group_id]))

  def testProcessFormData_Import(self):
    post_data = fake.PostData(
        groupname=['group@example.com'], group_type='1',
        import_group=['on'])
    self.servlet.ProcessFormData(self.mr, post_data)
    group_id = self.services.user.LookupUserID('cnxn', 'group@example.com')
    group_settings = self.services.usergroup.GetGroupSettings('cnxn', group_id)
    self.assertIsNotNone(group_settings)
    self.assertEqual(usergroup_pb2.MemberVisibility.OWNERS,
                     group_settings.who_can_view_members)
    self.assertEqual(usergroup_pb2.GroupType.MDB,
                     group_settings.ext_group_type)
