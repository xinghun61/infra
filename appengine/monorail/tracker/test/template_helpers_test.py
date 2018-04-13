# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the template helpers module."""

import unittest

import settings

from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import template_helpers
from tracker import tracker_bizobj
from proto import tracker_pb2


class TemplateHelpers(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        config=fake.ConfigService(),
        project=fake.ProjectService(),
        usergroup=fake.UserGroupService())
    self.project = self.services.project.TestAddProject('proj')
    self.mr = testing_helpers.MakeMonorailRequest(
        project=self.project)
    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', self.project.project_id)
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
    self.fd_3 = tracker_bizobj.MakeFieldDef(
        3, 789, 'UXApproval', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for UX review', False)
    self.fd_4 = tracker_bizobj.MakeFieldDef(
        4, 789, 'TestApproval', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for Test review', False)
    self.fd_5 = tracker_bizobj.MakeFieldDef(
        5, 789, 'SomeApproval', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for Test review', False)
    self.ad_3 = tracker_pb2.ApprovalDef(approval_id=3)
    self.ad_4 = tracker_pb2.ApprovalDef(approval_id=4)
    self.ad_5 = tracker_pb2.ApprovalDef(approval_id=5)
    self.cd_1 = tracker_bizobj.MakeComponentDef(
        1, 789, 'BackEnd', 'doc', False, [111L], [], 100000, 222L)

    self.services.user.TestAddUser('1@ex.com', 111L)
    self.services.user.TestAddUser('2@ex.com', 222L)
    self.services.user.TestAddUser('3@ex.com', 333L)
    self.services.project.TestAddProjectMembers(
        [111L], self.project, 'OWNER_ROLE')

  def testParseTemplateRequest_Empty(self):
    post_data = fake.PostData()
    parsed = template_helpers.ParseTemplateRequest(post_data, self.config)
    self.assertEqual(parsed.name, '')
    self.assertFalse(parsed.members_only)
    self.assertEqual(parsed.summary, '')
    self.assertFalse(parsed.summary_must_be_edited)
    self.assertEqual(parsed.content, '')
    self.assertEqual(parsed.status, '')
    self.assertEqual(parsed.owner_str, '')
    self.assertEqual(parsed.labels, [])
    self.assertEqual(parsed.field_val_strs, {})
    self.assertEqual(parsed.component_paths, [])
    self.assertFalse(parsed.component_required)
    self.assertFalse(parsed.owner_defaults_to_member)
    self.assertFalse(parsed.add_phases)
    self.assertItemsEqual(parsed.phase_names, ['', '', '', '', '', ''])
    self.assertEqual(parsed.approvals_by_phase_idx, {})
    self.assertEqual(parsed.required_approval_ids, [])

  def testParseTemplateRequest_Normal(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    self.config.approval_defs.extend([self.ad_3, self.ad_4])
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
        owner_defaults_to_memeber=['no'],
        admin_names=['jojwang@test.com, annajo@test.com'],
        add_phases=['on'],
        phase_0=['Canary'],
        phase_1=['Stable-Exp'],
        phase_2=['Stable'],
        phase_3=[''],
        phase_4=[''],
        phase_5=['Oops'],
        approval_3=['phase_2'],
        approval_4=['phase_2'],
        approval_3_required=['on'],
        approval_4_required=['not-on'],
        # ignore required cb for omitted approvals
        approval_5_required=['on']
    )

    parsed = template_helpers.ParseTemplateRequest(post_data, self.config)
    self.assertEqual(parsed.name, 'sometemplate')
    self.assertTrue(parsed.members_only)
    self.assertEqual(parsed.summary, 'TLDR')
    self.assertTrue(parsed.summary_must_be_edited)
    self.assertEqual(parsed.content, 'HEY WHY')
    self.assertEqual(parsed.status, 'Accepted')
    self.assertEqual(parsed.owner_str, 'someone@world.com')
    self.assertEqual(parsed.labels, ['label-One', 'label-Two'])
    self.assertEqual(parsed.field_val_strs, {1: ['NO'], 2: ['MOOD']})
    self.assertEqual(parsed.component_paths, ['hey', 'hey2', 'he3'])
    self.assertTrue(parsed.component_required)
    self.assertFalse(parsed.owner_defaults_to_member)
    self.assertTrue(parsed.add_phases)
    self.assertEqual(parsed.admin_str, 'jojwang@test.com, annajo@test.com')
    self.assertItemsEqual(parsed.phase_names,
                          ['Canary', 'Stable-Exp', 'Stable', '', '', 'Oops'])
    self.assertEqual(parsed.approvals_by_phase_idx, {2:[3, 4]})
    self.assertEqual(parsed.required_approval_ids, [3])

  def testGetTemplateInfoFromParsed_Normal(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    self.config.component_defs.append(self.cd_1)
    parsed = template_helpers.ParsedTemplate(
        'template', True, 'summary', True, 'content', 'Available',
        '1@ex.com', ['label1', 'label1'], {1: ['NO'], 2: ['MOOD']},
        ['BackEnd'], True, True, '2@ex.com', False, [], {}, [])
    (admin_ids, owner_id, component_ids,
     field_values, phases) = template_helpers.GetTemplateInfoFromParsed(
        self.mr, self.services, parsed, self.config)
    self.assertEqual(admin_ids, [222L])
    self.assertEqual(owner_id, 111L)
    self.assertEqual(component_ids, [1])
    self.assertEqual(field_values[0].str_value, 'NO')
    self.assertEqual(field_values[1].str_value, 'MOOD')
    self.assertEqual(phases, [])

  def testGetTemplateInfoFromParsed_Errors(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    parsed = template_helpers.ParsedTemplate(
        'template', True, 'summary', True, 'content', 'Available',
        '4@ex.com', ['label1', 'label1'], {1: ['NO'], 2: ['MOOD']},
        ['BackEnd'], True, True, '2@ex.com', False, [], {}, [])
    (admin_ids, _owner_id, _component_ids,
     field_values, phases) = template_helpers.GetTemplateInfoFromParsed(
        self.mr, self.services, parsed, self.config)
    self.assertEqual(admin_ids, [222L])
    self.assertEqual(field_values[0].str_value, 'NO')
    self.assertEqual(field_values[1].str_value, 'MOOD')
    self.assertEqual(self.mr.errors.owner, 'Owner not found.')
    self.assertEqual(self.mr.errors.components, 'Unknown component BackEnd')
    self.assertEqual(phases, [])

  def testGetPhasesFromParsed_Normal(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    self.config.approval_defs.extend([self.ad_3, self.ad_4, self.ad_5])

    phase_names = ['Canary', '', 'Stable-Exp', '', '', '']
    approvals_by_phase_idx = {0: [3, 4], 2: [5]}
    required_approval_ids = [3, 5]

    phases = template_helpers._GetPhasesFromParsed(
        self.mr, phase_names, approvals_by_phase_idx, required_approval_ids)
    self.assertEqual(len(phases), 2)

    canary = tracker_bizobj.FindPhase('canary', phases)
    self.assertEqual(canary.rank, 0)
    av_3 = tracker_bizobj.FindApprovalValueByID(3, canary.approval_values)
    self.assertEqual(av_3.status, tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    av_4 = tracker_bizobj.FindApprovalValueByID(4, canary.approval_values)
    self.assertEqual(av_4.status, tracker_pb2.ApprovalStatus.NOT_SET)

    stable_exp = tracker_bizobj.FindPhase('stable-exp', phases)
    self.assertEqual(stable_exp.rank, 2)
    av_5 = tracker_bizobj.FindApprovalValueByID(5, stable_exp.approval_values)
    self.assertEqual(av_5.status, tracker_pb2.ApprovalStatus.NEEDS_REVIEW)

    self.assertIsNone(self.mr.errors.phase_approvals)

  def testGetPhasesFromParsed_Errors(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    self.config.approval_defs.extend([self.ad_3, self.ad_4, self.ad_5])
    required_approval_ids = []

    phase_names = ['Canary', 'Extra', 'Stable-Exp', '', '', '']
    approvals_by_phase_idx = {0: [self.ad_3, self.ad_4], 2: [self.ad_5]}

    template_helpers._GetPhasesFromParsed(
        self.mr, phase_names, approvals_by_phase_idx, required_approval_ids)
    self.assertEqual(self.mr.errors.phase_approvals,
                     'Defined gates must have assigned approvals.')

  def testGetPhasesFromParsed_DupsErrors(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    self.config.approval_defs.extend([self.ad_3, self.ad_4, self.ad_5])
    required_approval_ids = []

    phase_names = ['Canary', 'canary', 'Stable-Exp', '', '', '']
    approvals_by_phase_idx = {0: [self.ad_3, self.ad_4], 2: [self.ad_5]}

    template_helpers._GetPhasesFromParsed(
        self.mr, phase_names, approvals_by_phase_idx, required_approval_ids)
    self.assertEqual(self.mr.errors.phase_approvals,
                     'Duplicate gate names.')
