# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the authdata module."""

import unittest
from framework import authdata
from services import service_manager
from testing import fake


class AuthDataTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.services.user.TestAddUser('test@example.com', 111L)

  # TODO(jrobbins): Fill in a bunch of missing tests here.

  def testFinishInitialization_NoMemberships(self):
    """No user groups means effective_ids == {user_id}."""
    auth = authdata.AuthData(user_id=111L, email='test@example.com')
    authdata.AuthData._FinishInitialization(
        self.cnxn, auth, self.services)
    self.assertEqual(auth.user_id, 111L)
    self.assertEqual(auth.effective_ids, {111L})

  def testFinishInitialization_NormalMemberships(self):
    """effective_ids should be {user_id, group_id...}."""
    self.services.usergroup.TestAddMembers(888L, [111L])
    self.services.usergroup.TestAddMembers(999L, [111L])
    auth = authdata.AuthData(user_id=111L, email='test@example.com')
    authdata.AuthData._FinishInitialization(
        self.cnxn, auth, self.services)
    self.assertEqual(auth.user_id, 111L)
    self.assertEqual(auth.effective_ids, {111L, 888L, 999L})

  def testFinishInitialization_ComputedUserGroup(self):
    """effective_ids should be {user_id, group_id...}."""
    self.services.usergroup.TestAddGroupSettings(888L, 'everyone@example.com')
    auth = authdata.AuthData(user_id=111L, email='test@example.com')
    authdata.AuthData._FinishInitialization(
        self.cnxn, auth, self.services)
    self.assertEqual(auth.user_id, 111L)
    self.assertEqual(auth.effective_ids, {111L, 888L})
