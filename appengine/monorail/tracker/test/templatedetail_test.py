# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for Template editing/viewing servlet."""

import mox
import logging
import unittest
import settings

from third_party import ezt

from framework import permissions
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import templatedetail
from tracker import tracker_bizobj
from proto import tracker_pb2


class TemplateDetailTest(unittest.TestCase):
  """Tests for the TemplateDetail servlet."""

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(project=fake.ProjectService(),
                                             config=fake.ConfigService(),
                                             usergroup=fake.UserGroupService(),
                                             user=fake.UserService())
    self.servlet = templatedetail.TemplateDetail('req', 'res',
                                               services=self.services)

    self.services.user.TestAddUser('gatsby@example.com', 111L)
    self.services.user.TestAddUser('sport@example.com', 222L)
    self.services.user.TestAddUser('gatsby@example.com', 111L)
    self.services.user.TestAddUser('daisy@example.com', 333L)

    self.project = self.services.project.TestAddProject('proj')
    self.services.project.TestAddProjectMembers(
        [333L], self.project, 'CONTRIBUTOR_ROLE')

    self.template = self.test_template = tracker_bizobj.MakeIssueTemplate(
        'TestTemplate', 'sum', 'New', 111L, 'content', ['label1', 'label2'],
        [], [222L], [], summary_must_be_edited=True,
        owner_defaults_to_member=True, component_required=False,
        members_only=False)
    self.template.template_id = 12345

    self.mr = testing_helpers.MakeMonorailRequest(project=self.project)
    self.mr.template_name = 'TestTemplate'

    self.mox = mox.Mox()

    self.fd_1 =  tracker_bizobj.MakeFieldDef(
        1, 789, 'UXReview', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for UX review', False)
    self.fd_2 =  tracker_bizobj.MakeFieldDef(
        2, 789, 'UXReview', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for UX review', False)
    self.cd_1 = tracker_bizobj.MakeComponentDef(
        1, 789, 'BackEnd', 'doc', False, [111L], [], 100000, 222L)
    self.template.component_ids.append(1)

    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', self.project.project_id)
    self.config.templates.append(self.template)
    self.config.component_defs.append(self.cd_1)
    self.services.config.StoreConfig(None, self.config)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testAssertBasePermission_Anyone(self):
    self.mr.auth.effective_ids = {222L}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.auth.effective_ids = {333L}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

  def testAssertBasePermision_MembersOnly(self):
    self.template.members_only = True
    self.mr.auth.effective_ids = {222L}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.auth.effective_ids = {333L}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.auth.effective_ids = {444L}
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

  def testGatherPageData(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_TEMPLATES,
                     page_data['admin_tab_mode'])
    self.assertTrue(page_data['allow_edit'])
    self.assertFalse(page_data['new_template_form'])
    self.assertFalse(page_data['initial_members_only'])
    self.assertEqual(page_data['template_name'], 'TestTemplate')
    self.assertEqual(page_data['initial_summary'], 'sum')
    self.assertTrue(page_data['initial_must_edit_summary'])
    self.assertEqual(page_data['initial_content'], 'content')
    self.assertEqual(page_data['initial_status'], 'New')
    self.assertEqual(page_data['initial_owner'], 'gatsby@example.com')
    self.assertTrue(page_data['initial_owner_defaults_to_member'])
    self.assertEqual(page_data['initial_components'], 'BackEnd')
    self.assertFalse(page_data['initial_component_required'])
    self.assertItemsEqual(page_data['labels'], ['label1', 'label2'])
    self.assertEqual(page_data['initial_admins'], 'sport@example.com')

  def testProcessFormData_Reject(self):
    post_data = fake.PostData(
      name=['TestTemplate'],
      members_only=['on'],
      summary=['TLDR'],
      summary_must_be_edited=['on'],
      content=['HEY WHY'],
      status=['Accepted'],
      owner=['someone@world.com'],
      label=['label-One', 'label-Two'],
      custom_1=['NO'],
      custom_2=['MOOD'],
      components=['hey, hey2,he3'],
      component_required=['on'],
      owner_defaults_to_member=['no']
    )

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        self.mr,
        initial_members_only=ezt.boolean(True),
        template_name='TestTemplate',
        initial_summary='TLDR',
        initial_must_edit_summary=ezt.boolean(True),
        initial_content='HEY WHY',
        initial_status='Accepted',
        initial_owner='someone@world.com',
        initial_owner_defaults_to_member=ezt.boolean(False),
        initial_components='hey, hey2, he3',
        initial_component_required=ezt.boolean(True),
        initial_admins='',
        labels=['label-One', 'label-Two'],
        fields=mox.IgnoreArg()
        )
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Owner not found.', self.mr.errors.owner)
    self.assertEqual('Unknown component he3', self.mr.errors.components)
    self.assertIsNone(url)

  def testProcessFormData_Accept(self):
    self.config.field_defs.append(self.fd_1)
    self.config.field_defs.append(self.fd_2)
    self.config.component_defs.append(self.cd_1)
    self.services.config.StoreConfig(None, self.config)
    post_data = fake.PostData(
      name=['TestTemplate'],
      members_only=['on'],
      summary=['TLDR'],
      summary_must_be_edited=[''],
      content=['HEY WHY'],
      status=['Accepted'],
      owner=['daisy@example.com'],
      label=['label-One', 'label-Two'],
      custom_1=['NO'],
      custom_2=['MOOD'],
      components=['BackEnd'],
      component_required=['on'],
      owner_defaults_to_member=['on']
    )
    url = self.servlet.ProcessFormData(self.mr, post_data)
    template = tracker_bizobj.FindIssueTemplate('TestTemplate', self.config)
    self.assertEqual(template.summary, 'TLDR')
    self.assertEqual(template.content, 'HEY WHY')
    self.assertEqual(template.status, 'Accepted')
    self.assertEqual(template.owner_id, 333L)
    self.assertEqual(template.labels, ['label-One', 'label-Two'])
    self.assertItemsEqual(template.field_values[0].str_value, 'NO')
    self.assertTrue(template.members_only)
    self.assertFalse(template.summary_must_be_edited)
    self.assertTrue(template.component_required)
    self.assertTrue(template.owner_defaults_to_member)
    self.assertTrue('/templates/detail?saved=1&template=TestTemplate&' in url)

  def testProcessFormData_Delete(self):
     post_data = fake.PostData(
         deletetemplate=['Submit'],
         name=['TestTemplate'],
         members_only=['on'],
     )
     url=self.servlet.ProcessFormData(self.mr, post_data)
     template = tracker_bizobj.FindIssueTemplate('TestTemplate', self.config)
     self.assertIsNone(template)
     self.assertTrue('/adminTemplates?deleted=1&ts=' in url)
