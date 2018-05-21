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
from api.api_proto import projects_pb2
from framework import authdata
from framework import monorailcontext
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

  def CallWrapped(self, wrapped_handler, *args, **kwargs):
    return wrapped_handler.wrapped(self.projects_svcr, *args, **kwargs)

  def testDoListProjects_Normal(self):
    """We can get a list of all projects on the site."""
    request = projects_pb2.ListProjectsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.projects_svcr.ListProjects, mc, request)
    self.assertEqual(2, len(response.projects))

  def testDoUpdateProjectConfiguredLabels_Normal(self):
    """We can replace all label definitions in a project."""
    request = projects_pb2.UpdateProjectConfiguredLabelsRequest(project='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.UpdateProjectConfiguredLabels, mc, request)
    self.assertEqual(4, len(response.labels))

  def testDoPatchProjectConfiguredLabels_Normal(self):
    """We can modify label definitions in a project."""
    request = projects_pb2.PatchProjectConfiguredLabelsRequest(project='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.PatchProjectConfiguredLabels, mc, request)
    self.assertEqual(4, len(response.labels))
