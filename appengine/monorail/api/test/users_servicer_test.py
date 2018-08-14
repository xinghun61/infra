# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the users servicer."""

import unittest

import mox
from components.prpc import codes
from components.prpc import context
from components.prpc import server

from api import users_servicer
from api.api_proto import common_pb2
from api.api_proto import users_pb2
from api.api_proto import user_objects_pb2
from framework import authdata
from framework import monorailcontext
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
        user_star=fake.UserStarService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        features=fake.FeaturesService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.user = self.services.user.TestAddUser('owner@example.com', 111L)
    self.user_2 = self.services.user.TestAddUser('test2@example.com', 222L)
    self.users_svcr = users_servicer.UsersServicer(
        self.services, make_rate_limiter=False)
    self.prpc_context = context.ServicerContext()
    self.prpc_context.set_code(codes.StatusCode.OK)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def CallWrapped(self, wrapped_handler, *args, **kwargs):
    return wrapped_handler.wrapped(self.users_svcr, *args, **kwargs)

  def testGetUser_Normal(self):
    """We can get a user by email address."""
    request = common_pb2.UserRef(display_name='test2@example.com', user_id=222L)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.users_svcr.GetUser, mc, request)
    self.assertEqual('test2@example.com', response.email)
    self.assertEqual(222L, response.user_id)

  def testListCommits_Normal(self):
    """We can get user commits"""
    request = users_pb2.GetUserCommitsRequest(email="test@example.com",
        from_timestamp=1, until_timestamp=3)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    response = self.CallWrapped(self.users_svcr.GetUserCommits, mc, request)

    actual_0 = response.user_commits[0]
    actual_1 = response.user_commits[1]
    expected_0 = user_objects_pb2.Commit(commit_sha="mysha2",
        author_id=3784859778, commit_time=2, commit_message="hi",
        commit_repo_url="repo")
    expected_1 = user_objects_pb2.Commit(commit_sha="mysha1",
        author_id=3784859778, commit_time=1, commit_message="hi",
        commit_repo_url="repo")
    self.assertEqual(expected_0, actual_0)
    self.assertEqual(expected_1, actual_1)

  def testListReferencedUsers(self):
    """We can get all valid users by email addresses."""
    request = users_pb2.ListReferencedUsersRequest(
        # we ignore emails that are empty or belong to non-existent users.
        emails=['test2@example.com', 'ghost@example.com', ''])
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.users_svcr.ListReferencedUsers, mc, request)
    self.assertEqual(len(response.users), 1)
    self.assertEqual(response.users[0].user_id, 222L)

  def CallGetStarCount(self):
    request = users_pb2.GetUserStarCountRequest(
        user_ref=common_pb2.UserRef(user_id=222L))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.users_svcr.GetUserStarCount, mc, request)
    return response.star_count

  def CallStar(self, requester='owner@example.com', starred=True):
    request = users_pb2.StarUserRequest(
        user_ref=common_pb2.UserRef(user_id=222L), starred=starred)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester=requester)
    response = self.CallWrapped(
        self.users_svcr.StarUser, mc, request)
    return response.star_count

  def testStarCount_Normal(self):
    self.assertEqual(0, self.CallGetStarCount())
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

  def testStarCount_StarTwiceSameUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

  def testStarCount_StarTwiceDifferentUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(2, self.CallStar(requester='test2@example.com'))
    self.assertEqual(2, self.CallGetStarCount())

  def testStarCount_RemoveStarTwiceSameUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

    self.assertEqual(0, self.CallStar(starred=False))
    self.assertEqual(0, self.CallStar(starred=False))
    self.assertEqual(0, self.CallGetStarCount())

  def testStarCount_RemoveStarTwiceDifferentUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(2, self.CallStar(requester='test2@example.com'))
    self.assertEqual(2, self.CallGetStarCount())

    self.assertEqual(1, self.CallStar(starred=False))
    self.assertEqual(
        0, self.CallStar(requester='test2@example.com', starred=False))
    self.assertEqual(0, self.CallGetStarCount())
