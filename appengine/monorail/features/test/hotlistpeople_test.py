# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for Hotlist People servlet."""

import mox
import unittest
import logging

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
        'PrivateHotlist', 'owner only', [111L], [222L], is_private=True)
    self.public_hotlist = self.services.features.TestAddHotlist(
        'PublicHotlist', 'everyone', [111L], [222L], is_private=False)
    self.servlet = hotlistpeople.HotlistPeopleList(
        'req', 'res', services=self.services)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

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
    mr.auth.user_id = 111L
    mr.auth.effective_ids = {111L}
    mr.cnxn = 'fake cnxn'
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(ezt.boolean(True), page_data['offer_membership_editing'])
    self.assertEqual(page_data['total_num_owners'], 1)
    self.assertEqual(page_data['newly_added_views'], [])
    self.assertEqual(len(page_data['pagination'].visible_results), 2)

    # non-owners cannot edit people list
    mr.auth.user_id = 222L
    mr.auth.effective_ids = {222L}
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(ezt.boolean(False), page_data['offer_membership_editing'])

    mr.auth.user_id = 333L
    mr.auth.effective_ids = {333L}
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(ezt.boolean(False), page_data['offer_membership_editing'])

  def testProcessFormData_Permission(self):
    """Only owner can change member of hotlist."""
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/buzbuz@gmail.com/hotlists/PrivateHotlist/people',
        hotlist=self.private_hotlist,
        )
    mr.auth.effective_ids = {111L, 444L}
    self.servlet.ProcessFormData(mr, {})

    mr.auth.effective_ids = {222L, 444L}
    self.assertRaises(permissions.PermissionException,
                      self.servlet.ProcessFormData, mr, {})


  def testProcessRemoveMembers(self):
    hotlist = self.servlet.services.features.TestAddHotlist(
        'HotlistName', 'removing 222, monica', [111L], [222L])
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/buzbuz@gmail.com/hotlists/HotlistName/people',
        hotlist=hotlist)
    mr.hotlist_id = hotlist.hotlist_id
    post_data = fake.PostData(
        remove = ['monica@gmail.com'])
    url = self.servlet.ProcessRemoveMembers(
        mr, post_data, '/u/111/hotlists/HotlistName')
    self.assertTrue('/u/111/hotlists/HotlistName/people' in url)
    self.assertEqual(hotlist.editor_ids, [])

  def testProcessAddMembers(self):
    hotlist = self.servlet.services.features.TestAddHotlist(
        'HotlistName', 'adding 333, who-dis', [111L], [222L])
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/buzbuz@gmail.com/hotlists/HotlistName/people',
        hotlist=hotlist)
    mr.hotlist_id = hotlist.hotlist_id
    post_data = fake.PostData(
        addmembers = ['who-dis@gmail.com'],
        role = ['editor'])
    url = self.servlet.ProcessAddMembers(
        mr, post_data, '/u/111/hotlists/HotlistName')
    self.assertTrue('/u/111/hotlists/HotlistName/people' in url)
    self.assertEqual(hotlist.editor_ids, [222L, 333L])

  def testProcessAddMembers_OwnerToEditor(self):
    hotlist = self.servlet.services.features.TestAddHotlist(
        'HotlistName', 'adding owner 111, buzbuz as editor', [111L], [222L])
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/buzbuz@gmail.com/hotlists/HotlistName/people',
        hotlist=hotlist)
    mr.hotlist_id = hotlist.hotlist_id
    addmembers_input = 'buzbuz@gmail.com'
    post_data = fake.PostData(
        addmembers = [addmembers_input],
        role = ['editor'])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, initial_add_members=addmembers_input, initially_expand_form=True)
    self.mox.ReplayAll()
    url = self.servlet.ProcessAddMembers(
        mr, post_data, '/u/111/hotlists/HotlistName')
    self.mox.VerifyAll()
    self.assertEqual(
        'Cannot have a hotlist without an owner; please leave at least one.',
        mr.errors.addmembers)
    self.assertIsNone(url)
    # Verify that no changes have actually occurred.
    self.assertEqual(hotlist.owner_ids, [111L])
    self.assertEqual(hotlist.editor_ids, [222L])

  def testProcessChangeOwnership(self):
    hotlist = self.servlet.services.features.TestAddHotlist(
        'HotlistName', 'new owner 333L, who-dis', [111L], [222L])
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/buzbuz@gmail.com/hotlists/HotlistName/people',
        hotlist=hotlist)
    mr.hotlist_id = hotlist.hotlist_id
    post_data = fake.PostData(
        changeowners = ['who-dis@gmail.com'],
        becomeeditor = ['on'])
    url = self.servlet.ProcessChangeOwnership(mr, post_data)
    self.assertTrue('/u/333/hotlists/HotlistName/people' in url)
    self.assertEqual(hotlist.owner_ids, [333L])
    self.assertEqual(hotlist.editor_ids, [222L, 111L])

  def testProcessChangeOwnership_UnownedHotlist(self):
    hotlist = self.services.features.TestAddHotlist(
        'unowned', 'new owner 333L, who-dis', [], [222L])
    mr = testing_helpers.MakeMonorailRequest(
        path='/whatever',
        hotlist=hotlist)
    mr.hotlist_id = hotlist.hotlist_id
    post_data = fake.PostData(
        changeowners = ['who-dis@gmail.com'],
        becomeeditor = ['on'])
    self.servlet.ProcessChangeOwnership(mr, post_data)
    self.assertEqual([333L], mr.hotlist.owner_ids)

  def testProcessChangeOwnership_BadEmail(self):
    hotlist = self.servlet.services.features.TestAddHotlist(
        'HotlistName', 'new owner 333L, who-dis', [111L], [222L])
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/buzbuz@gmail.com/hotlists/HotlistName/people',
        hotlist=hotlist)
    mr.hotlist_id = hotlist.hotlist_id
    changeowners_input = 'who-dis@gmail.com, extra-email@gmail.com'
    post_data = fake.PostData(
        changeowners = [changeowners_input],
        becomeeditor = ['on'])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, initial_new_owner_username=changeowners_input, open_dialog='yes')
    self.mox.ReplayAll()
    url = self.servlet.ProcessChangeOwnership(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual(
        'Please add one valid user email.', mr.errors.transfer_ownership)
    self.assertIsNone(url)

  def testProcessChangeOwnership_DuplicateName(self):
    # other_hotlist = self.servlet.services.features.TestAddHotlist(
    #    'HotlistName', 'hotlist with same name', [333L], [])
    # hotlist = self.servlet.services.features.TestAddHotlist(
    #     'HotlistName', 'new owner 333L, who-dis', [111L], [222L])

    # in the test_hotlists dict of features_service in testing/fake
    # 'other_hotlist' is overwritten by 'hotlist'
    # TODO(jojwang): edit the fake features_service to allow hotlists
    # with the same name but different owners
    pass
