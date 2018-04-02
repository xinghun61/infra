# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit test for User Group Detail servlet."""

import unittest

from framework import exceptions
from framework import permissions
from services import service_manager
from sitewide import groupdetail
from testing import fake
from testing import testing_helpers


class GroupDetailTest(unittest.TestCase):
  """Tests for the GroupDetail servlet."""

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.services.user.TestAddUser('a@example.com', 111L)
    self.services.user.TestAddUser('b@example.com', 222L)
    self.services.user.TestAddUser('c@example.com', 333L)
    self.services.user.TestAddUser('group@example.com', 888L)
    self.services.usergroup.TestAddGroupSettings(888L, 'group@example.com')
    self.servlet = groupdetail.GroupDetail(
        'req', 'res', services=self.services)
    self.mr = testing_helpers.MakeMonorailRequest()
    self.mr.viewed_username = 'group@example.com'
    self.mr.viewed_user_auth.user_id = 888L

  def testAssertBasePermission(self):
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.GetPermissions(None, {}, None))
    mr.viewed_user_auth.user_id = 888L
    mr.auth.effective_ids = set([111L])
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, mr)
    self.services.usergroup.TestAddMembers(888L, [111L], 'member')
    self.servlet.AssertBasePermission(mr)

  def testAssertBasePermission_IgnoreNoSuchGroup(self):
    """The permission check does not crash for non-existent user groups."""
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.GetPermissions(None, {}, None))
    mr.viewed_user_auth.user_id = 404L
    mr.auth.effective_ids = set([111L])
    self.servlet.AssertBasePermission(mr)

  def testAssertBasePermission_IndirectMembership(self):
    self.services.usergroup.TestAddGroupSettings(999L, 'subgroup@example.com')
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.GetPermissions(None, {}, None))
    mr.viewed_user_auth.user_id = 888L
    mr.auth.effective_ids = set([111L])
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, mr)
    self.services.usergroup.TestAddMembers(888L, [999L], 'member')
    self.services.usergroup.TestAddMembers(999L, [111L], 'member')
    self.servlet.AssertBasePermission(mr)

  def testGatherPagData_ZeroMembers(self):
    page_data = self.servlet.GatherPageData(self.mr)
    pagination = page_data['pagination']
    self.assertEqual(0, len(pagination.visible_results))

  def testGatherPagData_NonzeroMembers(self):
    self.services.usergroup.TestAddMembers(888L, [111L, 222L, 333L])
    page_data = self.servlet.GatherPageData(self.mr)
    pagination = page_data['pagination']
    self.assertEqual(3, len(pagination.visible_results))
    self.assertEqual(3, pagination.total_count)
    self.assertEqual(1, pagination.start)
    self.assertEqual(3, pagination.last)
    user_view_a, user_view_b, user_view_c = pagination.visible_results
    self.assertEqual('a@example.com', user_view_a.email)
    self.assertEqual('b@example.com', user_view_b.email)
    self.assertEqual('c@example.com', user_view_c.email)

  def testProcessAddMembers_NoneAdded(self):
    post_data = fake.PostData(addmembers=[''], role=['member'])
    url = self.servlet.ProcessAddMembers(self.mr, post_data)
    self.assertIn('/g/group@example.com/?', url)
    members_after, _ = self.services.usergroup.LookupMembers('cnxn', [888L])
    self.assertEqual(0, len(members_after[888L]))

    self.services.usergroup.TestAddMembers(888L, [111L, 222L, 333L])
    url = self.servlet.ProcessAddMembers(self.mr, post_data)
    self.assertIn('/g/group@example.com/?', url)
    members_after, _ = self.services.usergroup.LookupMembers('cnxn', [888L])
    self.assertEqual(3, len(members_after[888L]))

  def testProcessAddMembers_SomeAdded(self):
    self.services.usergroup.TestAddMembers(888L, [111L])
    post_data = fake.PostData(
        addmembers=['b@example.com, c@example.com'], role=['member'])
    url = self.servlet.ProcessAddMembers(self.mr, post_data)
    self.assertIn('/g/group@example.com/?', url)
    members_after, _ = self.services.usergroup.LookupMembers('cnxn', [888L])
    self.assertEqual(3, len(members_after[888L]))

  def testProcessRemoveMembers_SomeRemoved(self):
    self.services.usergroup.TestAddMembers(888L, [111L, 222L, 333L])
    post_data = fake.PostData(remove=['b@example.com', 'c@example.com'])
    url = self.servlet.ProcessRemoveMembers(self.mr, post_data)
    self.assertIn('/g/group@example.com/?', url)
    members_after, _ = self.services.usergroup.LookupMembers('cnxn', [888L])
    self.assertEqual(1, len(members_after[888L]))

  def testProcessFormData_NoPermission(self):
    """Group members cannot edit group."""
    self.services.usergroup.TestAddMembers(888L, [111L], 'member')
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.GetPermissions(None, {}, None))
    mr.viewed_user_auth.user_id = 888L
    mr.auth.effective_ids = set([111L])
    self.assertRaises(permissions.PermissionException,
                      self.servlet.ProcessFormData, mr, {})

  def testProcessFormData_OwnerPermission(self):
    """Group owners cannot edit group."""
    self.services.usergroup.TestAddMembers(888L, [111L], 'owner')
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.GetPermissions(None, {}, None))
    mr.viewed_user_auth.user_id = 888L
    mr.auth.effective_ids = set([111L])
    self.servlet.ProcessFormData(mr, {})

  def testGatherPagData_NoSuchUserGroup(self):
    """If there is no such user group, raise an exception."""
    self.mr.viewed_user_auth.user_id = 404L
    self.assertRaises(
        exceptions.NoSuchGroupException,
        self.servlet.GatherPageData, self.mr)


