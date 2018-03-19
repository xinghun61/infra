# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the projects servicer."""

import unittest

import mox

from api import projects_servicer
from api.proto import projects_pb2

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
        project=fake.ProjectService(),
        features=fake.FeaturesService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.user = self.services.user.TestAddUser('to_pass_tests', 0L)
    self.services.features.TestAddHotlist(
        name='dontcare', summary='', owner_ids=[0L])
    self.projects_svcr = projects_servicer.ProjectsServicer()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testListProjects_Normal(self):
    """We can get a list of all projects on the site."""
    req = projects_pb2.ListProjectsRequest()
    context = None
    ret = self.projects_svcr.ListProjects(req, context)
    self.assertEqual(2, len(ret.projects))

  def testUpdateProjectConfiguredLabels_Normal(self):
    """We can replace all label definitions in a project."""
    req = projects_pb2.UpdateProjectConfiguredLabelsRequest(project='proj')
    context = None
    ret = self.projects_svcr.UpdateProjectConfiguredLabels(req, context)
    self.assertEqual(4, len(ret.labels))

  def testPatchProjectConfiguredLabels_Normal(self):
    """We can modify label definitions in a project."""
    req = projects_pb2.PatchProjectConfiguredLabelsRequest(project='proj')
    context = None
    ret = self.projects_svcr.PatchProjectConfiguredLabels(req, context)
    self.assertEqual(4, len(ret.labels))
