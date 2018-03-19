# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the users servicer."""

import unittest

import mox

from api import users_servicer
from api.proto import users_pb2

from testing import fake
from services import service_manager


class UsersServicerTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService(),
        features=fake.FeaturesService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.user = self.services.user.TestAddUser('to_pass_tests', 0L)
    self.services.features.TestAddHotlist(
        name='dontcare', summary='', owner_ids=[0L])
    self.users_svcr = users_servicer.UsersServicer()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testGetUsers_Normal(self):
    """We can get a user by email address."""
    req = users_pb2.GetUserRequest(email='test@example.com')
    context = None
    ret = self.users_svcr.GetUser(req, context)
    self.assertEqual(hash('test@example.com'), ret.id)
