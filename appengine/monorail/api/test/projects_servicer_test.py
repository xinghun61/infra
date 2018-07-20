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
from framework import exceptions
from framework import monorailcontext
from framework import permissions
from proto import project_pb2
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
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789, owner_ids=[111L])
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

  def testListProjects_Normal(self):
    """We can get a list of all projects on the site."""
    request = projects_pb2.ListProjectsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.projects_svcr.ListProjects, mc, request)
    self.assertEqual(2, len(response.projects))

  def testGetConfig_Normal(self):
    """We can get a project config."""
    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.projects_svcr.GetConfig, mc, request)
    self.assertEqual('proj', response.project_name)

  def testGetConfig_NoSuchProject(self):
    """We reject a request to get a config for a non-existent project."""
    request = projects_pb2.GetConfigRequest(project_name='unknown-proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    with self.assertRaises(exceptions.NoSuchProjectException):
      self.CallWrapped(self.projects_svcr.GetConfig, mc, request)

  def testGetConfig_PermissionDenied(self):
    """We reject a request to get a config for a non-viewable project."""
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    request = projects_pb2.GetConfigRequest(project_name='proj')

    # User is a member of the members-only project.
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.projects_svcr.GetConfig, mc, request)
    self.assertEqual('proj', response.project_name)

    # User is not a member of the members-only project.
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='nonmember@example.com')
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.projects_svcr.GetConfig, mc, request)

  def testGetCustomPermissions_Normal(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111L,
            perms=['FooPerm', 'BarPerm'])]

    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual(['BarPerm', 'FooPerm'], response.permissions)

  def testGetCustomPermissions_PermissionsAreDedupped(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111L,
            perms=['FooPerm', 'FooPerm']),
        project_pb2.Project.ExtraPerms(
            member_id=222L,
            perms=['FooPerm'])]

    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual(['FooPerm'], response.permissions)

  def testGetCustomPermissions_PermissionsAreSorted(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111L,
            perms=['FooPerm', 'BarPerm']),
        project_pb2.Project.ExtraPerms(
            member_id=222L,
            perms=['BazPerm'])]

    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual(['BarPerm', 'BazPerm', 'FooPerm'], response.permissions)

  def testGetCustomPermissions_PermissionsAreDedupped(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111L,
            perms=['FooPerm', 'FooPerm']),
        project_pb2.Project.ExtraPerms(
            member_id=222L,
            perms=['FooPerm'])]

    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual(['FooPerm'], response.permissions)

  def testGetCustomPermissions_IgnoreStandardPermissions(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111L,
            perms=permissions.STANDARD_PERMISSIONS + ['FooPerm'])]

    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual(['FooPerm'], response.permissions)

  def testGetCustomPermissions_NoCustomPermissions(self):
    self.project.extra_perms = []
    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual([], response.permissions)
