# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit test for Template creation servlet."""

import mox
import unittest
import settings

from third_party import ezt

from framework import permissions
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import templatecreate
from tracker import tracker_bizobj
from tracker import tracker_views
from proto import tracker_pb2


class TemplateCreateTest(unittest.TestCase):
  """Tests for the TemplateCreate servlet."""

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(project=fake.ProjectService(),
                                             config=fake.ConfigService(),
                                             user=fake.UserService())
    self.servlet = templatecreate.TemplateCreate('req', 'res',
                                               services=self.services)
    self.project = self.services.project.TestAddProject('proj')
    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', self.project.project_id)
    first_tmpl = tracker_bizobj.MakeIssueTemplate(
        'sometemplate', 'summary', None, None, 'content', [], [], [],
        [])
    self.config.templates.append(first_tmpl)
    self.services.config.StoreConfig(None, self.config)
    self.mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testAssertBasePermission(self):
    # Anon users can never do it
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

    # Project owner can do it.
    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

    # Project member cannot do it
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

  def testGatherPageData(self):
    fd = tracker_bizobj.MakeFieldDef(
        1, self.mr.project_id, 'StringFieldName',
        tracker_pb2.FieldTypes.STR_TYPE, None, '', False,
        False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'some approval thing', False)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)
    config.field_defs.append(fd)
    self.services.config.StoreConfig(self.cnxn, config)
    fv = tracker_views.MakeFieldValueView(fd, config, [], [], [], {})

    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_TEMPLATES,
                     page_data['admin_tab_mode'])
    self.assertTrue(page_data['allow_edit'])
    self.assertTrue(page_data['new_template_form'])
    self.assertFalse(page_data['initial_members_only'])
    self.assertEqual(page_data['template_name'], '')
    self.assertEqual(page_data['initial_summary'], '')
    self.assertFalse(page_data['initial_must_edit_summary'])
    self.assertEqual(page_data['initial_content'], '')
    self.assertEqual(page_data['initial_status'], '')
    self.assertEqual(page_data['initial_owner'], '')
    self.assertFalse(page_data['initial_owner_defaults_to_member'])
    self.assertEqual(page_data['initial_components'], '')
    self.assertFalse(page_data['initial_component_required'])
    self.assertEqual(page_data['fields'][0].field_name, fv.field_name)
    self.assertEqual(page_data['initial_admins'], '')

  def testProcessFormData_Reject(self):
    fd_1 = tracker_bizobj.MakeFieldDef(
        1, 789, 'UXApproval', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for UX review', False)
    fd_2 = tracker_bizobj.MakeFieldDef(
        2, 789, 'TestApproval', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for Test review', False)
    ad_1 = tracker_pb2.ApprovalDef(approval_id=1)
    ad_2 = tracker_pb2.ApprovalDef(approval_id=2)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)
    config.field_defs.extend([fd_1, fd_2])
    config.approval_defs.extend([ad_1, ad_2])
    self.services.config.StoreConfig(self.cnxn, config)
    post_data = fake.PostData(
      name=['sometemplate'],
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
      owner_defaults_to_member=['no'],
      add_phases = ['on'],
      phase_0=['Canary'],
      phase_1=['Stable-Exp'],
      phase_2=['Stable'],
      phase_3=[''],
      phase_4=[''],
      phase_5=[''],
      approval_1=['phase_1'],
      approval_2=['phase_2']
    )

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        self.mr,
        initial_members_only=ezt.boolean(True),
        template_name='sometemplate',
        initial_content='TLDR',
        initial_must_edit_summary=ezt.boolean(True),
        initial_description='HEY WHY',
        initial_status='Accepted',
        initial_owner='someone@world.com',
        initial_owner_defaults_to_member=ezt.boolean(False),
        initial_components='hey, hey2, he3',
        initial_component_required=ezt.boolean(True),
        initial_admins='',
        labels=['label-One', 'label-Two'],
        fields=mox.IgnoreArg(),
        initial_add_phases=ezt.boolean(True),
        initial_phases=[tracker_pb2.Phase(name=name) for
                        name in ['Canary', 'Stable-Exp', 'Stable', '', '', '']],
        approvals=mox.IgnoreArg(),
        prechecked_approvals=['1_phase_1', '2_phase_2'],
        )
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Owner not found.', self.mr.errors.owner)
    self.assertEqual('Unknown component he3', self.mr.errors.components)
    self.assertEqual(
        'Template with name sometemplate already exists', self.mr.errors.name)
    self.assertEqual('Defined gates must have assigned approvals.',
                     self.mr.errors.phase_approvals)
    self.assertIsNone(url)

  def testProcessFormData_Accept(self):
    fd_1 = tracker_bizobj.MakeFieldDef(
        1, self.mr.project_id, 'UXReview', tracker_pb2.FieldTypes.STR_TYPE,
        None, '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'First field', False)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)
    config.field_defs.append(fd_1)
    self.services.config.StoreConfig(self.cnxn, config)
    post_data = fake.PostData(
        name=['secondtemplate'],
        members_only=['on'],
        summary=['TLDR'],
        summary_must_be_edited=['on'],
        content=['HEY WHY'],
        status=['Accepted'],
        label=['label-One', 'label-Two'],
        custom_1=['NO'],
        component_required=['on'],
        owner_defaults_to_member=['no'])

    url = self.servlet.ProcessFormData(self.mr, post_data)

    template = None
    for tmpl in config.templates:
      if tmpl.name == 'secondtemplate':
        template = tmpl
    self.assertEqual(template.summary, 'TLDR')
    self.assertEqual(template.content, 'HEY WHY')
    self.assertItemsEqual(template.labels, ['label-One', 'label-Two'])
    self.assertItemsEqual(template.field_values[0].str_value, 'NO')
    self.assertTrue('/adminTemplates?saved=1&ts' in url)
