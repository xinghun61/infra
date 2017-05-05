# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for hotlist_views classes."""

import unittest

from features import hotlist_views
from framework import monorailrequest
from framework import framework_views
from services import service_manager
from testing import fake
from proto import user_pb2


class MemberViewTest(unittest.TestCase):

  def setUp(self):
    self.hotlist = fake.Hotlist('hotlistName', 123,
                                hotlist_item_fields=[
                                    (2, 0, None, None, ''),
                                    (1, 0, None, None, ''),
                                    (5, 0, None, None, '')],
                                is_private=False, owner_ids=[111])
    self.user1 = user_pb2.User(user_id=111)
    self.user1_view = framework_views.UserView(self.user1)

  def testMemberViewCorrect(self):
    member_view = hotlist_views.MemberView(111, 111, self.user1_view,
                                           self.hotlist)
    self.assertEqual(member_view.user, self.user1_view)
    self.assertEqual(member_view.detail_url, '/u/111/')
    self.assertEqual(member_view.role, 'Owner')
    self.assertTrue(member_view.viewing_self)


class HotlistViewTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(user=fake.UserService(),
    usergroup=fake.UserGroupService())
    self.user1 = self.services.user.TestAddUser('user1', 111L)
    self.user1.obscure_email = True
    self.user1_view = framework_views.UserView(self.user1)
    self.user2 = self.services.user.TestAddUser('user2', 222L)
    self.user2.obscure_email = False
    self.user2_view = framework_views.UserView(self.user2)
    self.user3 = self.services.user.TestAddUser('user3', 333L)
    self.user3_view = framework_views.UserView(self.user3)
    self.user4 = self.services.user.TestAddUser('user4', 444L, banned=True)
    self.user4_view = framework_views.UserView(self.user4)

    self.user_auth = monorailrequest.AuthData.FromEmail(
        None, 'user3', self.services)
    self.user_auth.effective_ids = {3}
    self.user_auth.user_id = 3
    self.users_by_id = {1: self.user1_view, 2: self.user2_view,
        3: self.user3_view, 4: self.user4_view}

  def testNoOwner(self):
    hotlist = fake.Hotlist('unowned', 500, owner_ids=[])
    view = hotlist_views.HotlistView(hotlist, self.user_auth, 1,
                                             self.users_by_id)
    self.assertFalse(view.url)

  def testBanned(self):
    # With a banned user
    hotlist = fake.Hotlist('userBanned', 423, owner_ids=[4])
    hotlist_view = hotlist_views.HotlistView(hotlist, self.user_auth, 1,
                                             self.users_by_id)
    self.assertFalse(hotlist_view.visible)

    # With a user not banned
    hotlist = fake.Hotlist('userNotBanned', 453, owner_ids=[1])
    hotlist_view = hotlist_views.HotlistView(hotlist, self.user_auth, 1,
                                             self.users_by_id)
    self.assertTrue(hotlist_view.visible)

  def testNoPermissions(self):
    hotlist = fake.Hotlist(
        'private', 333, is_private=True, owner_ids=[1], editor_ids=[2])
    hotlist_view = hotlist_views.HotlistView(
        hotlist, self.user_auth, 1, self.users_by_id)
    self.assertFalse(hotlist_view.visible)
    self.assertEqual(hotlist_view.url, '/u/1/hotlists/private')

  def testFriendlyURL(self):
    # owner with obscure_email:false
    hotlist = fake.Hotlist(
        'noObscureHotlist', 133, owner_ids=[2], editor_ids=[3])
    hotlist_view = hotlist_views.HotlistView(
        hotlist, self.user_auth, viewed_user_id=3, users_by_id=self.users_by_id)
    self.assertEqual(hotlist_view.url, '/u/user2/hotlists/noObscureHotlist')

    #owner with obscure_email:true
    hotlist = fake.Hotlist('ObscureHotlist', 133, owner_ids=[1], editor_ids=[3])
    hotlist_view = hotlist_views.HotlistView(
        hotlist, self.user_auth, viewed_user_id=1, users_by_id=self.users_by_id)
    self.assertEqual(hotlist_view.url, '/u/1/hotlists/ObscureHotlist')

  def testOtherAttributes(self):
    hotlist = fake.Hotlist(
        'hotlistName', 123, hotlist_item_fields=[(2, 0, None, None, ''),
                                                (1, 0, None, None, ''),
                                                 (5, 0, None, None, '')],
                                is_private=False, owner_ids=[1],
                                editor_ids=[2, 3])
    hotlist_view = hotlist_views.HotlistView(
        hotlist, self.user_auth, viewed_user_id=2,
        users_by_id=self.users_by_id, is_starred=True)
    self.assertTrue(hotlist_view.visible, True)
    self.assertEqual(hotlist_view.role_name, 'editor')
    self.assertEqual(hotlist_view.owners, [self.user1_view])
    self.assertEqual(hotlist_view.editors, [self.user2_view, self.user3_view])
    self.assertEqual(hotlist_view.num_issues, 3)
    self.assertTrue(hotlist_view.is_starred)
