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
from tracker import tracker_constants
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
        project_star=fake.ProjectStarService(),
        features=fake.FeaturesService())

    self.services.user.TestAddUser('owner@example.com', 111L)
    self.services.user.TestAddUser('user_222@example.com', 222L)
    self.services.user.TestAddUser('user_333@example.com', 333L)
    self.services.user.TestAddUser('user_444@example.com', 444L)
    self.services.user.TestAddUser('user_666@example.com', 666L)

    # User group 888 has members: user_555 and proj@monorail.com
    self.services.user.TestAddUser('group888@googlegroups.com', 888L)
    self.services.usergroup.TestAddGroupSettings(
        888L, 'group888@googlegroups.com')
    self.services.usergroup.TestAddMembers(888L, [555L, 1001L])

    # User group 999 has members: user_111 and user_444
    self.services.user.TestAddUser('group999@googlegroups.com', 999L)
    self.services.usergroup.TestAddGroupSettings(
        999L, 'group999@googlegroups.com')
    self.services.usergroup.TestAddMembers(999L, [111L, 444L])

    self.project = self.services.project.TestAddProject(
        'proj', project_id=789)
    self.project.owner_ids.extend([111L])
    self.project.committer_ids.extend([222L])
    self.project.contributor_ids.extend([333L])
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

  def assertVisibleMembers(self, expected_user_ids, expected_group_ids,
                           requester=None):
    request = projects_pb2.GetVisibleMembersRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester=requester)
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.GetVisibleMembers, mc, request)
    self.assertEqual(
        expected_user_ids,
        [user_ref.user_id for user_ref in response.user_refs])
    self.assertEqual(
        expected_group_ids,
        [group_ref.user_id for group_ref in response.group_refs])
    return response

  def testGetVisibleMembers_Normal(self):
    # Not logged in
    self.assertVisibleMembers([111L, 222L, 333L], [])
    # Logged in
    self.assertVisibleMembers([111L, 222L, 333L], [],
                              requester='foo@example.com')
    # Logged in as owner
    self.assertVisibleMembers([111L, 222L, 333L], [],
                              requester='owner@example.com')
    # Logged in as comitter
    self.assertVisibleMembers([111L, 222L, 333L], [],
                              requester='user_222@example.com')
    # Logged in as contributor
    self.assertVisibleMembers([111L, 222L, 333L], [],
                              requester='user_333@example.com')

  def testGetVisibleMembers_OnlyOwnersSeeContributors(self):
    self.project.only_owners_see_contributors = True
    # Not logged in
    self.assertVisibleMembers([111L, 222L], [])
    # Logged in
    self.assertVisibleMembers([111L, 222L], [],
                              requester='foo@example.com')
    # Logged in as owner
    self.assertVisibleMembers([111L, 222L, 333L], [],
                              requester='owner@example.com')
    # Logged in as comitter
    self.assertVisibleMembers([111L, 222L, 333L], [],
                              requester='user_222@example.com')
    # Logged in as contributor
    self.assertVisibleMembers([111L, 222L], [],
                              requester='user_333@example.com')

  def testGetVisibleMembers_MemberIsGroup(self):
    self.project.contributor_ids.extend([999L])
    self.assertVisibleMembers([111L, 222L, 333L, 444L, 999L], [999L],
                              requester='owner@example.com')

  def testGetVisibleMembers_AcExclusion(self):
    self.services.project.ac_exclusion_ids[self.project.project_id] = [333L]
    self.assertVisibleMembers([111L, 222L], [], requester='owner@example.com')

  def testGetVisibleMembers_NoExpand(self):
    self.services.project.no_expand_ids[self.project.project_id] = [999L]
    self.project.contributor_ids.extend([999L])
    self.assertVisibleMembers([111L, 222L, 333L, 999L], [999L],
                              requester='owner@example.com')

  def AddField(self, name, **kwargs):
    if kwargs.get('needs_perm'):
      kwargs['needs_member'] = True
    kwargs.setdefault('cnxn', self.cnxn)
    kwargs.setdefault('project_id', self.project.project_id)
    kwargs.setdefault('field_name', name)
    kwargs.setdefault('field_type_str', 'USER_TYPE')
    for arg in ('applic_type', 'applic_pred', 'is_required', 'is_niche',
                'is_multivalued', 'min_value', 'max_value', 'regex',
                'needs_member', 'needs_perm', 'grants_perm', 'notify_on',
                'date_action_str', 'docstring', 'admin_ids'):
      kwargs.setdefault(arg, None)

    self.services.config.CreateFieldDef(**kwargs)

  def testListFields_Normal(self):
    self.AddField('Foo Field', needs_perm=permissions.EDIT_ISSUE)

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_user_choices=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)
    self.assertEqual(
        [111L, 222L],
        sorted([user_ref.user_id for user_ref in field.user_choices]))

  def testListFields_DontIncludeUserChoices(self):
    self.AddField('Foo Field', needs_perm=permissions.EDIT_ISSUE)

    request = projects_pb2.ListFieldsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual(0, len(field.user_choices))

  def testListFields_IncludeAdminInfo(self):
    self.AddField('Foo Field', needs_perm=permissions.EDIT_ISSUE, is_niche=True,
                  applic_type='Foo Applic Type')

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_admin_info=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)
    self.assertEqual(True, field.is_niche)
    self.assertEqual('Foo Applic Type', field.applicable_type)

  def testListFields_EnumFieldChoices(self):
    self.AddField('Type', field_type_str='ENUM_TYPE')

    request = projects_pb2.ListFieldsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Type', field.field_ref.field_name)
    self.assertEqual(
        ['Defect', 'Enhancement', 'Task', 'Other'],
        [label.label for label in field.enum_choices])

  def testListFields_CustomPermission(self):
    self.AddField('Foo Field', needs_perm='FooPerm')
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=222L,
            perms=['FooPerm'])]

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_user_choices=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)
    self.assertEqual(
        [222L],
        sorted([user_ref.user_id for user_ref in field.user_choices]))

  def testListFields_NoPermissionsNeeded(self):
    self.AddField('Foo Field')

    request = projects_pb2.ListFieldsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)

  def testListFields_MultipleFields(self):
    self.AddField('Bar Field', needs_perm=permissions.VIEW)
    self.AddField('Foo Field', needs_perm=permissions.EDIT_ISSUE)

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_user_choices=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(2, len(response.field_defs))
    field_defs = sorted(
        response.field_defs, key=lambda field: field.field_ref.field_name)

    self.assertEqual(
        ['Bar Field', 'Foo Field'],
        [field.field_ref.field_name for field in field_defs])
    self.assertEqual(
        [[111L, 222L, 333L],
         [111L, 222L]],
        [sorted(user_ref.user_id for user_ref in field.user_choices)
         for field in field_defs])

  def testListFields_NoFields(self):
    request = projects_pb2.ListFieldsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(0, len(response.field_defs))

  def testGetLabelOptions_Normal(self):
    request = projects_pb2.GetLabelOptionsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.GetLabelOptions, mc, request)

    expected_label_names = [
        label[0] for label in tracker_constants.DEFAULT_WELL_KNOWN_LABELS]
    expected_label_names += [
        'Restrict-View-EditIssue', 'Restrict-AddIssueComment-EditIssue',
        'Restrict-View-CoreTeam']
    self.assertEqual(
        sorted(expected_label_names),
        sorted(label.label for label in response.label_options))

  def testGetLabelOptions_CustomPermissions(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=222L,
            perms=['FooPerm', 'BarPerm'])]

    request = projects_pb2.GetLabelOptionsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.GetLabelOptions, mc, request)

    expected_label_names = [
        label[0] for label in tracker_constants.DEFAULT_WELL_KNOWN_LABELS]
    expected_label_names += [
        'Restrict-View-EditIssue', 'Restrict-AddIssueComment-EditIssue']
    expected_label_names += [
        'Restrict-%s-%s' % (std_perm, custom_perm)
        for std_perm in permissions.STANDARD_ISSUE_PERMISSIONS
        for custom_perm in ('BarPerm', 'FooPerm')]

    self.assertEqual(
        sorted(expected_label_names),
        sorted(label.label for label in response.label_options))

  def testGetLabelOptions_FieldMasksLabel(self):
    self.AddField('Type')

    request = projects_pb2.GetLabelOptionsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.GetLabelOptions, mc, request)

    expected_label_names = [
        label[0] for label in tracker_constants.DEFAULT_WELL_KNOWN_LABELS
        if not label[0].startswith('Type-')
    ]
    expected_label_names += [
        'Restrict-View-EditIssue', 'Restrict-AddIssueComment-EditIssue',
        'Restrict-View-CoreTeam']
    self.assertEqual(
        sorted(expected_label_names),
        sorted(label.label for label in response.label_options))

  def CallGetStarCount(self):
    request = projects_pb2.GetStarCountRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.GetStarCount, mc, request)
    return response.star_count

  def SetStar(self, user_id=111L, starred=True):
    self.services.project_star.SetStar(
        self.cnxn, self.project.project_id, user_id, starred)

  def testGetStarCount_Normal(self):
    self.assertEqual(0, self.CallGetStarCount())
    self.SetStar()
    self.assertEqual(1, self.CallGetStarCount())

  def testGetStarCount_StarTwiceSameUser(self):
    self.SetStar()
    self.SetStar()
    self.assertEqual(1, self.CallGetStarCount())

  def testGetStarCount_StarTwiceDifferentUser(self):
    self.SetStar()
    self.SetStar(user_id=222L)
    self.assertEqual(2, self.CallGetStarCount())

  def testGetStarCount_RemoveStarTwiceSameUser(self):
    self.SetStar()
    self.assertEqual(1, self.CallGetStarCount())
    self.SetStar(starred=False)
    self.SetStar(starred=False)
    self.assertEqual(0, self.CallGetStarCount())

  def testGetStarCount_RemoveStarTwiceDifferentUser(self):
    self.SetStar()
    self.SetStar(user_id=222L)
    self.assertEqual(2, self.CallGetStarCount())
    self.SetStar(starred=False)
    self.SetStar(user_id=222L, starred=False)
    self.assertEqual(0, self.CallGetStarCount())
