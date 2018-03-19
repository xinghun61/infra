# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the issues servicer."""

import unittest

import mox

from api import issues_servicer
from api.proto import issues_pb2

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
        project=fake.ProjectService(),
        features=fake.FeaturesService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.user = self.services.user.TestAddUser('to_pass_tests', 0L)
    self.services.features.TestAddHotlist(
        name='dontcare', summary='', owner_ids=[0L])
    self.issues_svcr = issues_servicer.IssuesServicer()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testCreateIssue_Normal(self):
    """We can create an issue."""
    req = issues_pb2.CreateIssueRequest(
        project_name='proj',
        issue=issues_pb2.Issue(
            project_name='proj', local_id=1, summary='sum'))
    context = None
    ret = self.issues_svcr.CreateIssue(req, context)
    self.assertEqual('proj', ret.project_name)

  def testDeleteIssueComment_Normal(self):
    """We can delete a comment."""
    req = issues_pb2.DeleteIssueCommentRequest(
        project_name='proj', local_id=1, comment_id=11, delete=True)
    context = None
    ret = self.issues_svcr.DeleteIssueComment(req, context)
    self.assertTrue(ret.deleted)
