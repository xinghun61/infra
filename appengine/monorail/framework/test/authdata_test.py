# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the authdata module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

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

  def testFinishInitialization_AccountHasParent(self):
    """The parent's effective_ids are added to child's."""
    child = self.services.user.TestAddUser('child@example.com', 111)
    child.linked_parent_id = 222
    parent = self.services.user.TestAddUser('parent@example.com', 222)
    parent.linked_child_ids = [111]
    auth = authdata.AuthData(user_id=111, email='child@example.com')
    authdata.AuthData._FinishInitialization(
        self.cnxn, auth, self.services)
    self.assertEqual(auth.user_id, 111)
    self.assertEqual(auth.effective_ids, {111, 222})

    self.services.usergroup.TestAddMembers(888, [111])
    self.services.usergroup.TestAddMembers(999, [222])
    auth = authdata.AuthData(user_id=111, email='child@example.com')
    authdata.AuthData._FinishInitialization(
        self.cnxn, auth, self.services)
    self.assertEqual(auth.user_id, 111)
    self.assertEqual(auth.effective_ids, {111, 222, 888, 999})

  def testFinishInitialization_AccountHasChildren(self):
    """All linked child effective_ids are added to parent's."""
    child1 = self.services.user.TestAddUser('child1@example.com', 111)
    child1.linked_parent_id = 333
    child2 = self.services.user.TestAddUser('child3@example.com', 222)
    child2.linked_parent_id = 333
    parent = self.services.user.TestAddUser('parent@example.com', 333)
    parent.linked_child_ids = [111, 222]

    auth = authdata.AuthData(user_id=333, email='parent@example.com')
    authdata.AuthData._FinishInitialization(
        self.cnxn, auth, self.services)
    self.assertEqual(auth.user_id, 333)
    self.assertEqual(auth.effective_ids, {111, 222, 333})

    self.services.usergroup.TestAddMembers(888, [111])
    self.services.usergroup.TestAddMembers(999, [222])
    auth = authdata.AuthData(user_id=333, email='parent@example.com')
    authdata.AuthData._FinishInitialization(
        self.cnxn, auth, self.services)
    self.assertEqual(auth.user_id, 333)
    self.assertEqual(auth.effective_ids, {111, 222, 333, 888, 999})
