# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for converting internal protorpc to external protoc."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from mock import Mock, patch
import unittest

from google.protobuf import wrappers_pb2

import settings
from api import converters
from api.api_proto import common_pb2
from api.api_proto import features_objects_pb2
from api.api_proto import issue_objects_pb2
from api.api_proto import project_objects_pb2
from api.api_proto import user_objects_pb2
from framework import exceptions
from framework import permissions
from proto import tracker_pb2
from proto import user_pb2
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj
from services import features_svc
from services import service_manager


class ConverterFunctionsTest(unittest.TestCase):

  NOW = 1234567890

  def setUp(self):
    self.users_by_id = {
        111: testing_helpers.Blank(
            display_name='one@example.com', email='one@example.com',
            banned=False),
        222: testing_helpers.Blank(
            display_name='two@example.com', email='two@example.com',
            banned=False),
        333: testing_helpers.Blank(
            display_name='ban...@example.com', email='banned@example.com',
            banned=True),
        }

    self.services = service_manager.Services(
        issue=fake.IssueService(),
        project=fake.ProjectService(),
        user=fake.UserService(),
        features=fake.FeaturesService())
    self.cnxn = fake.MonorailConnection()
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789)
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

    self.fd_1 = tracker_pb2.FieldDef(
        field_name='FirstField', field_id=1,
        field_type=tracker_pb2.FieldTypes.STR_TYPE,
        applicable_type='')
    self.fd_2 = tracker_pb2.FieldDef(
        field_name='SecField', field_id=2,
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        applicable_type='')
    self.fd_3 = tracker_pb2.FieldDef(
        field_name='LegalApproval', field_id=3,
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE,
        applicable_type='')
    self.fd_4 = tracker_pb2.FieldDef(
        field_name='UserField', field_id=4,
        field_type=tracker_pb2.FieldTypes.USER_TYPE,
        applicable_type='')
    self.fd_5 = tracker_pb2.FieldDef(
        field_name='Pre', field_id=5,
        field_type=tracker_pb2.FieldTypes.ENUM_TYPE,
        applicable_type='')
    self.fd_6 = tracker_pb2.FieldDef(
        field_name='PhaseField', field_id=6,
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        applicable_type='', is_phase_field=True)
    self.fd_7 = tracker_pb2.FieldDef(
        field_name='ApprovalEnum', field_id=7,
        field_type=tracker_pb2.FieldTypes.ENUM_TYPE,
        applicable_type='', approval_id=self.fd_3.field_id)

    self.services.user.TestAddUser('owner@example.com', 111)
    self.services.user.TestAddUser('editor@example.com', 222)
    self.issue_1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj')
    self.issue_2 = fake.MakeTestIssue(
        789, 2, 'sum', 'New', 111, project_name='proj')
    self.services.issue.TestAddIssue(self.issue_1)
    self.services.issue.TestAddIssue(self.issue_2)

  def testConvertApprovalValues_Empty(self):
    """We handle the case where an issue has no approval values."""
    actual = converters.ConvertApprovalValues([], [], {}, self.config)
    self.assertEqual([], actual)

  def testConvertApprovalValues_Normal(self):
    """We can convert a list of approval values."""
    now = 1234567890
    self.config.field_defs.append(tracker_pb2.FieldDef(
        field_id=1, project_id=789, field_name='EstDays',
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        applicable_type=''))
    self.config.field_defs.append(tracker_pb2.FieldDef(
        field_id=11, project_id=789, field_name='Accessibility',
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE,
        applicable_type='Launch'))
    self.config.approval_defs.append(tracker_pb2.ApprovalDef(
        approval_id=11, approver_ids=[111], survey='survey 1'))
    self.config.approval_defs.append(tracker_pb2.ApprovalDef(
        approval_id=12, approver_ids=[111], survey='survey 2'))
    av_11 = tracker_pb2.ApprovalValue(
        approval_id=11, status=tracker_pb2.ApprovalStatus.NEED_INFO,
        setter_id=111, set_on=now, approver_ids=[111, 222],
        phase_id=21)
    # Note: no approval def, no phase, so it won't be returned.
    # TODO(ehmaldonado): Figure out support for "foreign" fields.
    av_12 = tracker_pb2.ApprovalValue(
        approval_id=12, status=tracker_pb2.ApprovalStatus.NOT_SET,
        setter_id=111, set_on=now, approver_ids=[111])
    phase_21 = tracker_pb2.Phase(phase_id=21, name='Stable', rank=1)
    actual = converters.ConvertApprovalValues(
        [av_11, av_12], [phase_21], self.users_by_id, self.config)

    expected_av_1 = issue_objects_pb2.Approval(
        field_ref=common_pb2.FieldRef(
            field_id=11,
            field_name='Accessibility',
            type=common_pb2.APPROVAL_TYPE),
        approver_refs=[
            common_pb2.UserRef(user_id=111, display_name='one@example.com'),
            common_pb2.UserRef(user_id=222, display_name='two@example.com'),
            ],
        status=issue_objects_pb2.NEED_INFO,
        set_on=now,
        setter_ref=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        phase_ref=issue_objects_pb2.PhaseRef(phase_name='Stable'))

    self.assertEqual([expected_av_1], actual)

  def testConvertApproval(self):
    """We can convert ApprovalValues to protoc Approvals."""
    approval_value = tracker_pb2.ApprovalValue(
        approval_id=3,
        status=tracker_pb2.ApprovalStatus.NEED_INFO,
        setter_id=222,
        set_on=2345,
        approver_ids=[111],
        phase_id=1
    )

    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3]

    phase = tracker_pb2.Phase(phase_id=1, name='Canary')

    actual = converters.ConvertApproval(
        approval_value, self.users_by_id, self.config, phase=phase)
    expected = issue_objects_pb2.Approval(
        field_ref=common_pb2.FieldRef(
            field_id=3,
            field_name='LegalApproval',
            type=common_pb2.APPROVAL_TYPE),
        approver_refs=[common_pb2.UserRef(
            user_id=111, display_name='one@example.com', is_derived=False)
          ],
        status=5,
        set_on=2345,
        setter_ref=common_pb2.UserRef(
            user_id=222, display_name='two@example.com', is_derived=False
        ),
        phase_ref=issue_objects_pb2.PhaseRef(phase_name='Canary')
    )

    self.assertEqual(expected, actual)

  def testConvertApproval_NonExistentApproval(self):
    approval_value = tracker_pb2.ApprovalValue(
        approval_id=3,
        status=tracker_pb2.ApprovalStatus.NEED_INFO,
        setter_id=222,
        set_on=2345,
        approver_ids=[111],
        phase_id=1
    )
    phase = tracker_pb2.Phase(phase_id=1, name='Canary')
    self.assertIsNone(converters.ConvertApproval(
        approval_value, self.users_by_id, self.config, phase=phase))


  def testConvertApprovalStatus(self):
    """We can convert a protorpc ApprovalStatus to a protoc ApprovalStatus."""
    actual = converters.ConvertApprovalStatus(
        tracker_pb2.ApprovalStatus.REVIEW_REQUESTED)
    self.assertEqual(actual, issue_objects_pb2.REVIEW_REQUESTED)

    actual = converters.ConvertApprovalStatus(
        tracker_pb2.ApprovalStatus.NOT_SET)
    self.assertEqual(actual, issue_objects_pb2.NOT_SET)

  def testConvertUserRef(self):
    """We can convert user IDs to a UserRef."""
    # No specified user
    actual = converters.ConvertUserRef(None, None, self.users_by_id)
    expected = common_pb2.UserRef(
        user_id=0, is_derived=False, display_name='----')
    self.assertEqual(expected, actual)

    # Explicitly specified user
    actual = converters.ConvertUserRef(111, None, self.users_by_id)
    expected = common_pb2.UserRef(
        user_id=111, is_derived=False, display_name='one@example.com')
    self.assertEqual(expected, actual)

    # Derived user
    actual = converters.ConvertUserRef(None, 111, self.users_by_id)
    expected = common_pb2.UserRef(
        user_id=111, is_derived=True, display_name='one@example.com')
    self.assertEqual(expected, actual)

  def testConvertUserRefs(self):
    """We can convert lists of user_ids into UserRefs."""
    # No specified users
    actual = converters.ConvertUserRefs(
        [], [], self.users_by_id, False)
    expected = []
    self.assertEqual(expected, actual)

    # A mix of explicit and derived users
    actual = converters.ConvertUserRefs(
        [111], [222], self.users_by_id, False)
    expected = [
      common_pb2.UserRef(
          user_id=111, is_derived=False, display_name='one@example.com'),
      common_pb2.UserRef(
          user_id=222, is_derived=True, display_name='two@example.com'),
      ]
    self.assertEqual(expected, actual)

    # Use display name
    actual = converters.ConvertUserRefs([333], [], self.users_by_id, False)
    self.assertEqual(
      [common_pb2.UserRef(
           user_id=333, is_derived=False, display_name='ban...@example.com')],
      actual)

    # Use email
    actual = converters.ConvertUserRefs([333], [], self.users_by_id, True)
    self.assertEqual(
      [common_pb2.UserRef(
           user_id=333, is_derived=False, display_name='banned@example.com')],
      actual)

  @patch('time.time')
  def testConvertUsers(self, mock_time):
    """We can convert lists of protorpc Users to protoc Users."""
    mock_time.return_value = self.NOW
    user1 = user_pb2.User(
        user_id=1, email='user1@example.com', last_visit_timestamp=self.NOW)
    user2 = user_pb2.User(
        user_id=2, email='user2@example.com', is_site_admin=True,
        last_visit_timestamp=self.NOW)
    user3 = user_pb2.User(
        user_id=3, email='user3@example.com',
        linked_child_ids=[4])
    user4 = user_pb2.User(
        user_id=4, email='user4@example.com', last_visit_timestamp=1,
        linked_parent_id=3)
    users_by_id = {
        3: testing_helpers.Blank(
            display_name='user3@example.com', email='user3@example.com',
            banned=False),
        4: testing_helpers.Blank(
            display_name='user4@example.com', email='user4@example.com',
            banned=False),
        }

    actual = converters.ConvertUsers(
        [user1, user2, user3, user4], users_by_id)
    self.assertItemsEqual(
        actual,
        [user_objects_pb2.User(
            user_id=1,
            email='user1@example.com',
            display_name='user1@example.com'),
         user_objects_pb2.User(
            user_id=2,
            email='user2@example.com',
            display_name='user2@example.com',
            is_site_admin=True),
         user_objects_pb2.User(
            user_id=3,
            email='user3@example.com',
            display_name='user3@example.com',
            availability='User never visited',
            linked_child_refs=[common_pb2.UserRef(
              user_id=4, display_name='user4@example.com')]),
         user_objects_pb2.User(
            user_id=4,
            email='user4@example.com',
            display_name='user4@example.com',
            availability='Last visit > 30 days ago',
            linked_parent_ref=common_pb2.UserRef(
              user_id=3, display_name='user3@example.com')),
         ])

  def testConvetPrefValues(self):
    """We can convert a list of UserPrefValues from protorpc to protoc."""
    self.assertEqual(
        [],
        converters.ConvertPrefValues([]))

    userprefvalues = [
        user_pb2.UserPrefValue(name='foo_1', value='bar_1'),
        user_pb2.UserPrefValue(name='foo_2', value='bar_2')]
    actual = converters.ConvertPrefValues(userprefvalues)
    expected = [
        user_objects_pb2.UserPrefValue(name='foo_1', value='bar_1'),
        user_objects_pb2.UserPrefValue(name='foo_2', value='bar_2')]
    self.assertEqual(expected, actual)

  def testConvertLabels(self):
    """We can convert labels."""
    # No labels specified
    actual = converters.ConvertLabels([], [])
    self.assertEqual([], actual)

    # A mix of explicit and derived labels
    actual = converters.ConvertLabels(
        ['Milestone-66'], ['Restrict-View-CoreTeam'])
    expected = [
        common_pb2.LabelRef(label='Milestone-66', is_derived=False),
        common_pb2.LabelRef(label='Restrict-View-CoreTeam', is_derived=True),
        ]
    self.assertEqual(expected, actual)

  def testConvertComponentRef(self):
    """We can convert a component ref."""
    self.config.component_defs = [
        tracker_pb2.ComponentDef(component_id=1, path='UI'),
        tracker_pb2.ComponentDef(component_id=2, path='DB')]

    self.assertEqual(
        common_pb2.ComponentRef(
            path='UI',
            is_derived=False),
        converters.ConvertComponentRef(1, self.config))

    self.assertEqual(
        common_pb2.ComponentRef(
            path='DB',
            is_derived=True),
        converters.ConvertComponentRef(2, self.config, True))

    self.assertIsNone(
        converters.ConvertComponentRef(3, self.config, True))

  def testConvertComponents(self):
    """We can convert a list of components."""
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI'),
      tracker_pb2.ComponentDef(component_id=2, path='DB'),
      ]

    # No components specified
    actual = converters.ConvertComponents([], [], self.config)
    self.assertEqual([], actual)

    # A mix of explicit, derived, and non-existing components
    actual = converters.ConvertComponents([1, 4], [2, 3], self.config)
    expected = [
        common_pb2.ComponentRef(path='UI', is_derived=False),
        common_pb2.ComponentRef(path='DB', is_derived=True),
        ]
    self.assertEqual(expected, actual)

  def testConvertIssueRef(self):
    """We can convert a pair (project_name, local_id) to an IssueRef."""
    actual = converters.ConvertIssueRef(('proj', 1))
    self.assertEqual(
        common_pb2.IssueRef(project_name='proj', local_id=1),
        actual)

  def testConvertIssueRef_ExtIssue(self):
    """ConvertIssueRef successfully converts an external issue."""
    actual = converters.ConvertIssueRef(('', 0), ext_id='b/1234567')
    self.assertEqual(
        common_pb2.IssueRef(project_name='', local_id=0,
            ext_identifier='b/1234567'),
        actual)

  def testConvertIssueRefs(self):
    """We can convert issue_ids to IssueRefs."""
    related_refs_dict = {
        78901: ('proj', 1),
        78902: ('proj', 2),
        }
    actual = converters.ConvertIssueRefs([78901, 78902], related_refs_dict)
    self.assertEqual(
        [common_pb2.IssueRef(project_name='proj', local_id=1),
         common_pb2.IssueRef(project_name='proj', local_id=2)],
        actual)

  def testConvertFieldType(self):
    self.assertEqual(
        common_pb2.STR_TYPE,
        converters.ConvertFieldType(tracker_pb2.FieldTypes.STR_TYPE))

    self.assertEqual(
        common_pb2.URL_TYPE,
        converters.ConvertFieldType(tracker_pb2.FieldTypes.URL_TYPE))

  def testConvertFieldRef(self):
    actual = converters.ConvertFieldRef(
        1, 'SomeName', tracker_pb2.FieldTypes.ENUM_TYPE, None)
    self.assertEqual(
        actual,
        common_pb2.FieldRef(
            field_id=1,
            field_name='SomeName',
            type=common_pb2.ENUM_TYPE))

  def testConvertFieldValue(self):
    """We can convert one FieldValueView item to a protoc FieldValue."""
    actual = converters.ConvertFieldValue(
        1, 'Size', 123, tracker_pb2.FieldTypes.INT_TYPE, phase_name='Canary')
    expected = issue_objects_pb2.FieldValue(
        field_ref=common_pb2.FieldRef(
            field_id=1,
            field_name='Size',
            type=common_pb2.INT_TYPE),
        value='123',
        phase_ref=issue_objects_pb2.PhaseRef(phase_name='Canary'))
    self.assertEqual(expected, actual)

    actual = converters.ConvertFieldValue(
        1, 'Size', 123, tracker_pb2.FieldTypes.INT_TYPE, 'Legal', '',
        is_derived=True)
    expected = issue_objects_pb2.FieldValue(
        field_ref=common_pb2.FieldRef(
            field_id=1,
            field_name='Size',
            type=common_pb2.INT_TYPE,
            approval_name='Legal'),
        value='123',
        is_derived=True)
    self.assertEqual(expected, actual)

  def testConvertFieldValue_Unicode(self):
    """We can convert one FieldValueView unicode item to a protoc FieldValue."""
    actual = converters.ConvertFieldValue(
        1, 'Size', u'\xe2\x9d\xa4\xef\xb8\x8f',
        tracker_pb2.FieldTypes.STR_TYPE, phase_name='Canary')
    expected = issue_objects_pb2.FieldValue(
        field_ref=common_pb2.FieldRef(
            field_id=1,
            field_name='Size',
            type=common_pb2.STR_TYPE),
        value=u'\xe2\x9d\xa4\xef\xb8\x8f',
        phase_ref=issue_objects_pb2.PhaseRef(phase_name='Canary'))
    self.assertEqual(expected, actual)

  def testConvertFieldValues(self):
    self.fd_2.approval_id = 3
    self.config.field_defs = [
        self.fd_1, self.fd_2, self.fd_3, self.fd_4, self.fd_5]
    fv_1 = tracker_bizobj.MakeFieldValue(
        1, None, 'string', None, None, None, False)
    fv_2 = tracker_bizobj.MakeFieldValue(
        2, 34, None, None, None, None, False)
    fv_3 = tracker_bizobj.MakeFieldValue(
        111, None, 'value', None, None, None, False)
    labels = ['Pre-label', 'not-label-enum', 'prenot-label']
    der_labels =  ['Pre-label2']
    phases = [tracker_pb2.Phase(name='Canary', phase_id=17)]
    fv_1.phase_id=17

    actual = converters.ConvertFieldValues(
        self.config, labels, der_labels, [fv_1, fv_2, fv_3], {}, phases=phases)

    self.maxDiff = None
    expected = [
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(
              field_id=1,
              field_name='FirstField',
              type=common_pb2.STR_TYPE),
          value='string',
          phase_ref=issue_objects_pb2.PhaseRef(phase_name='Canary')),
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(
              field_id=2,
              field_name='SecField',
              type=common_pb2.INT_TYPE,
              approval_name='LegalApproval'),
          value='34'),
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(
              field_id=5, field_name='Pre', type=common_pb2.ENUM_TYPE),
          value='label'),
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(
              field_id=5, field_name='Pre', type=common_pb2.ENUM_TYPE),
          value='label2', is_derived=True),
      ]
    self.assertItemsEqual(expected, actual)

  def testConvertIssue(self):
    """We can convert a protorpc Issue to a protoc Issue."""
    related_refs_dict = {
        78901: ('proj', 1),
        78902: ('proj', 2),
        }
    now = 12345678
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI'),
      tracker_pb2.ComponentDef(component_id=2, path='DB'),
      ]
    issue = fake.MakeTestIssue(
      789, 3, 'sum', 'New', 111, labels=['Hot'],
      derived_labels=['Scalability'], star_count=12, reporter_id=222,
      opened_timestamp=now, component_ids=[1], project_name='proj',
      cc_ids=[111], derived_cc_ids=[222])
    issue.phases = [
        tracker_pb2.Phase(phase_id=1, name='Dev', rank=1),
        tracker_pb2.Phase(phase_id=2, name='Beta', rank=2),
        ]
    issue.dangling_blocked_on_refs = [
        tracker_pb2.DanglingIssueRef(project='dangling_proj', issue_id=1234)]
    issue.dangling_blocking_refs = [
        tracker_pb2.DanglingIssueRef(project='dangling_proj', issue_id=5678)]

    actual = converters.ConvertIssue(
        issue, self.users_by_id, related_refs_dict, self.config)

    expected = issue_objects_pb2.Issue(
        project_name='proj',
        local_id=3,
        summary='sum',
        status_ref=common_pb2.StatusRef(
            status='New',
            is_derived=False,
            means_open=True),
        owner_ref=common_pb2.UserRef(
            user_id=111,
            display_name='one@example.com',
            is_derived=False),
        cc_refs=[
            common_pb2.UserRef(
                user_id=111,
                display_name='one@example.com',
                is_derived=False),
            common_pb2.UserRef(
                user_id=222,
                display_name='two@example.com',
                is_derived=True)],
        label_refs=[
            common_pb2.LabelRef(label='Hot', is_derived=False),
            common_pb2.LabelRef(label='Scalability', is_derived=True)],
        component_refs=[common_pb2.ComponentRef(path='UI', is_derived=False)],
        is_deleted=False,
        reporter_ref=common_pb2.UserRef(
            user_id=222, display_name='two@example.com', is_derived=False),
        opened_timestamp=now,
        component_modified_timestamp=now,
        status_modified_timestamp=now,
        owner_modified_timestamp=now,
        star_count=12,
        is_spam=False,
        attachment_count=0,
        dangling_blocked_on_refs=[
            common_pb2.IssueRef(project_name='dangling_proj', local_id=1234)],
        dangling_blocking_refs=[
            common_pb2.IssueRef(project_name='dangling_proj', local_id=5678)],
        phases=[
            issue_objects_pb2.PhaseDef(
              phase_ref=issue_objects_pb2.PhaseRef(phase_name='Dev'),
              rank=1),
            issue_objects_pb2.PhaseDef(
              phase_ref=issue_objects_pb2.PhaseRef(phase_name='Beta'),
              rank=2)])
    self.assertEqual(expected, actual)

  def testConvertIssue_ExternalMergedInto(self):
    """ConvertIssue works on issues with external mergedinto values."""
    issue = fake.MakeTestIssue(789, 3, 'sum', 'New', 111, project_name='proj',
        merged_into_external='b/5678')
    actual = converters.ConvertIssue(issue, self.users_by_id, {}, self.config)
    expected = issue_objects_pb2.Issue(
        project_name='proj',
        local_id=3,
        summary='sum',
        merged_into_issue_ref=common_pb2.IssueRef(ext_identifier='b/5678'),
        status_ref=common_pb2.StatusRef(
            status='New',
            is_derived=False,
            means_open=True),
        owner_ref=common_pb2.UserRef(
            user_id=111,
            display_name='one@example.com',
            is_derived=False),
        reporter_ref=common_pb2.UserRef(
            user_id=111, display_name='one@example.com', is_derived=False))

    self.assertEqual(expected, actual)

  def testConvertPhaseDef(self):
    """We can convert a prototpc Phase to a protoc PhaseDef. """
    phase = tracker_pb2.Phase(phase_id=1, name='phase', rank=2)
    actual = converters.ConvertPhaseDef(phase)
    expected = issue_objects_pb2.PhaseDef(
        phase_ref=issue_objects_pb2.PhaseRef(phase_name='phase'),
        rank=2
    )
    self.assertEqual(expected, actual)

  def testConvertAmendment(self):
    """We can convert various kinds of Amendments."""
    amend = tracker_pb2.Amendment(
        field=tracker_pb2.FieldID.SUMMARY, newvalue='new', oldvalue='old')
    actual = converters.ConvertAmendment(amend, self.users_by_id)
    self.assertEqual('Summary', actual.field_name)
    self.assertEqual('new', actual.new_or_delta_value)
    self.assertEqual('old', actual.old_value)

    amend = tracker_pb2.Amendment(
        field=tracker_pb2.FieldID.OWNER, added_user_ids=[111])
    actual = converters.ConvertAmendment(amend, self.users_by_id)
    self.assertEqual('Owner', actual.field_name)
    self.assertEqual('one@example.com', actual.new_or_delta_value)
    self.assertEqual('', actual.old_value)

    amend = tracker_pb2.Amendment(
        field=tracker_pb2.FieldID.CC,
        added_user_ids=[111], removed_user_ids=[222])
    actual = converters.ConvertAmendment(amend, self.users_by_id)
    self.assertEqual('Cc', actual.field_name)
    self.assertEqual(
      '-two@example.com one@example.com', actual.new_or_delta_value)
    self.assertEqual('', actual.old_value)

    amend = tracker_pb2.Amendment(
        field=tracker_pb2.FieldID.CUSTOM, custom_field_name='EstDays',
        newvalue='12')
    actual = converters.ConvertAmendment(amend, self.users_by_id)
    self.assertEqual('EstDays', actual.field_name)
    self.assertEqual('12', actual.new_or_delta_value)
    self.assertEqual('', actual.old_value)

  @patch('tracker.attachment_helpers.SignAttachmentID')
  def testConvertAttachment(self, mock_SignAttachmentID):
    mock_SignAttachmentID.return_value = 2
    attach = tracker_pb2.Attachment(
        attachment_id=1, mimetype='image/png', filename='example.png',
        filesize=12345)

    actual = converters.ConvertAttachment(attach, 'proj')

    expected = issue_objects_pb2.Attachment(
        attachment_id=1, filename='example.png',
        size=12345, content_type='image/png',
        thumbnail_url='attachment?aid=1&signed_aid=2&inline=1&thumb=1',
        view_url='attachment?aid=1&signed_aid=2&inline=1',
        download_url='attachment?aid=1&signed_aid=2')
    self.assertEqual(expected, actual)

  def testConvertComment_Normal(self):
    """We can convert a protorpc IssueComment to a protoc Comment."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12)

    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {}, 111,
        permissions.PermissionSet([]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment', is_spam=False)
    self.assertEqual(expected, actual)

  def testConvertComment_CanReportComment(self):
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12)

    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {}, 111,
        permissions.PermissionSet([permissions.FLAG_SPAM]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment', can_flag=True)
    self.assertEqual(expected, actual)

  def testConvertComment_CanUnReportComment(self):
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12)

    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [111], {}, 111,
        permissions.PermissionSet([permissions.FLAG_SPAM]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment', is_spam=True, is_deleted=True,
        can_flag=True)
    self.assertEqual(expected, actual)

  def testConvertComment_CantUnFlagCommentWithoutVerdictSpam(self):
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12, is_spam=True)

    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [111], {}, 111,
        permissions.PermissionSet([permissions.FLAG_SPAM]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12,
        timestamp=now, is_spam=True, is_deleted=True)
    self.assertEqual(expected, actual)

  def testConvertComment_CanFlagSpamComment(self):
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12)

    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {}, 111,
        permissions.PermissionSet([permissions.VERDICT_SPAM]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment', can_flag=True)
    self.assertEqual(expected, actual)

  def testConvertComment_CanUnFlagSpamComment(self):
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12, is_spam=True)

    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [222], {}, 111,
        permissions.PermissionSet([permissions.VERDICT_SPAM]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment', is_spam=True, is_deleted=True,
        can_flag=True)
    self.assertEqual(expected, actual)

  def testConvertComment_DeletedComment(self):
    """We can convert a protorpc IssueComment to a protoc Comment."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12, deleted_by=111)
    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {}, 111,
        permissions.PermissionSet([permissions.DELETE_OWN]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=True,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment', can_delete=True)
    self.assertEqual(expected, actual)

  def testConvertComment_DeletedCommentCantView(self):
    """We can convert a protorpc IssueComment to a protoc Comment."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12, deleted_by=111)
    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {}, 111,
        permissions.PermissionSet([]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=True,
        timestamp=now)
    self.assertEqual(expected, actual)

  def testConvertComment_CommentByBannedUser(self):
    """We can convert a protorpc IssueComment to a protoc Comment."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=333, timestamp=now,
        content='a comment', sequence=12)
    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {}, 111,
        permissions.PermissionSet([]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=True,
        timestamp=now)
    self.assertEqual(expected, actual)

  def testConvertComment_Description(self):
    """We can convert a protorpc IssueComment to a protoc Comment."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12, is_description=True)
    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {101: 1}, 111,
        permissions.PermissionSet([]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment', is_spam=False, description_num=1)
    self.assertEqual(expected, actual)
    comment.is_description = False

  def testConvertComment_Approval(self):
    """We can convert a protorpc IssueComment to a protoc Comment."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12, approval_id=11)
    # Comment on an approval.
    self.config.field_defs.append(tracker_pb2.FieldDef(
        field_id=11, project_id=789, field_name='Accessibility',
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE,
        applicable_type='Launch'))
    self.config.approval_defs.append(tracker_pb2.ApprovalDef(
        approval_id=11, approver_ids=[111], survey='survey 1'))

    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {}, 111,
        permissions.PermissionSet([]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment', is_spam=False,
        approval_ref=common_pb2.FieldRef(field_name='Accessibility'))
    self.assertEqual(expected, actual)

  def testConvertComment_ViewOwnInboundMessage(self):
    """Users can view their own inbound messages."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12, inbound_message='inbound message')

    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {}, 111,
        permissions.PermissionSet([]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment', inbound_message='inbound message')
    self.assertEqual(expected, actual)

  def testConvertComment_ViewInboundMessageWithPermission(self):
    """Users can view their own inbound messages."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12, inbound_message='inbound message')

    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {}, 222,
        permissions.PermissionSet([permissions.VIEW_INBOUND_MESSAGES]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment', inbound_message='inbound message')
    self.assertEqual(expected, actual)

  def testConvertComment_NotAllowedToViewInboundMessage(self):
    """Users can view their own inbound messages."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111, timestamp=now,
        content='a comment', sequence=12, inbound_message='inbound message')

    actual = converters.ConvertComment(
        issue, comment, self.config, self.users_by_id, [], {}, 222,
        permissions.PermissionSet([]))
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a comment')
    self.assertEqual(expected, actual)

  def testConvertCommentList(self):
    """We can convert a list of comments."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment_0 = tracker_pb2.IssueComment(
        id=100, project_id=789, user_id=111, timestamp=now,
        content='a description', sequence=0, is_description=True)
    comment_1 = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=222, timestamp=now,
        content='a comment', sequence=1)
    comment_2 = tracker_pb2.IssueComment(
        id=102, project_id=789, user_id=222, timestamp=now,
        content='deleted comment', sequence=2, deleted_by=111)
    comment_3 = tracker_pb2.IssueComment(
        id=103, project_id=789, user_id=111, timestamp=now,
        content='another desc', sequence=3, is_description=True)

    actual = converters.ConvertCommentList(
        issue, [comment_0, comment_1, comment_2, comment_3], self.config,
        self.users_by_id, {}, 222,
        permissions.PermissionSet([permissions.DELETE_OWN]))

    expected_0 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=0, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a description', is_spam=False,
        description_num=1)
    expected_1 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=1, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=222, display_name='two@example.com'),
        timestamp=now, content='a comment', is_spam=False, can_delete=True)
    expected_2 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=2, is_deleted=True,
        timestamp=now)
    expected_3 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=3, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='another desc', is_spam=False,
        description_num=2)
    self.assertEqual(expected_0, actual[0])
    self.assertEqual(expected_1, actual[1])
    self.assertEqual(expected_2, actual[2])
    self.assertEqual(expected_3, actual[3])

  def testConvertCommentList_DontUseDeletedOrSpamDescriptions(self):
    """When converting comments, deleted or spam are not descriptions."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, project_name='proj')
    comment_0 = tracker_pb2.IssueComment(
        id=100, project_id=789, user_id=111, timestamp=now,
        content='a description', sequence=0, is_description=True)
    comment_1 = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=222, timestamp=now,
        content='a spam description', sequence=1, is_description=True,
        is_spam=True)
    comment_2 = tracker_pb2.IssueComment(
        id=102, project_id=789, user_id=222, timestamp=now,
        content='a deleted description', sequence=2, is_description=True,
        deleted_by=111)
    comment_3 = tracker_pb2.IssueComment(
        id=103, project_id=789, user_id=111, timestamp=now,
        content='another good desc', sequence=3, is_description=True)
    comment_4 = tracker_pb2.IssueComment(
        id=104, project_id=789, user_id=333, timestamp=now,
        content='desc from banned', sequence=4, is_description=True)

    actual = converters.ConvertCommentList(
        issue, [comment_0, comment_1, comment_2, comment_3, comment_4],
        self.config, self.users_by_id, {}, 222,
        permissions.PermissionSet([permissions.DELETE_OWN]))

    expected_0 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=0, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='a description', is_spam=False,
        description_num=1)
    expected_1 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=1, is_deleted=True,
        timestamp=now, is_spam=True, can_delete=False)
    expected_2 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=2, is_deleted=True,
        timestamp=now)
    expected_3 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=3, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='one@example.com'),
        timestamp=now, content='another good desc', is_spam=False,
        description_num=2)
    expected_4 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=4, is_deleted=True,
        timestamp=now, is_spam=False)
    self.assertEqual(expected_0, actual[0])
    self.assertEqual(expected_1, actual[1])
    self.assertEqual(expected_2, actual[2])
    self.assertEqual(expected_3, actual[3])
    self.assertEqual(expected_4, actual[4])

  def testIngestUserRef(self):
    """We can look up a single user ID for a protoc UserRef."""
    self.services.user.TestAddUser('user1@example.com', 111)
    ref = common_pb2.UserRef(display_name='user1@example.com')
    actual = converters.IngestUserRef(self.cnxn, ref, self.services.user)
    self.assertEqual(111, actual)

  def testIngestUserRef_NoSuchUser(self):
    """We reject a malformed UserRef.display_name."""
    ref = common_pb2.UserRef(display_name='Bob@gmail.com')
    with self.assertRaises(exceptions.NoSuchUserException):
      converters.IngestUserRef(self.cnxn, ref, self.services.user)

  def testIngestUserRefs_ClearTheOwnerField(self):
    """We can look up user IDs for protoc UserRefs."""
    ref = common_pb2.UserRef(user_id=0)
    actual = converters.IngestUserRefs(self.cnxn, [ref], self.services.user)
    self.assertEqual([0], actual)

  def testIngestUserRefs_ByExistingID(self):
    """Users can be specified by user_id."""
    self.services.user.TestAddUser('user1@example.com', 111)
    ref = common_pb2.UserRef(user_id=111)
    actual = converters.IngestUserRefs(self.cnxn, [ref], self.services.user)
    self.assertEqual([111], actual)

  def testIngestUserRefs_ByNonExistingID(self):
    """We reject references to non-existing user IDs."""
    ref = common_pb2.UserRef(user_id=999)
    with self.assertRaises(exceptions.NoSuchUserException):
      converters.IngestUserRefs(self.cnxn, [ref], self.services.user)

  def testIngestUserRefs_ByExistingEmail(self):
    """Existing users can be specified by email address."""
    self.services.user.TestAddUser('user1@example.com', 111)
    ref = common_pb2.UserRef(display_name='user1@example.com')
    actual = converters.IngestUserRefs(self.cnxn, [ref], self.services.user)
    self.assertEqual([111], actual)

  def testIngestUserRefs_ByNonExistingEmail(self):
    """New users can be specified by email address."""
    # Case where autocreate=False
    ref = common_pb2.UserRef(display_name='new@example.com')
    with self.assertRaises(exceptions.NoSuchUserException):
      converters.IngestUserRefs(
          self.cnxn, [ref], self.services.user, autocreate=False)

    # Case where autocreate=True
    actual = converters.IngestUserRefs(
        self.cnxn, [ref], self.services.user, autocreate=True)
    user_id = self.services.user.LookupUserID(self.cnxn, 'new@example.com')
    self.assertEqual([user_id], actual)

  def testIngestUserRefs_ByMalformedEmail(self):
    """We ignore malformed user emails."""
    self.services.user.TestAddUser('user1@example.com', 111)
    self.services.user.TestAddUser('user3@example.com', 333)
    refs = [
        common_pb2.UserRef(user_id=0),
        common_pb2.UserRef(display_name='not-a-valid-email'),
        common_pb2.UserRef(user_id=333),
        common_pb2.UserRef(display_name='user1@example.com')
        ]
    actual = converters.IngestUserRefs(
        self.cnxn, refs, self.services.user, autocreate=True)
    self.assertEqual(actual, [0, 333, 111])

  def testIngestUserRefs_MixOfIDAndEmail(self):
    """Requests can specify some users by ID and others by email."""
    self.services.user.TestAddUser('user1@example.com', 111)
    self.services.user.TestAddUser('user2@example.com', 222)
    self.services.user.TestAddUser('user3@example.com', 333)
    ref1 = common_pb2.UserRef(display_name='user1@example.com')
    ref2 = common_pb2.UserRef(display_name='user2@example.com')
    ref3 = common_pb2.UserRef(user_id=333)
    actual = converters.IngestUserRefs(
        self.cnxn, [ref1, ref2, ref3], self.services.user)
    self.assertEqual([111, 222, 333], actual)

  def testIngestPrefValues(self):
    """We can convert a list of UserPrefValues from protoc to protorpc."""
    self.assertEqual(
        [],
        converters.IngestPrefValues([]))

    userprefvalues = [
        user_objects_pb2.UserPrefValue(name='foo_1', value='bar_1'),
        user_objects_pb2.UserPrefValue(name='foo_2', value='bar_2')]
    actual = converters.IngestPrefValues(userprefvalues)
    expected = [
        user_pb2.UserPrefValue(name='foo_1', value='bar_1'),
        user_pb2.UserPrefValue(name='foo_2', value='bar_2')]
    self.assertEqual(expected, actual)

  def testIngestComponentRefs(self):
    """We can look up component IDs for a list of protoc UserRefs."""
    self.assertEqual([], converters.IngestComponentRefs([], self.config))

    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI'),
      tracker_pb2.ComponentDef(component_id=2, path='DB')]
    refs = [common_pb2.ComponentRef(path='UI'),
            common_pb2.ComponentRef(path='DB')]
    self.assertEqual(
        [1, 2], converters.IngestComponentRefs(refs, self.config))

  def testIngestIssueRefs_ValidatesExternalRefs(self):
    """IngestIssueRefs requires external refs have at least one slash."""
    ref = common_pb2.IssueRef(ext_identifier='b123456')
    with self.assertRaises(exceptions.InvalidExternalIssueReference):
      converters.IngestIssueRefs(self.cnxn, [ref], self.services)

  def testIngestIssueRefs_SkipsExternalRefs(self):
    """IngestIssueRefs skips external refs."""
    ref = common_pb2.IssueRef(ext_identifier='b/123456')
    actual = converters.IngestIssueRefs(
        self.cnxn, [ref], self.services)
    self.assertEqual([], actual)

  def testIngestExtIssueRefs_Normal(self):
    """IngestExtIssueRefs returns all valid external refs."""
    refs = [
      common_pb2.IssueRef(project_name='rutabaga', local_id=1234),
      common_pb2.IssueRef(ext_identifier='b123456'),
      common_pb2.IssueRef(ext_identifier='b/123456'), # <- Valid ref 1.
      common_pb2.IssueRef(ext_identifier='rutabaga/123456'),
      common_pb2.IssueRef(ext_identifier='123456'),
      common_pb2.IssueRef(ext_identifier='b/56789'), # <- Valid ref 2.
      common_pb2.IssueRef(ext_identifier='b//123456')]

    actual = converters.IngestExtIssueRefs(refs)
    self.assertEqual(['b/123456', 'b/56789'], actual)

  def testIngestIssueDelta_Empty(self):
    """An empty protorpc IssueDelta makes an empty protoc IssueDelta."""
    delta = issue_objects_pb2.IssueDelta()
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, [])
    expected = tracker_pb2.IssueDelta()
    self.assertEqual(expected, actual)

  def testIngestIssueDelta_BuiltInFields(self):
    """We can create a protorpc IssueDelta from a protoc IssueDelta."""
    self.services.user.TestAddUser('user1@example.com', 111)
    self.services.user.TestAddUser('user2@example.com', 222)
    self.services.user.TestAddUser('user3@example.com', 333)
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI')]
    delta = issue_objects_pb2.IssueDelta(
        status=wrappers_pb2.StringValue(value='Fixed'),
        owner_ref=common_pb2.UserRef(user_id=222),
        summary=wrappers_pb2.StringValue(value='New summary'),
        cc_refs_add=[common_pb2.UserRef(user_id=333)],
        comp_refs_add=[common_pb2.ComponentRef(path='UI')],
        label_refs_add=[common_pb2.LabelRef(label='Hot')])
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, [])
    expected = tracker_pb2.IssueDelta(
        status='Fixed', owner_id=222, summary='New summary',
        cc_ids_add=[333], comp_ids_add=[1],
        labels_add=['Hot'])
    self.assertEqual(expected, actual)

  def testIngestIssueDelta_ClearMergedInto(self):
    """We can clear merged into from the current issue."""
    delta = issue_objects_pb2.IssueDelta(merged_into_ref=common_pb2.IssueRef())
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, [])
    expected = tracker_pb2.IssueDelta(merged_into=0)
    self.assertEqual(expected, actual)

  def testIngestIssueDelta_BadOwner(self):
    """We reject a specified owner that does not exist."""
    delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(display_name='user@exa'))
    with self.assertRaises(exceptions.NoSuchUserException):
      converters.IngestIssueDelta(
          self.cnxn, self.services, delta, self.config, [])

  def testIngestIssueDelta_BadOwnerIgnored(self):
    """We can ignore an incomplete owner email for presubmit."""
    delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(display_name='user@exa'))
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, [],
        ignore_missing_objects=True)
    expected = tracker_pb2.IssueDelta()
    self.assertEqual(expected, actual)

  def testIngestIssueDelta_InvalidComponent(self):
    """We reject a protorpc IssueDelta that has an invalid component."""
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI')]
    delta = issue_objects_pb2.IssueDelta(
        comp_refs_add=[common_pb2.ComponentRef(path='XYZ')])
    with self.assertRaises(exceptions.NoSuchComponentException):
      converters.IngestIssueDelta(
          self.cnxn, self.services, delta, self.config, [])

  def testIngestIssueDelta_InvalidComponentIgnored(self):
    """We can ignore invalid components for presubmits."""
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI')]
    delta = issue_objects_pb2.IssueDelta(
        comp_refs_add=[common_pb2.ComponentRef(path='UI'),
                       common_pb2.ComponentRef(path='XYZ')])
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, [],
        ignore_missing_objects=True)
    self.assertEqual([1], actual.comp_ids_add)

  def testIngestIssueDelta_CustomFields(self):
    """We can create a protorpc IssueDelta from a protoc IssueDelta."""
    self.config.field_defs = [
        self.fd_1, self.fd_2, self.fd_3, self.fd_4, self.fd_6]
    phases = [tracker_pb2.Phase(phase_id=1, name="Beta")]
    delta = issue_objects_pb2.IssueDelta(
        field_vals_add=[
            issue_objects_pb2.FieldValue(
                value='string',
                field_ref=common_pb2.FieldRef(field_name='FirstField')
            ),
            issue_objects_pb2.FieldValue(
                value='1',
                field_ref=common_pb2.FieldRef(field_name='PhaseField'),
                phase_ref=issue_objects_pb2.PhaseRef(phase_name='Beta')
            )],
        field_vals_remove=[
            issue_objects_pb2.FieldValue(
                value='34', field_ref=common_pb2.FieldRef(
                    field_name='SecField'))],
        fields_clear=[common_pb2.FieldRef(field_name='FirstField')])
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, phases)
    self.assertEqual(actual.field_vals_add,
                     [tracker_pb2.FieldValue(
                         str_value='string', field_id=1, derived=False),
                      tracker_pb2.FieldValue(
                          int_value=1, field_id=6, phase_id=1, derived=False)
                     ])
    self.assertEqual(actual.field_vals_remove, [tracker_pb2.FieldValue(
        int_value=34, field_id=2, derived=False)])
    self.assertEqual(actual.fields_clear, [1])

  def testIngestIssueDelta_InvalidCustomFields(self):
    """We can create a protorpc IssueDelta from a protoc IssueDelta."""
    # TODO(jrobbins): add and remove.
    delta = issue_objects_pb2.IssueDelta(
        fields_clear=[common_pb2.FieldRef(field_name='FirstField')])
    with self.assertRaises(exceptions.NoSuchFieldDefException):
      converters.IngestIssueDelta(
          self.cnxn, self.services, delta, self.config, [])

  def testIngestIssueDelta_ShiftFieldsIntoLabels(self):
    """Test that enum fields are shifted into labels."""
    self.config.field_defs = [self.fd_5]
    delta = issue_objects_pb2.IssueDelta(
        field_vals_add=[
            issue_objects_pb2.FieldValue(
                value='Foo',
                field_ref=common_pb2.FieldRef(field_name='Pre', field_id=5)
            )],
        field_vals_remove=[
            issue_objects_pb2.FieldValue(
                value='Bar',
                field_ref=common_pb2.FieldRef(field_name='Pre', field_id=5),
            )])
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, [])
    self.assertEqual(actual.field_vals_add, [])
    self.assertEqual(actual.field_vals_remove, [])
    self.assertEqual(actual.labels_add, ['Pre-Foo'])
    self.assertEqual(actual.labels_remove, ['Pre-Bar'])

  def testIngestIssueDelta_RelatedIssues(self):
    """We can create a protorpc IssueDelta that references related issues."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111)
    self.services.issue.TestAddIssue(issue)
    delta = issue_objects_pb2.IssueDelta(
        blocked_on_refs_add=[common_pb2.IssueRef(
            project_name='proj', local_id=issue.local_id)],
        merged_into_ref=common_pb2.IssueRef(
            project_name='proj', local_id=issue.local_id))
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, [])
    self.assertEqual([issue.issue_id], actual.blocked_on_add)
    self.assertEqual([], actual.blocking_add)
    self.assertEqual(issue.issue_id, actual.merged_into)

  def testIngestIssueDelta_InvalidRelatedIssues(self):
    """We reject references to related issues that do not exist."""
    delta = issue_objects_pb2.IssueDelta(
        merged_into_ref=common_pb2.IssueRef(
            project_name='not-a-proj', local_id=8))
    with self.assertRaises(exceptions.NoSuchProjectException):
      converters.IngestIssueDelta(
          self.cnxn, self.services, delta, self.config, [])

    delta = issue_objects_pb2.IssueDelta(
        merged_into_ref=common_pb2.IssueRef(
            project_name='proj', local_id=999))
    with self.assertRaises(exceptions.NoSuchIssueException):
      converters.IngestIssueDelta(
          self.cnxn, self.services, delta, self.config, [])

  def testIngestIssueDelta_ExternalMergedInto(self):
    """IngestIssueDelta properly handles external mergedinto refs."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111)
    self.services.issue.TestAddIssue(issue)
    delta = issue_objects_pb2.IssueDelta(
        merged_into_ref=common_pb2.IssueRef(ext_identifier='b/5678'))
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, [])

    self.assertEqual(0, actual.merged_into)
    self.assertEqual('b/5678', actual.merged_into_external)

  def testIngestAttachmentUploads_Empty(self):
    """Uploading zero files results in an empty list of attachments."""
    self.assertEqual([], converters.IngestAttachmentUploads([]))

  def testIngestAttachmentUploads_Normal(self):
    """Uploading files results in a list of attachments."""
    uploads = [
        issue_objects_pb2.AttachmentUpload(
            filename='hello.c', content='int main() {}'),
        issue_objects_pb2.AttachmentUpload(
            filename='README.md', content='readme content'),
        ]
    actual = converters.IngestAttachmentUploads(uploads)
    self.assertEqual(
      [('hello.c', 'int main() {}', 'text/plain'),
       ('README.md', 'readme content', 'text/plain')],
      actual)

  def testIngestAttachmentUploads_Invalid(self):
    """We reject uploaded files that lack a name or content."""
    with self.assertRaises(exceptions.InputException):
      converters.IngestAttachmentUploads([
          issue_objects_pb2.AttachmentUpload(content='name is mssing')])

    with self.assertRaises(exceptions.InputException):
      converters.IngestAttachmentUploads([
          issue_objects_pb2.AttachmentUpload(filename='content is mssing')])

  def testIngestApprovalDelta(self):
    self.services.user.TestAddUser('user1@example.com', 111)
    self.services.user.TestAddUser('user2@example.com', 222)

    self.config.field_defs = [
        self.fd_1, self.fd_2, self.fd_3, self.fd_4, self.fd_7]

    approval_delta = issue_objects_pb2.ApprovalDelta(
        status=issue_objects_pb2.APPROVED,
        approver_refs_add=[common_pb2.UserRef(user_id=111)],
        approver_refs_remove=[common_pb2.UserRef(user_id=222)],
        field_vals_add=[
            issue_objects_pb2.FieldValue(
                value='string', field_ref=common_pb2.FieldRef(
                    field_id=1, field_name='FirstField')),
            issue_objects_pb2.FieldValue(
                value='choice1', field_ref=common_pb2.FieldRef(
                    field_id=7, field_name='ApprovalEnum')),
        ],
        field_vals_remove=[
            issue_objects_pb2.FieldValue(
                value='34', field_ref=common_pb2.FieldRef(
                    field_id=2, field_name='SecField')),
            issue_objects_pb2.FieldValue(
                value='choice2', field_ref=common_pb2.FieldRef(
                    field_id=7, field_name='ApprovalEnum')),
        ],
        fields_clear=[common_pb2.FieldRef(field_name='FirstField')])

    actual = converters.IngestApprovalDelta(
        self.cnxn, self.services.user, approval_delta, 333, self.config)
    self.assertEqual(
        actual.status, tracker_pb2.ApprovalStatus.APPROVED,)
    self.assertEqual(actual.setter_id, 333)
    self.assertEqual(actual.approver_ids_add, [111])
    self.assertEqual(actual.approver_ids_remove, [222])
    self.assertEqual(actual.subfield_vals_add, [tracker_pb2.FieldValue(
        str_value='string', field_id=1, derived=False)])
    self.assertEqual(actual.subfield_vals_remove, [tracker_pb2.FieldValue(
        int_value=34, field_id=2, derived=False)])
    self.assertEqual(actual.subfields_clear, [1])
    self.assertEqual(actual.labels_add, ['ApprovalEnum-choice1'])
    self.assertEqual(actual.labels_remove, ['ApprovalEnum-choice2'])

    # test a NOT_SET status is registered as None.
    approval_delta.status = issue_objects_pb2.NOT_SET
    actual = converters.IngestApprovalDelta(
        self.cnxn, self.services.user, approval_delta, 333, self.config)
    self.assertIsNone(actual.status)

  def testIngestApprovalStatus(self):
    actual = converters.IngestApprovalStatus(issue_objects_pb2.NOT_SET)
    self.assertEqual(actual, tracker_pb2.ApprovalStatus.NOT_SET)

    actual = converters.IngestApprovalStatus(issue_objects_pb2.NOT_APPROVED)
    self.assertEqual(actual, tracker_pb2.ApprovalStatus.NOT_APPROVED)

  def testIngestFieldValues(self):
    self.services.user.TestAddUser('user1@example.com', 111)
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_4, self.fd_6]
    phases = [
        tracker_pb2.Phase(phase_id=3, name="Dev"),
        tracker_pb2.Phase(phase_id=1, name="Beta")
    ]

    field_values = [
        issue_objects_pb2.FieldValue(
            value='string',
            field_ref=common_pb2.FieldRef(field_name='FirstField')
        ),
        issue_objects_pb2.FieldValue(
            value='34',
            field_ref=common_pb2.FieldRef(field_name='SecField')
        ),
        issue_objects_pb2.FieldValue(
            value='user1@example.com',
            field_ref=common_pb2.FieldRef(field_name='UserField'),
            # phase_ref for non-phase fields should be ignored.
            phase_ref=issue_objects_pb2.PhaseRef(phase_name='Dev')
        ),
        issue_objects_pb2.FieldValue(
            value='2',
            field_ref=common_pb2.FieldRef(field_name='PhaseField'),
            phase_ref=issue_objects_pb2.PhaseRef(phase_name='Beta'))
    ]

    actual = converters.IngestFieldValues(
        self.cnxn, self.services.user, field_values, self.config, phases)
    self.assertEqual(
        actual,
        [
            tracker_pb2.FieldValue(
                str_value='string', field_id=1, derived=False),
            tracker_pb2.FieldValue(int_value=34, field_id=2, derived=False),
            tracker_pb2.FieldValue(user_id=111, field_id=4, derived=False),
            tracker_pb2.FieldValue(
                int_value=2, field_id=6, phase_id=1, derived=False)
        ]
    )

  def testIngestFieldValues_EmptyUser(self):
    """We ignore empty user email strings."""
    self.services.user.TestAddUser('user1@example.com', 111)
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_4, self.fd_6]
    field_values = [
        issue_objects_pb2.FieldValue(
            value='user1@example.com',
            field_ref=common_pb2.FieldRef(field_name='UserField')),
        issue_objects_pb2.FieldValue(
            value='',
            field_ref=common_pb2.FieldRef(field_name='UserField'))
        ]

    actual = converters.IngestFieldValues(
        self.cnxn, self.services.user, field_values, self.config, [])
    self.assertEqual(
        actual,
        [tracker_pb2.FieldValue(user_id=111, field_id=4, derived=False)])

  def testIngestFieldValues_Unicode(self):
    """We can ingest unicode strings."""
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_4, self.fd_6]
    field_values = [
        issue_objects_pb2.FieldValue(
            value=u'\xe2\x9d\xa4\xef\xb8\x8f',
            field_ref=common_pb2.FieldRef(field_name='FirstField')
        ),
    ]

    actual = converters.IngestFieldValues(
        self.cnxn, self.services.user, field_values, self.config, [])
    self.assertEqual(
        actual,
        [
            tracker_pb2.FieldValue(
               str_value=u'\xe2\x9d\xa4\xef\xb8\x8f', field_id=1,
               derived=False),
        ]
    )

  def testIngestFieldValues_InvalidUser(self):
    """We reject invalid user email strings."""
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_4, self.fd_6]
    field_values = [
        issue_objects_pb2.FieldValue(
            value='bad value',
            field_ref=common_pb2.FieldRef(field_name='UserField'))]

    with self.assertRaises(exceptions.NoSuchUserException):
      converters.IngestFieldValues(
          self.cnxn, self.services.user, field_values, self.config, [])

  def testIngestFieldValues_InvalidInt(self):
    """We reject invalid int-field strings."""
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_4, self.fd_6]
    field_values = [
        issue_objects_pb2.FieldValue(
            value='Not a number',
            field_ref=common_pb2.FieldRef(field_name='SecField'))]

    with self.assertRaises(exceptions.InputException) as cm:
      converters.IngestFieldValues(
          self.cnxn, self.services.user, field_values, self.config, [])

    self.assertEqual(
        'Unparsable value for field SecField',
        cm.exception.message)

  def testIngestSavedQueries(self):
    self.services.project.TestAddProject('chromium', project_id=1)
    self.services.project.TestAddProject('fakeproject', project_id=2)

    saved_queries = [
        tracker_pb2.SavedQuery(
            query_id=101,
            name='test query',
            query='owner:me',
            executes_in_project_ids=[1, 2]),
        tracker_pb2.SavedQuery(
            query_id=202,
            name='another query',
            query='-component:Test',
            executes_in_project_ids=[1])
    ]

    converted_queries = converters.IngestSavedQueries(self.cnxn,
        self.services.project, saved_queries)

    self.assertEqual(converted_queries[0].query_id, 101)
    self.assertEqual(converted_queries[0].name, 'test query')
    self.assertEqual(converted_queries[0].query, 'owner:me')
    self.assertEqual(converted_queries[0].project_names,
        ['chromium', 'fakeproject'])

    self.assertEqual(converted_queries[1].query_id, 202)
    self.assertEqual(converted_queries[1].name, 'another query')
    self.assertEqual(converted_queries[1].query, '-component:Test')
    self.assertEqual(converted_queries[1].project_names, ['chromium'])


  def testIngestHotlistRef(self):
    self.services.user.TestAddUser('user1@example.com', 111)
    hotlist = self.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[222])

    owner_ref = common_pb2.UserRef(user_id=111)
    hotlist_ref = common_pb2.HotlistRef(name='Fake-Hotlist', owner=owner_ref)

    actual_hotlist_id = converters.IngestHotlistRef(
        self.cnxn, self.services.user, self.services.features, hotlist_ref)
    self.assertEqual(actual_hotlist_id, hotlist.hotlist_id)

  def testIngestHotlistRef_HotlistID(self):
    self.services.user.TestAddUser('user1@example.com', 111)
    hotlist = self.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[222])

    hotlist_ref = common_pb2.HotlistRef(hotlist_id=hotlist.hotlist_id)

    actual_hotlist_id = converters.IngestHotlistRef(
        self.cnxn, self.services.user, self.services.features, hotlist_ref)
    self.assertEqual(actual_hotlist_id, hotlist.hotlist_id)

  def testIngestHotlistRef_NotEnoughInformation(self):
    hotlist_ref = common_pb2.HotlistRef(name='Some-Hotlist')
    with self.assertRaises(features_svc.NoSuchHotlistException):
      converters.IngestHotlistRef(
          self.cnxn, self.services.user, self.services.features, hotlist_ref)

  def testIngestHotlistRef_InconsistentRequest(self):
    self.services.user.TestAddUser('user1@example.com', 111)
    hotlist1 = self.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[222])
    self.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist-2', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[222])

    hotlist_ref = common_pb2.HotlistRef(
        hotlist_id=hotlist1.hotlist_id,
        name='Fake-Hotlist-2',
        owner=common_pb2.UserRef(user_id=111))
    with self.assertRaises(features_svc.NoSuchHotlistException):
      converters.IngestHotlistRef(
          self.cnxn, self.services.user, self.services.features, hotlist_ref)

  def testIngestHotlistRef_NonExistentHotlistID(self):
    hotlist_ref = common_pb2.HotlistRef(hotlist_id=1234)
    with self.assertRaises(features_svc.NoSuchHotlistException):
      converters.IngestHotlistRef(
          self.cnxn, self.services.user, self.services.features, hotlist_ref)

  def testIngestHotlistRef_NoSuchHotlist(self):
    self.services.user.TestAddUser('user1@example.com', 111)

    owner_ref = common_pb2.UserRef(user_id=111)
    hotlist_ref = common_pb2.HotlistRef(name='Fake-Hotlist', owner=owner_ref)

    with self.assertRaises(features_svc.NoSuchHotlistException):
      converters.IngestHotlistRef(
          self.cnxn, self.services.user, self.services.features, hotlist_ref)

  def testIngestHotlistRefs(self):
    self.services.user.TestAddUser('user1@example.com', 111)
    hotlist_1 = self.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[222])
    hotlist_2 = self.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist-2', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[222])

    owner_ref = common_pb2.UserRef(user_id=111)
    hotlist_refs = [
        common_pb2.HotlistRef(name='Fake-Hotlist', owner=owner_ref),
        common_pb2.HotlistRef(hotlist_id=hotlist_2.hotlist_id)]

    actual_hotlist_ids = converters.IngestHotlistRefs(
        self.cnxn, self.services.user, self.services.features, hotlist_refs)
    self.assertEqual(
        actual_hotlist_ids, [hotlist_1.hotlist_id, hotlist_2.hotlist_id])

  def testIngestPagination(self):
    # Use settings.max_project_search_results_per_page if max_items is not
    # present.
    pagination = common_pb2.Pagination(start=1234)
    self.assertEqual(
        (1234, settings.max_artifact_search_results_per_page),
        converters.IngestPagination(pagination))
    # Otherwise, use the minimum between what was requested and
    # settings.max_project_search_results_per_page
    pagination = common_pb2.Pagination(start=1234, max_items=56)
    self.assertEqual(
        (1234, 56),
        converters.IngestPagination(pagination))
    pagination = common_pb2.Pagination(start=1234, max_items=5678)
    self.assertEqual(
        (1234, settings.max_artifact_search_results_per_page),
        converters.IngestPagination(pagination))

  def testConvertStatusDef(self):
    """We can convert a status definition to protoc."""
    status_def = tracker_pb2.StatusDef(status='Started')
    actual = converters.ConvertStatusDef(status_def)
    self.assertEqual('Started', actual.status)
    self.assertFalse(actual.means_open)
    self.assertEqual('', actual.docstring)
    self.assertFalse(actual.deprecated)
    # rank is not set on output, only used when setting a new rank.
    self.assertEqual(0, actual.rank)

    status_def = tracker_pb2.StatusDef(
        status='New', means_open=True, status_docstring='doc', deprecated=True)
    actual = converters.ConvertStatusDef(status_def)
    self.assertEqual('New', actual.status)
    self.assertTrue(actual.means_open)
    self.assertEqual('doc', actual.docstring)
    self.assertTrue(actual.deprecated)
    self.assertEqual(0, actual.rank)

  def testConvertLabelDef(self):
    """We can convert a label definition to protoc."""
    label_def = tracker_pb2.LabelDef(label='Security')
    actual = converters.ConvertLabelDef(label_def)
    self.assertEqual('Security', actual.label)
    self.assertEqual('', actual.docstring)
    self.assertFalse(actual.deprecated)

    label_def = tracker_pb2.LabelDef(
        label='UI', label_docstring='doc', deprecated=True)
    actual = converters.ConvertLabelDef(label_def)
    self.assertEqual('UI', actual.label)
    self.assertEqual('doc', actual.docstring)
    self.assertTrue(actual.deprecated)

  def testConvertComponentDef_Simple(self):
    """We can convert a minimal component definition to protoc."""
    now = 1234567890
    component_def = tracker_pb2.ComponentDef(
        path='Frontend', docstring='doc', created=now, creator_id=111,
        modified=now + 1, modifier_id=111)
    actual = converters.ConvertComponentDef(
        component_def, self.users_by_id, {}, True)
    self.assertEqual('Frontend', actual.path)
    self.assertEqual('doc', actual.docstring)
    self.assertFalse(actual.deprecated)
    self.assertEqual(now, actual.created)
    self.assertEqual(111, actual.creator_ref.user_id)
    self.assertEqual(now + 1, actual.modified)
    self.assertEqual(111, actual.modifier_ref.user_id)
    self.assertEqual('one@example.com', actual.creator_ref.display_name)

  def testConvertComponentDef_Normal(self):
    """We can convert a component def that has CC'd users and adds labels."""
    labels_by_id = {1: 'Security', 2: 'Usability'}
    component_def = tracker_pb2.ComponentDef(
        path='Frontend', admin_ids=[111], cc_ids=[222], label_ids=[1, 2],
        docstring='doc')
    actual = converters.ConvertComponentDef(
        component_def, self.users_by_id, labels_by_id, True)
    self.assertEqual('Frontend', actual.path)
    self.assertEqual('doc', actual.docstring)
    self.assertEqual(1, len(actual.admin_refs))
    self.assertEqual(111, actual.admin_refs[0].user_id)
    self.assertEqual(1, len(actual.cc_refs))
    self.assertFalse(actual.deprecated)
    self.assertEqual(222, actual.cc_refs[0].user_id)
    self.assertEqual(2, len(actual.label_refs))
    self.assertEqual('Security', actual.label_refs[0].label)
    self.assertEqual('Usability', actual.label_refs[1].label)

    # Without include_admin_info, some fields are not set.
    actual = converters.ConvertComponentDef(
        component_def, self.users_by_id, labels_by_id, False)
    self.assertEqual('Frontend', actual.path)
    self.assertEqual('doc', actual.docstring)
    self.assertEqual(0, len(actual.admin_refs))
    self.assertEqual(0, len(actual.cc_refs))
    self.assertFalse(actual.deprecated)
    self.assertEqual(0, len(actual.label_refs))

  def testConvertFieldDef_Simple(self):
    """We can convert a minimal field definition to protoc."""
    field_def = tracker_pb2.FieldDef(
        field_name='EstDays', field_type=tracker_pb2.FieldTypes.INT_TYPE)
    actual = converters.ConvertFieldDef(
        field_def, [], self.users_by_id, self.config, True)
    self.assertEqual('EstDays', actual.field_ref.field_name)
    self.assertEqual(common_pb2.INT_TYPE, actual.field_ref.type)
    self.assertEqual('', actual.field_ref.approval_name)
    self.assertEqual('', actual.applicable_type)
    self.assertEqual('', actual.docstring)
    self.assertEqual(0, len(actual.admin_refs))
    self.assertFalse(actual.is_required)
    self.assertFalse(actual.is_niche)
    self.assertFalse(actual.is_multivalued)
    self.assertFalse(actual.is_phase_field)

    field_def = tracker_pb2.FieldDef(
        field_name='DesignDocs', field_type=tracker_pb2.FieldTypes.URL_TYPE,
        applicable_type='Enhancement', is_required=True, is_niche=True,
        is_multivalued=True, docstring='doc', admin_ids=[111],
        is_phase_field=True)
    actual = converters.ConvertFieldDef(
        field_def, [], self.users_by_id, self.config, True)
    self.assertEqual('DesignDocs', actual.field_ref.field_name)
    self.assertEqual(common_pb2.URL_TYPE, actual.field_ref.type)
    self.assertEqual('', actual.field_ref.approval_name)
    self.assertEqual('Enhancement', actual.applicable_type)
    self.assertEqual('doc', actual.docstring)
    self.assertEqual(1, len(actual.admin_refs))
    self.assertEqual(111, actual.admin_refs[0].user_id)
    self.assertTrue(actual.is_required)
    self.assertTrue(actual.is_niche)
    self.assertTrue(actual.is_multivalued)
    self.assertTrue(actual.is_phase_field)

    # Without include_admin_info, some fields are not set.
    actual = converters.ConvertFieldDef(
        field_def, [], self.users_by_id, self.config, False)
    self.assertEqual('DesignDocs', actual.field_ref.field_name)
    self.assertEqual(common_pb2.URL_TYPE, actual.field_ref.type)
    self.assertEqual('', actual.field_ref.approval_name)
    self.assertEqual('', actual.applicable_type)
    self.assertEqual('doc', actual.docstring)
    self.assertEqual(0, len(actual.admin_refs))
    self.assertFalse(actual.is_required)
    self.assertFalse(actual.is_niche)
    self.assertFalse(actual.is_multivalued)
    self.assertFalse(actual.is_phase_field)

  def testConvertFieldDef_FieldOfAnApproval(self):
    """We can convert a field that is part of an approval."""
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3]
    field_def = tracker_pb2.FieldDef(
        field_name='Waiver', field_type=tracker_pb2.FieldTypes.URL_TYPE,
        approval_id=self.fd_3.field_id)
    actual = converters.ConvertFieldDef(
        field_def, [], self.users_by_id, self.config, True)
    self.assertEqual('Waiver', actual.field_ref.field_name)
    self.assertEqual('LegalApproval', actual.field_ref.approval_name)

  def testConvertFieldDef_UserChoices(self):
    """We can convert an user type field that need special permissions."""
    field_def = tracker_pb2.FieldDef(
        field_name='PM', field_type=tracker_pb2.FieldTypes.USER_TYPE)
    actual = converters.ConvertFieldDef(
        field_def, [111, 333], self.users_by_id, self.config, False)
    self.assertEqual('PM', actual.field_ref.field_name)
    self.assertEqual(
        [111, 333],
        [user_ref.user_id for user_ref in actual.user_choices])
    self.assertEqual(
        ['one@example.com', 'banned@example.com'],
        [user_ref.display_name for user_ref in actual.user_choices])

  def testConvertFieldDef_EnumChoices(self):
    """We can convert an enum type field."""
    field_def = tracker_pb2.FieldDef(
        field_name='Type', field_type=tracker_pb2.FieldTypes.ENUM_TYPE)
    actual = converters.ConvertFieldDef(
        field_def, [], self.users_by_id, self.config, False)
    self.assertEqual('Type', actual.field_ref.field_name)
    self.assertEqual(
        ['Defect', 'Enhancement', 'Task', 'Other'],
        [label_def.label for label_def in actual.enum_choices])

  def testConvertApprovalDef(self):
    """We can convert an ApprovalDef to protoc."""
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3]
    approval_def = tracker_pb2.ApprovalDef(approval_id=3)
    actual = converters.ConvertApprovalDef(
        approval_def, self.users_by_id, self.config, True)
    self.assertEqual('LegalApproval', actual.field_ref.field_name)
    self.assertEqual(common_pb2.APPROVAL_TYPE, actual.field_ref.type)
    self.assertEqual(0, len(actual.approver_refs))
    self.assertEqual('', actual.survey)

    approval_def = tracker_pb2.ApprovalDef(
        approval_id=3, approver_ids=[111], survey='What?')
    actual = converters.ConvertApprovalDef(
        approval_def, self.users_by_id, self.config, True)
    self.assertEqual('LegalApproval', actual.field_ref.field_name)
    self.assertEqual(common_pb2.APPROVAL_TYPE, actual.field_ref.type)
    self.assertEqual(1, len(actual.approver_refs))
    self.assertEqual(111, actual.approver_refs[0].user_id)
    self.assertEqual('What?', actual.survey)

    # Without include_admin_info, some fields are not set.
    actual = converters.ConvertApprovalDef(
        approval_def, self.users_by_id, self.config, False)
    self.assertEqual('LegalApproval', actual.field_ref.field_name)
    self.assertEqual(common_pb2.APPROVAL_TYPE, actual.field_ref.type)
    self.assertEqual(0, len(actual.approver_refs))
    self.assertEqual('', actual.survey)

  def testConvertConfig_Simple(self):
    """We can convert a simple config to protoc."""
    actual = converters.ConvertConfig(
        self.project, self.config, self.users_by_id, {})
    self.assertEqual('proj', actual.project_name)
    self.assertEqual(9, len(actual.status_defs))
    self.assertEqual('New', actual.status_defs[0].status)
    self.assertEqual(17, len(actual.label_defs))
    self.assertEqual('Type-Defect', actual.label_defs[0].label)
    self.assertEqual(
        ['Type', 'Priority', 'Milestone'], actual.exclusive_label_prefixes)
    self.assertEqual(0, len(actual.component_defs))
    self.assertEqual(0, len(actual.field_defs))
    self.assertEqual(0, len(actual.approval_defs))
    self.assertEqual(False, actual.restrict_to_known)
    self.assertEqual(
        ['Duplicate'], [s.status for s in actual.statuses_offer_merge])

  def testConvertConfig_Normal(self):
    """We can convert a config with fields and components to protoc."""
    labels_by_id = {1: 'Security', 2: 'Usability'}
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3]
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI', label_ids=[2])]
    self.config.approval_defs.append(tracker_pb2.ApprovalDef(
        approval_id=3, approver_ids=[111], survey='What?'))
    self.config.restrict_to_known = True
    self.config.statuses_offer_merge = ['Duplicate', 'New']
    actual = converters.ConvertConfig(
        self.project, self.config, self.users_by_id, labels_by_id)
    self.assertEqual(1, len(actual.component_defs))
    self.assertEqual(3, len(actual.field_defs))
    self.assertEqual(1, len(actual.approval_defs))
    self.assertEqual('proj', actual.project_name)
    self.assertEqual(True, actual.restrict_to_known)
    self.assertEqual(
        ['Duplicate', 'New'],
        sorted(s.status for s in actual.statuses_offer_merge))

  def testConvertConfig_FiltersDeletedFieldDefs(self):
    """Deleted fieldDefs don't make it into the config response."""
    labels_by_id = {1: 'Security', 2: 'Usability'}
    deleted_fd1 = tracker_pb2.FieldDef(
        field_name='DeletedField', field_id=100,
        field_type=tracker_pb2.FieldTypes.STR_TYPE,
        applicable_type='',
        is_deleted=True)
    deleted_fd2 = tracker_pb2.FieldDef(
        field_name='RemovedField', field_id=101,
        field_type=tracker_pb2.FieldTypes.ENUM_TYPE,
        applicable_type='',
        is_deleted=True)
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3, deleted_fd1,
        deleted_fd2]
    actual = converters.ConvertConfig(
        self.project, self.config, self.users_by_id, labels_by_id)
    self.assertEqual(3, len(actual.field_defs))

  def testConvertTemplates_Normal(self):
    """We can convert protoc TemplateDefs."""
    templates = [
        tracker_pb2.TemplateDef(name='Chicken'),
        tracker_pb2.TemplateDef(name='Kale')]
    actual = converters.ConvertTemplates(templates)
    expected = [project_objects_pb2.TemplateDef(template_name='Chicken'),
                project_objects_pb2.TemplateDef(template_name='Kale')]
    self.assertEqual(actual, expected)

  def testConvertTemplates_Empty(self):
    """We can convert an empty list of protoc TemplateDefs."""
    actual = converters.ConvertTemplates([])
    self.assertEqual(actual, [])

  def testConvertHotlist(self):
    """We can convert a hotlist to protoc."""
    hotlist = testing_helpers.Blank(
        owner_ids=[111],
        name='Fake-Hotlist',
        summary='A fake hotlist.',
        description='Detailed description of the fake hotlist.')
    actual = converters.ConvertHotlist(hotlist, self.users_by_id)
    self.assertEqual(111, actual.owner_ref.user_id)
    self.assertEqual('one@example.com', actual.owner_ref.display_name)
    self.assertEqual('Fake-Hotlist', actual.name)
    self.assertEqual('A fake hotlist.', actual.summary)
    self.assertEqual(
        'Detailed description of the fake hotlist.', actual.description)

  def testConvertHotlistItem(self):
    """We can convert a HotlistItem to protoc."""
    hotlist = self.services.features.CreateHotlist(
        self.cnxn, 'Fake-Hotlist', 'Summary', 'Description',
        owner_ids=[111], editor_ids=[])
    self.services.features.UpdateHotlistItems(
        self.cnxn, hotlist.hotlist_id, [],
        [(self.issue_1.issue_id, 222, 12345, 'Note')])
    issues_by_id = {self.issue_1.issue_id: self.issue_1}
    related_refs = {}
    configs = {'proj': self.config}

    actual = converters.ConvertHotlistItem(
        hotlist.items[0], issues_by_id, self.users_by_id, related_refs, configs)

    expected_issue = converters.ConvertIssue(
        self.issue_1, self.users_by_id, related_refs, self.config)
    self.assertEqual(
        features_objects_pb2.HotlistItem(
            issue=expected_issue,
            rank=10,
            adder_ref=common_pb2.UserRef(
                user_id=222,
                display_name='two@example.com'),
            added_timestamp=12345,
            note='Note'),
        actual)

  def testConvertValueAndWhy(self):
    """We can covert a dict wth 'why' and 'value' fields to a ValueAndWhy PB."""
    actual = converters.ConvertValueAndWhy({'value': 'Foo', 'why': 'Because'})
    self.assertEqual(
        common_pb2.ValueAndWhy(value='Foo', why='Because'),
        actual)

  def testConvertValueAndWhyList(self):
    """We can convert a list of value and why dicts."""
    actual = converters.ConvertValueAndWhyList([
        {'value': 'A', 'why': 'Because A'},
        {'value': 'B'},
        {'why': 'Why what?'},
        {}])
    self.assertEqual(
        [common_pb2.ValueAndWhy(value='A', why='Because A'),
         common_pb2.ValueAndWhy(value='B'),
         common_pb2.ValueAndWhy(why='Why what?'),
         common_pb2.ValueAndWhy()],
        actual)

  def testRedistributeEnumFieldsIntoLabels(self):
    # function called and tests covered by
    # IngestIssueDelta and IngestApprovalDelta
    pass
