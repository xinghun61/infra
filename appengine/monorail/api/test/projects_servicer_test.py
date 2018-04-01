# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the projects servicer."""

import unittest

import mox
from components.prpc import codes
from components.prpc import context
from components.prpc import server

from api import projects_servicer
from api import monorailcontext
from api.api_proto import projects_pb2
from framework import authdata
from testing import fake
from services import service_manager


class ProjectsServicerTest(unittest.TestCase):

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
    self.project = self.services.project.TestAddProject('proj', project_id=789)
    self.user = self.services.user.TestAddUser('owner@example.com', 111L)
    self.projects_svcr = projects_servicer.ProjectsServicer(
        self.services, make_rate_limiter=False)
    self.prpc_context = context.ServicerContext()
    self.prpc_context.set_code(codes.StatusCode.OK)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testListProjects(self):
    """API call to ListProjects() can reach Do* method."""
    request = projects_pb2.ListProjectsRequest()
    response = self.projects_svcr.ListProjects(
        request, self.prpc_context, cnxn=self.cnxn,
        auth=authdata.AuthData(user_id=111L, email='owner@example.com'))
    self.assertEqual(codes.StatusCode.OK, self.prpc_context._code)
    self.assertEqual(2, len(response.projects))

  def testDoListProjects_Normal(self):
    """We can get a list of all projects on the site."""
    request = projects_pb2.ListProjectsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.projects_svcr.DoListProjects(mc, request)
    self.assertEqual(2, len(response.projects))

  def testUpdateProjectConfiguredLabels(self):
    """API call to UpdateProjectConfiguredLabels can reach Do* method."""
    request = projects_pb2.UpdateProjectConfiguredLabelsRequest(project='proj')
    response = self.projects_svcr.UpdateProjectConfiguredLabels(
        request, self.prpc_context, cnxn=self.cnxn,
        auth=authdata.AuthData(user_id=111L, email='owner@example.com'))
    self.assertEqual(codes.StatusCode.OK, self.prpc_context._code)
    self.assertEqual(4, len(response.labels))

  def testDoUpdateProjectConfiguredLabels_Normal(self):
    """We can replace all label definitions in a project."""
    request = projects_pb2.UpdateProjectConfiguredLabelsRequest(project='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.projects_svcr.DoUpdateProjectConfiguredLabels(mc, request)
    self.assertEqual(4, len(response.labels))

  def testPatchProjectConfiguredLabels(self):
    """API call PatchProjectConfiguredLabels can reach Do* method."""
    request = projects_pb2.PatchProjectConfiguredLabelsRequest(project='proj')
    response = self.projects_svcr.PatchProjectConfiguredLabels(
        request, self.prpc_context,
        auth=authdata.AuthData(user_id=111L, email='owner@example.com'))
    self.assertEqual(codes.StatusCode.OK, self.prpc_context._code)
    self.assertEqual(4, len(response.labels))

  def testDoPatchProjectConfiguredLabels_Normal(self):
    """We can modify label definitions in a project."""
    request = projects_pb2.PatchProjectConfiguredLabelsRequest(project='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.projects_svcr.DoPatchProjectConfiguredLabels(mc, request)
    self.assertEqual(4, len(response.labels))
