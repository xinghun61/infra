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
from api.api_proto import common_pb2
from api.api_proto import project_objects_pb2
from api.api_proto import projects_pb2
from framework import authdata
from framework import exceptions
from framework import framework_constants
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

    self.admin = self.services.user.TestAddUser('admin@example.com', 123L)
    self.admin.is_site_admin = True
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

    # User group 777 has members: user_666 and group 999.
    self.services.user.TestAddUser('group777@googlegroups.com', 777L)
    self.services.usergroup.TestAddGroupSettings(
        777L, 'group777@googlegroups.com')
    self.services.usergroup.TestAddMembers(777L, [666L, 999L])

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
    # Assert that we get the full email address.
    self.assertEqual(
        [self.services.user.LookupUserEmail(self.cnxn, user_id)
         for user_id in expected_user_ids],
        [user_ref.display_name for user_ref in response.user_refs])
    self.assertEqual(
        expected_group_ids,
        [group_ref.user_id for group_ref in response.group_refs])
    # Assert that we get the full email address.
    self.assertEqual(
        [self.services.user.LookupUserEmail(self.cnxn, user_id)
         for user_id in expected_group_ids],
        [group_ref.display_name for group_ref in response.group_refs])
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
    # Logged in as committer
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
    # Logged in as committer
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

  def testListStatuses(self):
    request = projects_pb2.ListStatusesRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListStatuses, mc, request)
    self.assertFalse(response.restrict_to_known)
    self.assertEqual(
        [('New', True),
         ('Accepted', True),
         ('Started', True),
         ('Fixed', False),
         ('Verified', False),
         ('Invalid', False),
         ('Duplicate', False),
         ('WontFix', False),
         ('Done', False)],
        [(status_def.status, status_def.means_open)
         for status_def in response.status_defs])
    self.assertEqual(
        [('Duplicate', False)],
        [(status_def.status, status_def.means_open)
         for status_def in response.statuses_offer_merge])

  def testListComponents(self):
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Foo', 'Foo Component', True, [],
        [], True, 111L, [])
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Bar', 'Bar Component', False, [],
        [], True, 111L, [])
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Bar>Baz', 'Baz Component',
        False, [], [], True, 111L, [])

    request = projects_pb2.ListComponentsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListComponents, mc, request)

    self.assertEqual(
        [project_objects_pb2.ComponentDef(
            path='Foo',
            docstring='Foo Component',
            deprecated=True),
         project_objects_pb2.ComponentDef(
             path='Bar',
             docstring='Bar Component',
             deprecated=False),
         project_objects_pb2.ComponentDef(
             path='Bar>Baz',
             docstring='Baz Component',
             deprecated=False)],
        list(response.component_defs))

  def testListComponents_IncludeAdminInfo(self):
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Foo', 'Foo Component', True, [],
        [], 1234567, 111L, [])
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Bar', 'Bar Component', False, [],
        [], 1234568, 111L, [])
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Bar>Baz', 'Baz Component',
        False, [], [], 1234569, 111L, [])
    creator_ref = common_pb2.UserRef(
        user_id=111L,
        display_name='owner@example.com')
    no_user_ref = common_pb2.UserRef(
        display_name=framework_constants.NO_USER_NAME)

    request = projects_pb2.ListComponentsRequest(
        project_name='proj', include_admin_info=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListComponents, mc, request)

    self.assertEqual(
        [project_objects_pb2.ComponentDef(
            path='Foo',
            docstring='Foo Component',
            deprecated=True,
            created=1234567,
            creator_ref=creator_ref,
             modifier_ref=no_user_ref),
         project_objects_pb2.ComponentDef(
             path='Bar',
             docstring='Bar Component',
             deprecated=False,
             created=1234568,
             creator_ref=creator_ref,
             modifier_ref=no_user_ref),
         project_objects_pb2.ComponentDef(
             path='Bar>Baz',
             docstring='Baz Component',
             deprecated=False,
             created=1234569,
             creator_ref=creator_ref,
             modifier_ref=no_user_ref),
            ],
        list(response.component_defs))

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
    self.assertEqual(
        ['owner@example.com', 'user_222@example.com'],
        sorted([user_ref.display_name for user_ref in field.user_choices]))

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
            member_id=111L,
            perms=['UnrelatedPerm']),
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
    self.assertEqual(
        ['user_222@example.com'],
        sorted([user_ref.display_name for user_ref in field.user_choices]))

  def testListFields_IndirectPermission(self):
    """Test that the permissions of effective ids are also considered."""
    self.AddField('Foo Field', needs_perm='FooPerm')
    self.project.contributor_ids.extend([999L])
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=999L,
            perms=['FooPerm', 'BarPerm'])]

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_user_choices=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)
    # Users 111L and 444L are members of group 999L, which has the needed
    # permission.
    self.assertEqual(
        [111L, 444L, 999L],
        sorted([user_ref.user_id for user_ref in field.user_choices]))
    self.assertEqual(
        ['group999@googlegroups.com', 'owner@example.com',
         'user_444@example.com'],
        sorted([user_ref.display_name for user_ref in field.user_choices]))

  def testListFields_TwiceIndirectPermission(self):
     """Test that only direct memberships are considered."""
     self.AddField('Foo Field', needs_perm='FooPerm')
     self.project.contributor_ids.extend([777L])
     self.project.contributor_ids.extend([999L])
     self.project.extra_perms = [
         project_pb2.Project.ExtraPerms(
             member_id=777L,
             perms=['FooPerm', 'BarPerm'])]

     request = projects_pb2.ListFieldsRequest(
         project_name='proj', include_user_choices=True)
     mc = monorailcontext.MonorailContext(
         self.services, cnxn=self.cnxn, requester='owner@example.com')
     mc.LookupLoggedInUserPerms(self.project)
     response = self.CallWrapped(
         self.projects_svcr.ListFields, mc, request)

     self.assertEqual(1, len(response.field_defs))
     field = response.field_defs[0]
     self.assertEqual('Foo Field', field.field_ref.field_name)
     self.assertEqual(
         [666L, 777L, 999L],
         sorted([user_ref.user_id for user_ref in field.user_choices]))
     self.assertEqual(
         ['group777@googlegroups.com', 'group999@googlegroups.com',
          'user_666@example.com'],
         sorted([user_ref.display_name for user_ref in field.user_choices]))

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
    self.assertEqual(
        [['owner@example.com', 'user_222@example.com', 'user_333@example.com'],
         ['owner@example.com', 'user_222@example.com']],
        [sorted(user_ref.display_name for user_ref in field.user_choices)
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
    request = projects_pb2.GetProjectStarCountRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.GetProjectStarCount, mc, request)
    return response.star_count

  def CallStar(self, requester='owner@example.com', starred=True):
    request = projects_pb2.StarProjectRequest(
        project_name='proj', starred=starred)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester=requester)
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.StarProject, mc, request)
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
    self.assertEqual(2, self.CallStar(requester='user_222@example.com'))
    self.assertEqual(2, self.CallGetStarCount())

  def testStarCount_RemoveStarTwiceSameUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

    self.assertEqual(0, self.CallStar(starred=False))
    self.assertEqual(0, self.CallStar(starred=False))
    self.assertEqual(0, self.CallGetStarCount())

  def testStarCount_RemoveStarTwiceDifferentUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(2, self.CallStar(requester='user_222@example.com'))
    self.assertEqual(2, self.CallGetStarCount())

    self.assertEqual(1, self.CallStar(starred=False))
    self.assertEqual(
        0, self.CallStar(requester='user_222@example.com', starred=False))
    self.assertEqual(0, self.CallGetStarCount())

  def AddUserProjects(self):
    project_states = {
        'live': project_pb2.ProjectState.LIVE,
        'archived': project_pb2.ProjectState.ARCHIVED,
        'deletable': project_pb2.ProjectState.DELETABLE}

    for name, state in project_states.iteritems():
      self.services.project.TestAddProject(
          'owner-' + name, state=state, owner_ids=[222L])
      self.services.project.TestAddProject(
          'committer-' + name, state=state, committer_ids=[222L])
      contributor = self.services.project.TestAddProject(
          'contributor-' + name, state=state)
      contributor.contributor_ids = [222L]

    members_only = self.services.project.TestAddProject(
        'members-only', owner_ids=[222L])
    members_only.access = project_pb2.ProjectAccess.MEMBERS_ONLY

  def testGetUserProjects(self):
    self.AddUserProjects()
    self.services.project_star.SetStar(
        self.cnxn, self.project.project_id, 222L, True)

    request = projects_pb2.GetUserProjectsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user_222@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.GetUserProjects, mc, request)

    self.assertEqual(
        projects_pb2.GetUserProjectsResponse(
            owner_of=['members-only', 'owner-live'],
            member_of=['committer-live', 'proj'],
            contributor_to=['contributor-live'],
            starred_projects=['proj']),
        response)

  def testCheckProjectName_OK(self):
    """We can check a project name."""
    request = projects_pb2.CheckProjectNameRequest(project_name='Foo')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.CheckProjectName, mc, request)

    self.assertEqual('', response.error)

  def testCheckProjectName_NotAllowed(self):
    """Users that can't create a project shouldn't get any information."""
    request = projects_pb2.CheckProjectNameRequest(project_name='Foo')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.projects_svcr.CheckProjectName, mc, request)

  def testCheckProjectName_ProjectAlreadyExists(self):
    """There is already a project with that name."""
    request = projects_pb2.CheckProjectNameRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.CheckProjectName, mc, request)

    self.assertNotEqual('', response.error)
