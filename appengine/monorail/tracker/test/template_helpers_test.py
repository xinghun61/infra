# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the template helpers module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
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
        1, 789, 'BackEnd', 'doc', False, [111], [], 100000, 222)

    self.services.user.TestAddUser('1@ex.com', 111)
    self.services.user.TestAddUser('2@ex.com', 222)
    self.services.user.TestAddUser('3@ex.com', 333)
    self.services.project.TestAddProjectMembers(
        [111], self.project, 'OWNER_ROLE')

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
    self.assertFalse(parsed.add_approvals)
    self.assertItemsEqual(parsed.phase_names, ['', '', '', '', '', ''])
    self.assertEqual(parsed.approvals_to_phase_idx, {})
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
        add_approvals=['on'],
        phase_0=['Canary'],
        phase_1=['Stable-Exp'],
        phase_2=['Stable'],
        phase_3=[''],
        phase_4=[''],
        phase_5=['Oops'],
        approval_3=['phase_2'],
        approval_4=['no_phase'],
        approval_3_required=['on'],
        approval_4_required=['on'],
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
    self.assertTrue(parsed.add_approvals)
    self.assertEqual(parsed.admin_str, 'jojwang@test.com, annajo@test.com')
    self.assertItemsEqual(parsed.phase_names,
                          ['Canary', 'Stable-Exp', 'Stable', '', '', 'Oops'])
    self.assertEqual(parsed.approvals_to_phase_idx, {3:2, 4:None})
    self.assertItemsEqual(parsed.required_approval_ids, [3, 4])

  def testGetTemplateInfoFromParsed_Normal(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    self.config.component_defs.append(self.cd_1)
    parsed = template_helpers.ParsedTemplate(
        'template', True, 'summary', True, 'content', 'Available',
        '1@ex.com', ['label1', 'label1'], {1: ['NO'], 2: ['MOOD']},
        ['BackEnd'], True, True, '2@ex.com', False, [], {}, [])
    (admin_ids, owner_id, component_ids,
     field_values, phases,
     approval_values) = template_helpers.GetTemplateInfoFromParsed(
        self.mr, self.services, parsed, self.config)
    self.assertEqual(admin_ids, [222])
    self.assertEqual(owner_id, 111)
    self.assertEqual(component_ids, [1])
    self.assertEqual(field_values[0].str_value, 'NO')
    self.assertEqual(field_values[1].str_value, 'MOOD')
    self.assertEqual(phases, [])
    self.assertEqual(approval_values, [])

  def testGetTemplateInfoFromParsed_Errors(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    parsed = template_helpers.ParsedTemplate(
        'template', True, 'summary', True, 'content', 'Available',
        '4@ex.com', ['label1', 'label1'], {1: ['NO'], 2: ['MOOD']},
        ['BackEnd'], True, True, '2@ex.com', False, [], {}, [])
    (admin_ids, _owner_id, _component_ids,
     field_values, phases,
     approval_values) = template_helpers.GetTemplateInfoFromParsed(
        self.mr, self.services, parsed, self.config)
    self.assertEqual(admin_ids, [222])
    self.assertEqual(field_values[0].str_value, 'NO')
    self.assertEqual(field_values[1].str_value, 'MOOD')
    self.assertEqual(self.mr.errors.owner, 'Owner not found.')
    self.assertEqual(self.mr.errors.components, 'Unknown component BackEnd')
    self.assertEqual(phases, [])
    self.assertEqual(approval_values, [])

  def testGetPhasesAndApprovalsFromParsed_Normal(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    self.config.approval_defs.extend([self.ad_3, self.ad_4, self.ad_5])

    phase_names = ['Canary', '', 'Stable-Exp', '', '', '']
    approvals_to_phase_idx = {3:0, 4:None, 5:2}
    required_approval_ids = [3, 5]

    phases, approval_values = template_helpers._GetPhasesAndApprovalsFromParsed(
        self.mr, phase_names, approvals_to_phase_idx, required_approval_ids)
    self.assertEqual(len(phases), 2)
    self.assertEqual(len(approval_values), 3)

    canary = tracker_bizobj.FindPhase('canary', phases)
    self.assertEqual(canary.rank, 0)
    av_3 = tracker_bizobj.FindApprovalValueByID(3, approval_values)
    self.assertEqual(av_3.status, tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    self.assertEqual(av_3.phase_id, canary.phase_id)

    av_4 = tracker_bizobj.FindApprovalValueByID(4, approval_values)
    self.assertEqual(av_4.status, tracker_pb2.ApprovalStatus.NOT_SET)
    self.assertIsNone(av_4.phase_id)

    stable_exp = tracker_bizobj.FindPhase('stable-exp', phases)
    self.assertEqual(stable_exp.rank, 2)
    av_5 = tracker_bizobj.FindApprovalValueByID(5, approval_values)
    self.assertEqual(av_5.status, tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    self.assertEqual(av_5.phase_id, stable_exp.phase_id)

    self.assertIsNone(self.mr.errors.phase_approvals)

  def testGetPhasesAndApprovalsFromParsed_Errors(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    self.config.approval_defs.extend([self.ad_3, self.ad_4, self.ad_5])
    required_approval_ids = []

    phase_names = ['Canary', 'Extra', 'Stable-Exp', '', '', '']
    approvals_to_phase_idx = {3:0, 4:None, 5:2}

    template_helpers._GetPhasesAndApprovalsFromParsed(
        self.mr, phase_names, approvals_to_phase_idx, required_approval_ids)
    self.assertEqual(self.mr.errors.phase_approvals,
                     'Defined gates must have assigned approvals.')

  def testGetPhasesAndApprovalsFromParsed_DupsErrors(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    self.config.approval_defs.extend([self.ad_3, self.ad_4, self.ad_5])
    required_approval_ids = []

    phase_names = ['Canary', 'canary', 'Stable-Exp', '', '', '']
    approvals_to_phase_idx = {3:0, 4:None, 5:2}

    template_helpers._GetPhasesAndApprovalsFromParsed(
        self.mr, phase_names, approvals_to_phase_idx, required_approval_ids)
    self.assertEqual(self.mr.errors.phase_approvals,
                     'Duplicate gate names.')

  def testGetPhasesAndApprovalsFromParsed_InvalidPhaseName(self):
    self.config.field_defs.extend([self.fd_1, self.fd_2])
    self.config.approval_defs.extend([self.ad_3, self.ad_4, self.ad_5])
    required_approval_ids = []

    phase_names = ['Canary', 'A B', 'Stable-Exp', '', '', '']
    approvals_to_phase_idx = {3:0, 4:None, 5:2}

    template_helpers._GetPhasesAndApprovalsFromParsed(
        self.mr, phase_names, approvals_to_phase_idx, required_approval_ids)
    self.assertEqual(self.mr.errors.phase_approvals,
                     'Invalid gate name(s).')

  def testGatherApprovalsPageData(self):
    self.fd_3.is_deleted = True
    self.config.field_defs = [self.fd_3, self.fd_4, self.fd_5]
    approval_values = [
        tracker_pb2.ApprovalValue(approval_id=3, phase_id=8),
        tracker_pb2.ApprovalValue(
            approval_id=4, phase_id=9,
            status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW),
        tracker_pb2.ApprovalValue(approval_id=5)
    ]
    tmpl_phases = [
        tracker_pb2.Phase(phase_id=8, rank=1, name='deletednoshow'),
        tracker_pb2.Phase(phase_id=9, rank=2, name='notdeleted')
    ]

    (prechecked_approvals, required_approval_ids,
     phases) = template_helpers.GatherApprovalsPageData(
         approval_values, tmpl_phases, self.config)
    self.assertItemsEqual(prechecked_approvals,
                          ['4_phase_0', '5'])
    self.assertEqual(required_approval_ids, [4])
    self.assertEqual(phases[0], tmpl_phases[1])
    self.assertIsNone(phases[1].name)
    self.assertEqual(len(phases), 6)

  def testGetCheckedApprovalsFromParsed(self):
    approvals_to_phase_idx = {23:0, 25:1, 26:None}
    checked = template_helpers.GetCheckedApprovalsFromParsed(
        approvals_to_phase_idx)
    self.assertItemsEqual(checked,
                          ['23_phase_0', '25_phase_1', '26'])
