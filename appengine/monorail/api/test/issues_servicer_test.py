# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the issues servicer."""

import unittest

import mox
from google.protobuf import empty_pb2

from components.prpc import codes
from components.prpc import context
from components.prpc import server

from api import issues_servicer
from api.api_proto import issues_pb2
from api.api_proto import issue_objects_pb2
from framework import authdata
from framework import monorailcontext
from testing import fake
from services import service_manager


class IssuesServicerTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        features=fake.FeaturesService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789, owner_ids=[111L])
    self.user = self.services.user.TestAddUser('owner@example.com', 111L)
    self.issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111L)
    self.services.issue.TestAddIssue(self.issue)
    self.issues_svcr = issues_servicer.IssuesServicer(
        self.services, make_rate_limiter=False)
    self.prpc_context = context.ServicerContext()
    self.prpc_context.set_code(server.StatusCode.OK)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testCreateIssue(self):
    """API call to CreateIssue can reach Do* method."""
    request = issues_pb2.CreateIssueRequest(
        project_name='proj',
        issue=issue_objects_pb2.Issue(
            project_name='proj', local_id=1, summary='sum'))
    response = self.issues_svcr.CreateIssue(
        request, self.prpc_context, cnxn=self.cnxn,
        auth=authdata.AuthData(user_id=111L, email='owner@example.com'))
    self.assertEqual(codes.StatusCode.OK, self.prpc_context._code)
    self.assertEqual('proj', response.project_name)

  def testDoCreateIssue_Normal(self):
    """We can create an issue."""
    request = issues_pb2.CreateIssueRequest(
        project_name='proj',
        issue=issue_objects_pb2.Issue(
            project_name='proj', local_id=1, summary='sum'))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.issues_svcr.DoCreateIssue(mc, request)
    self.assertEqual('proj', response.project_name)

  def testGetIssue(self):
    """API call to GetIssue can reach Do* method."""
    request = issues_pb2.GetIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 123
    response = self.issues_svcr.GetIssue(
        request, self.prpc_context, cnxn=self.cnxn,
        auth=authdata.AuthData(user_id=111L, email='owner@example.com'))
    self.assertEqual(codes.StatusCode.OK, self.prpc_context._code)
    self.assertEqual('proj', response.issue.project_name)
    self.assertEqual(123, response.issue.local_id)

  def testDoGetIssue_Normal(self):
    """We can get an issue."""
    request = issues_pb2.GetIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 123
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.issues_svcr.DoGetIssue(mc, request)
    self.assertEqual('proj', response.issue.project_name)
    self.assertEqual(123, response.issue.local_id)

  def testDeleteIssueComment(self):
    """API call to DeleteIssueComment can reach Do* method."""
    request = issues_pb2.DeleteIssueCommentRequest(
        project_name='proj', local_id=1, comment_id=11, delete=True)
    response = self.issues_svcr.DeleteIssueComment(
        request, self.prpc_context, cnxn=self.cnxn,
        auth=authdata.AuthData(user_id=111L, email='owner@example.com'))
    self.assertEqual(codes.StatusCode.OK, self.prpc_context._code)
    self.assertTrue(isinstance(response, empty_pb2.Empty))

  def testDoDeleteIssueComment_Normal(self):
    """We can delete a comment."""
    request = issues_pb2.DeleteIssueCommentRequest(
        project_name='proj', local_id=1, comment_id=11, delete=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.issues_svcr.DoDeleteIssueComment(mc, request)
    self.assertTrue(isinstance(response, empty_pb2.Empty))
