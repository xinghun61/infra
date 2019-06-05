# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for MonorailContext."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

import mox

from framework import authdata
from framework import monorailcontext
from framework import permissions
from framework import profiler
from framework import template_helpers
from framework import sql
from services import service_manager
from testing import fake


class MonorailContextTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789, owner_ids=[111])
    self.user = self.services.user.TestAddUser('owner@example.com', 111)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testConstructor_PassingAuthAndPerms(self):
    """We can easily make an mc for testing."""
    auth = authdata.AuthData(user_id=111, email='owner@example.com')
    mc = monorailcontext.MonorailContext(
      None, cnxn=self.cnxn, auth=auth, perms=permissions.USER_PERMISSIONSET)
    self.assertEqual(self.cnxn, mc.cnxn)
    self.assertEqual(auth, mc.auth)
    self.assertEqual(permissions.USER_PERMISSIONSET, mc.perms)
    self.assertTrue(isinstance(mc.profiler, profiler.Profiler))
    self.assertEqual([], mc.warnings)
    self.assertTrue(isinstance(mc.errors, template_helpers.EZTError))

    mc.CleanUp()
    self.assertIsNone(mc.cnxn)

  def testConstructor_AsUsedInApp(self):
    """We can make an mc like it is done in the app or a test."""
    self.mox.StubOutClassWithMocks(sql, 'MonorailConnection')
    mock_cnxn = sql.MonorailConnection()
    mock_cnxn.Close()
    requester = 'new-user@example.com'
    self.mox.ReplayAll()

    mc = monorailcontext.MonorailContext(self.services, requester=requester)
    mc.LookupLoggedInUserPerms(self.project)
    self.assertEqual(mock_cnxn, mc.cnxn)
    self.assertEqual(requester, mc.auth.email)
    self.assertEqual(permissions.USER_PERMISSIONSET, mc.perms)
    self.assertTrue(isinstance(mc.profiler, profiler.Profiler))
    self.assertEqual([], mc.warnings)
    self.assertTrue(isinstance(mc.errors, template_helpers.EZTError))

    mc.CleanUp()
    self.assertIsNone(mc.cnxn)

    # Double Cleanup or Cleanup with no cnxn is not a crash.
    mc.CleanUp()
    self.assertIsNone(mc.cnxn)

  def testRepr(self):
    """We get nice debugging strings."""
    auth = authdata.AuthData(user_id=111, email='owner@example.com')
    mc = monorailcontext.MonorailContext(
      None, cnxn=self.cnxn, auth=auth, perms=permissions.USER_PERMISSIONSET)
    repr_str = '%r' % mc
    self.assertTrue(repr_str.startswith('MonorailContext('))
    self.assertIn('owner@example.com', repr_str)
    self.assertIn('view', repr_str)
