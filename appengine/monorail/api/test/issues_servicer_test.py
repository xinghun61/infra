# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the issues servicer."""

import logging
import unittest

from google.protobuf import empty_pb2

from components.prpc import codes
from components.prpc import context
from components.prpc import server

from api import issues_servicer
from api.api_proto import common_pb2
from api.api_proto import issues_pb2
from api.api_proto import issue_objects_pb2
from framework import authdata
from framework import monorailcontext
from proto import tracker_pb2
from testing import fake
from services import service_manager


class IssuesServicerTest(unittest.TestCase):

  NOW = 1234567890

  def setUp(self):
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
    self.issue_1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111L, project_name='proj',
        opened_timestamp=self.NOW)
    self.issue_2 = fake.MakeTestIssue(
        789, 2, 'sum', 'New', 111L, project_name='proj')
    self.issue_1.blocked_on_iids.append(self.issue_2.issue_id)
    self.services.issue.TestAddIssue(self.issue_1)
    self.services.issue.TestAddIssue(self.issue_2)
    self.issues_svcr = issues_servicer.IssuesServicer(
        self.services, make_rate_limiter=False)
    self.prpc_context = context.ServicerContext()
    self.prpc_context.set_code(server.StatusCode.OK)

  def CallWrapped(self, wrapped_handler, *args, **kwargs):
    return wrapped_handler.wrapped(self.issues_svcr, *args, **kwargs)

  def testCreateIssue_Normal(self):
    """We can create an issue."""
    request = issues_pb2.CreateIssueRequest(
        project_name='proj',
        issue=issue_objects_pb2.Issue(
            project_name='proj', local_id=1, summary='sum'))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    response = self.CallWrapped(self.issues_svcr.CreateIssue, mc, request)

    self.assertEqual('proj', response.project_name)

  def testGetIssue_Normal(self):
    """We can get an issue."""
    request = issues_pb2.GetIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    response = self.CallWrapped(self.issues_svcr.GetIssue, mc, request)

    actual = response.issue
    self.assertEqual('proj', actual.project_name)
    self.assertEqual(1, actual.local_id)
    self.assertEqual(1, len(actual.blocked_on_issue_refs))
    self.assertEqual('proj', actual.blocked_on_issue_refs[0].project_name)
    self.assertEqual(2, actual.blocked_on_issue_refs[0].local_id)

  def testListComments_Normal(self):
    """We can get comments on an issue."""
    comment = tracker_pb2.IssueComment(
        user_id=111L, timestamp=self.NOW, content='second',
        project_id=789, issue_id=self.issue_1.issue_id, sequence=1)
    self.services.issue.TestAddComment(comment, self.issue_1.local_id)
    request = issues_pb2.ListCommentsRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    response = self.CallWrapped(self.issues_svcr.ListComments, mc, request)

    actual_0 = response.comments[0]
    actual_1 = response.comments[1]
    expected_0 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=0, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111L, display_name='owner@example.com'),
        timestamp=self.NOW, content='sum', is_spam=False,
        description_num=1)
    expected_1 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=1, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111L, display_name='owner@example.com'),
        timestamp=self.NOW, content='second')
    self.assertEqual(expected_0, actual_0)
    self.assertEqual(expected_1, actual_1)

  def testDoDeleteIssueComment_Normal(self):
    """We can delete a comment."""
    request = issues_pb2.DeleteIssueCommentRequest(
        project_name='proj', local_id=1, comment_id=11, delete=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    response = self.CallWrapped(
        self.issues_svcr.DeleteIssueComment, mc, request)

    self.assertTrue(isinstance(response, empty_pb2.Empty))
