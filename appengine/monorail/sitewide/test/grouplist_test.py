# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit test for User Group List servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from google.appengine.ext import testbed

from framework import permissions
from services import service_manager
from sitewide import grouplist
from testing import fake
from testing import testing_helpers


class GroupListTest(unittest.TestCase):
  """Tests for the GroupList servlet."""

  def setUp(self):
    self.services = service_manager.Services(
        usergroup=fake.UserGroupService())
    self.servlet = grouplist.GroupList('req', 'res', services=self.services)
    self.mr = testing_helpers.MakeMonorailRequest()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

  def testAssertBasePermission_Anon(self):
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    with self.assertRaises(permissions.PermissionException):
      self.servlet.AssertBasePermission(self.mr)

  def testAssertBasePermission_RegularUsers(self):
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    with self.assertRaises(permissions.PermissionException):
      self.servlet.AssertBasePermission(self.mr)

  def testAssertBasePermission_SiteAdmin(self):
    self.mr.perms = permissions.ADMIN_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

  def testGatherPagData_ZeroGroups(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual([], page_data['groups'])

  def testGatherPagData_NonzeroGroups(self):
    self.services.usergroup.TestAddGroupSettings(777, 'group_a@example.com')
    self.services.usergroup.TestAddGroupSettings(888, 'group_b@example.com')
    self.services.usergroup.TestAddMembers(888, [111, 222, 333])
    page_data = self.servlet.GatherPageData(self.mr)
    group_view_a, group_view_b = page_data['groups']
    self.assertEqual('group_a@example.com', group_view_a.name)
    self.assertEqual(0, group_view_a.num_members)
    self.assertEqual('group_b@example.com', group_view_b.name)
    self.assertEqual(3, group_view_b.num_members)

  def testProcessFormData_NoPermission(self):
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.USER_PERMISSIONSET)
    post_data = fake.PostData(
      removebtn=[1])
    self.assertRaises(permissions.PermissionException,
                      self.servlet.ProcessFormData, mr, post_data)

  def testProcessFormData_Normal(self):
    self.services.usergroup.TestAddGroupSettings(
        888, 'group_b@example.com', friend_projects=[789])
    self.services.usergroup.TestAddMembers(888, [111, 222, 333])

    post_data = fake.PostData(
        remove=[888],
        removebtn=[1])
    self.servlet.ProcessFormData(self.mr, post_data)
    self.assertNotIn(888, self.services.usergroup.group_settings)
