# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
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
    self.services.user.TestAddUser('test@example.com', 111)

  # TODO(jrobbins): Fill in a bunch of missing tests here.

  def testFinishInitialization_NoMemberships(self):
    """No user groups means effective_ids == {user_id}."""
    auth = authdata.AuthData(user_id=111, email='test@example.com')
    authdata.AuthData._FinishInitialization(
        self.cnxn, auth, self.services)
    self.assertEqual(auth.user_id, 111)
    self.assertEqual(auth.effective_ids, {111})

  def testFinishInitialization_NormalMemberships(self):
    """effective_ids should be {user_id, group_id...}."""
    self.services.usergroup.TestAddMembers(888, [111])
    self.services.usergroup.TestAddMembers(999, [111])
    auth = authdata.AuthData(user_id=111, email='test@example.com')
    authdata.AuthData._FinishInitialization(
        self.cnxn, auth, self.services)
    self.assertEqual(auth.user_id, 111)
    self.assertEqual(auth.effective_ids, {111, 888, 999})

  def testFinishInitialization_ComputedUserGroup(self):
    """effective_ids should be {user_id, group_id...}."""
    self.services.usergroup.TestAddGroupSettings(888, 'everyone@example.com')
    auth = authdata.AuthData(user_id=111, email='test@example.com')
    authdata.AuthData._FinishInitialization(
        self.cnxn, auth, self.services)
    self.assertEqual(auth.user_id, 111)
    self.assertEqual(auth.effective_ids, {111, 888})
