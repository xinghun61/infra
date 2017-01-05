# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for Hotlist People servlet."""

import unittest

from third_party import ezt

from testing import fake
from features import hotlistpeople
from framework import permissions
from services import service_manager
from testing import testing_helpers

class HotlistPeopleListTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(), features=fake.FeaturesService())
    self.owner_user = self.services.user.TestAddUser('buzbuz@gmail.com', 111L)
    self.editor_user = self.services.user.TestAddUser('monica@gmail.com', 222L)
    self.non_member_user = self.services.user.TestAddUser(
        'who-dis@gmail.com', 333L)
    self.private_hotlist = self.services.features.TestAddHotlist(
        'private_hotlist', 'owner only', [111L], [222L], is_private=True)
    self.public_hotlist = self.services.features.TestAddHotlist(
        'public_hotlist', 'everyone', [111L], [222L], is_private=False)
    self.servlet = hotlistpeople.HotlistPeopleList(
        'req', 'res', services=self.services)

  def testAssertBasePermission(self):
    # owner can view people in private hotlist
    mr = testing_helpers.MakeMonorailRequest(hotlist=self.private_hotlist)
    mr.auth.effective_ids = {111L, 444L}
    self.servlet.AssertBasePermission(mr)

    # editor can view people in private hotlist
    mr.auth.effective_ids = {222, 333L}
    self.servlet.AssertBasePermission(mr)

    # non-members cannot view people in private hotlist
    mr.auth.effective_ids = {444L, 333L}
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    # owner can view people in public hotlist
    mr = testing_helpers.MakeMonorailRequest(hotlist=self.public_hotlist)
    mr.auth.effective_ids = {111L, 444L}
    self.servlet.AssertBasePermission(mr)

    # editor can view people in public hotlist
    mr.auth.effective_ids = {222, 333L}
    self.servlet.AssertBasePermission(mr)

    # non-members cannot view people in public hotlist
    mr.auth.effective_ids = {444L, 333L}
    self.servlet.AssertBasePermission(mr)

  def testGatherPageData(self):
    mr = testing_helpers.MakeMonorailRequest(hotlist=self.public_hotlist)
    mr.auth.effective_ids = {111L}
    mr.cnxn = 'fake cnxn'
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(ezt.boolean(True), page_data['offer_membership_editing'])
    self.assertEqual(page_data['total_num_owners'], 1)
    self.assertEqual(page_data['newly_added_views'], [])
    self.assertEqual(len(page_data['pagination'].visible_results), 2)

    # non-owners cannot edit people list
    mr.auth.effective_ids = {222L}
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(ezt.boolean(False), page_data['offer_membership_editing'])

    mr.auth.effective_ids = {333L}
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(ezt.boolean(False), page_data['offer_membership_editing'])

  def testProcessFormData_Permission(self):
    """Only owner can change member of hotlist."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/buzbuz@gmail.com/hotlists/people',
        hotlist=self.private_hotlist,
        )
    mr.auth.effective_ids = {111L, 444L}
    self.servlet.ProcessFormData(mr, {})

    mr.auth.effective_ids = {222L, 444L}
    self.assertRaises(permissions.PermissionException,
                      self.servlet.ProcessFormData, mr, {})


  def testProcessRemoveMembers(self):
    # TODO(jojwang): Write this test
    pass

  def testProcessAddMembers(self):
    # TODO(jojwang): Write this test
    pass

  def testProcessChangeOwnership(self):
    # TODO(jojwang): Write this test
    pass
