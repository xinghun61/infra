# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the componentdetail servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from mock import Mock, patch

import mox

from features import filterrules_helpers
from framework import permissions
from proto import project_pb2
from services import service_manager
from services import template_svc
from testing import fake
from testing import testing_helpers
from tracker import componentdetail
from tracker import tracker_bizobj

import webapp2


class ComponentDetailTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        issue=fake.IssueService(),
        config=fake.ConfigService(),
        template=Mock(spec=template_svc.TemplateService),
        project=fake.ProjectService())
    self.servlet = componentdetail.ComponentDetail(
        'req', 'res', services=self.services)
    self.project = self.services.project.TestAddProject('proj')
    self.mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.mr.auth.email = 'b@example.com'
    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', self.project.project_id)
    self.services.config.StoreConfig('fake cnxn', self.config)
    self.cd = tracker_bizobj.MakeComponentDef(
        1, self.project.project_id, 'BackEnd', 'doc', False, [], [111], 100000,
        122, 10000000, 133)
    self.config.component_defs = [self.cd]
    self.services.user.TestAddUser('a@example.com', 111)
    self.services.user.TestAddUser('b@example.com', 122)
    self.services.user.TestAddUser('c@example.com', 133)
    self.mr.component_path = 'BackEnd'

    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testGetComponentDef_NotFound(self):
    self.mr.component_path = 'NeverHeardOfIt'
    self.assertRaises(
        webapp2.HTTPException,
        self.servlet._GetComponentDef, self.mr)

  def testGetComponentDef_Normal(self):
    actual_config, actual_cd = self.servlet._GetComponentDef(self.mr)
    self.assertEqual(self.config, actual_config)
    self.assertEqual(self.cd, actual_cd)

  def testAssertBasePermission_AnyoneCanView(self):
    self.servlet.AssertBasePermission(self.mr)
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

  def testAssertBasePermission_MembersOnly(self):
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    # The project members can view the component definition.
    self.servlet.AssertBasePermission(self.mr)
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)
    # Non-member is not allowed to view anything in the project.
    self.mr.perms = permissions.EMPTY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

  def testGatherPageData_ReadWrite(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_COMPONENTS,
                     page_data['admin_tab_mode'])
    self.assertTrue(page_data['allow_edit'])
    self.assertEqual([], page_data['initial_admins'])
    component_def_view = page_data['component_def']
    self.assertEqual('BackEnd', component_def_view.path)

  def testGatherPageData_ReadOnly(self):
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_COMPONENTS,
                     page_data['admin_tab_mode'])
    self.assertFalse(page_data['allow_edit'])
    self.assertFalse(page_data['allow_delete'])
    self.assertEqual([], page_data['initial_admins'])
    component_def_view = page_data['component_def']
    self.assertEqual('BackEnd', component_def_view.path)

  def testGatherPageData_ObscuredCreatorModifier(self):
    page_data = self.servlet.GatherPageData(self.mr)

    self.assertEqual('b...@example.com', page_data['creator'].display_name)
    self.assertEqual('/u/122/', page_data['creator'].profile_url)
    self.assertEqual('Jan 1970', page_data['created'])
    self.assertEqual('c...@example.com', page_data['modifier'].display_name)
    self.assertEqual('/u/133/', page_data['modifier'].profile_url)
    self.assertEqual('Apr 1970', page_data['modified'])

  def testGatherPageData_VisibleCreatorModifierForAdmin(self):
    self.mr.auth.user_pb.is_site_admin = True
    page_data = self.servlet.GatherPageData(self.mr)

    self.assertEqual('b@example.com', page_data['creator'].display_name)
    self.assertEqual('/u/b@example.com/', page_data['creator'].profile_url)
    self.assertEqual('Jan 1970', page_data['created'])
    self.assertEqual('c@example.com', page_data['modifier'].display_name)
    self.assertEqual('/u/c@example.com/', page_data['modifier'].profile_url)
    self.assertEqual('Apr 1970', page_data['modified'])

  def testGatherPageData_VisibleCreatorForSelf(self):
    self.mr.auth.user_id = 122
    page_data = self.servlet.GatherPageData(self.mr)

    self.assertEqual('b@example.com', page_data['creator'].display_name)
    self.assertEqual('/u/b@example.com/', page_data['creator'].profile_url)
    self.assertEqual('Jan 1970', page_data['created'])
    # Modifier should still be obscured.
    self.assertEqual('c...@example.com', page_data['modifier'].display_name)
    self.assertEqual('/u/133/', page_data['modifier'].profile_url)
    self.assertEqual('Apr 1970', page_data['modified'])

  def testGatherPageData_VisibleCreatorModifierForUnobscuredEmail(self):
    creator = self.services.user.GetUser(self.mr.cnxn, 122)
    creator.obscure_email = False
    modifier = self.services.user.GetUser(self.mr.cnxn, 133)
    modifier.obscure_email = False
    page_data = self.servlet.GatherPageData(self.mr)

    self.assertEqual('b@example.com', page_data['creator'].display_name)
    self.assertEqual('/u/b@example.com/', page_data['creator'].profile_url)
    self.assertEqual('Jan 1970', page_data['created'])
    self.assertEqual('c@example.com', page_data['modifier'].display_name)
    self.assertEqual('/u/c@example.com/', page_data['modifier'].profile_url)
    self.assertEqual('Apr 1970', page_data['modified'])

  def testGatherPageData_WithSubComponents(self):
    subcd = tracker_bizobj.MakeComponentDef(
        2, self.project.project_id, 'BackEnd>Worker', 'doc', False, [], [111],
        0, 122)
    self.config.component_defs.append(subcd)
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertFalse(page_data['allow_delete'])
    self.assertEqual([subcd], page_data['subcomponents'])

  def testGatherPageData_WithTemplates(self):
    self.services.template.TemplatesWithComponent.return_value = ['template']
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertFalse(page_data['allow_delete'])
    self.assertEqual(['template'], page_data['templates'])

  def testProcessFormData_Permission(self):
    """Only owners can edit components."""
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    mr.component_path = 'BackEnd'
    post_data = fake.PostData(
        name=['BackEnd'],
        deletecomponent=['Submit'])
    self.assertRaises(permissions.PermissionException,
                      self.servlet.ProcessFormData, mr, post_data)

    self.servlet.ProcessFormData(self.mr, post_data)

  def testProcessFormData_Delete(self):
    post_data = fake.PostData(
        name=['BackEnd'],
        deletecomponent=['Submit'])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue('/adminComponents?deleted=1&' in url)
    self.assertIsNone(
        tracker_bizobj.FindComponentDef('BackEnd', self.config))

  def testProcessFormData_Delete_WithSubComponent(self):
    subcd = tracker_bizobj.MakeComponentDef(
        2, self.project.project_id, 'BackEnd>Worker', 'doc', False, [], [111],
        0, 122)
    self.config.component_defs.append(subcd)

    post_data = fake.PostData(
        name=['BackEnd'],
        deletecomponent=['Submit'])
    with self.assertRaises(permissions.PermissionException) as cm:
      self.servlet.ProcessFormData(self.mr, post_data)
    self.assertEquals('User tried to delete component that had subcomponents',
                      cm.exception.message)

  def testProcessFormData_Edit(self):
    post_data = fake.PostData(
        leaf_name=['BackEnd'],
        docstring=['This is where the magic happens'],
        deprecated=[True],
        admins=['a@example.com'],
        cc=['a@example.com'],
        labels=['Hot, Cold'])

    url = self.servlet.ProcessFormData(self.mr, post_data)

    self.mox.VerifyAll()
    self.assertTrue('/components/detail?component=BackEnd&saved=1&' in url)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)

    cd = tracker_bizobj.FindComponentDef('BackEnd', config)
    self.assertEqual('BackEnd', cd.path)
    self.assertEqual(
        'This is where the magic happens',
        cd.docstring)
    self.assertEqual(True, cd.deprecated)
    self.assertEqual([111], cd.admin_ids)
    self.assertEqual([111], cd.cc_ids)

  def testProcessDeleteComponent(self):
    self.servlet._ProcessDeleteComponent(self.mr, self.cd)
    self.assertIsNone(
        tracker_bizobj.FindComponentDef('BackEnd', self.config))

  def testProcessEditComponent(self):
    post_data = fake.PostData(
        leaf_name=['BackEnd'],
        docstring=['This is where the magic happens'],
        deprecated=[True],
        admins=['a@example.com'],
        cc=['a@example.com'],
        labels=['Hot, Cold'])

    self.servlet._ProcessEditComponent(
        self.mr, post_data, self.config, self.cd)

    self.mox.VerifyAll()
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)
    cd = tracker_bizobj.FindComponentDef('BackEnd', config)
    self.assertEqual('BackEnd', cd.path)
    self.assertEqual(
        'This is where the magic happens',
        cd.docstring)
    self.assertEqual(True, cd.deprecated)
    self.assertEqual([111], cd.admin_ids)
    self.assertEqual([111], cd.cc_ids)
    # Assert that creator and created were not updated.
    self.assertEqual(122, cd.creator_id)
    self.assertEqual(100000, cd.created)
    # Assert that modifier and modified were updated.
    self.assertEqual(122, cd.modifier_id)
    self.assertTrue(cd.modified > 10000000)

  def testProcessEditComponent_RenameWithSubComponents(self):
    subcd_1 = tracker_bizobj.MakeComponentDef(
        2, self.project.project_id, 'BackEnd>Worker1', 'doc', False, [], [111],
        0, 125, 3, 126)
    subcd_2 = tracker_bizobj.MakeComponentDef(
        3, self.project.project_id, 'BackEnd>Worker2', 'doc', False, [], [111],
        0, 125, 4, 127)
    self.config.component_defs.extend([subcd_1, subcd_2])

    self.mox.StubOutWithMock(filterrules_helpers, 'RecomputeAllDerivedFields')
    filterrules_helpers.RecomputeAllDerivedFields(
        self.mr.cnxn, self.services, self.mr.project, self.config)
    self.mox.ReplayAll()
    post_data = fake.PostData(
        leaf_name=['BackEnds'],
        docstring=['This is where the magic happens'],
        deprecated=[True],
        admins=['a@example.com'],
        cc=['a@example.com'],
        labels=[''])

    self.servlet._ProcessEditComponent(
        self.mr, post_data, self.config, self.cd)

    self.mox.VerifyAll()
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)
    cd = tracker_bizobj.FindComponentDef('BackEnds', config)
    self.assertEqual('BackEnds', cd.path)
    subcd_1 = tracker_bizobj.FindComponentDef('BackEnds>Worker1', config)
    self.assertEqual('BackEnds>Worker1', subcd_1.path)
    # Assert that creator and modifier have not changed for subcd_1.
    self.assertEqual(125, subcd_1.creator_id)
    self.assertEqual(0, subcd_1.created)
    self.assertEqual(126, subcd_1.modifier_id)
    self.assertEqual(3, subcd_1.modified)

    subcd_2 = tracker_bizobj.FindComponentDef('BackEnds>Worker2', config)
    self.assertEqual('BackEnds>Worker2', subcd_2.path)
    # Assert that creator and modifier have not changed for subcd_2.
    self.assertEqual(125, subcd_2.creator_id)
    self.assertEqual(0, subcd_2.created)
    self.assertEqual(127, subcd_2.modifier_id)
    self.assertEqual(4, subcd_2.modified)
