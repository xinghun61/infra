# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for converting internal protorpc to external protoc."""

import unittest

from api import converters
from api.api_proto import common_pb2
from api.api_proto import issue_objects_pb2
from proto import tracker_pb2
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


class ConverterFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.users_by_id = {
        111L: testing_helpers.Blank(display_name='one@example.com'),
        222L: testing_helpers.Blank(display_name='two@example.com'),
        }

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
        approval_id=11, approver_ids=[111L], survey='survey 1'))
    self.config.approval_defs.append(tracker_pb2.ApprovalDef(
        approval_id=12, approver_ids=[111L], survey='survey 2'))
    av_11 = tracker_pb2.ApprovalValue(
        approval_id=11, status=tracker_pb2.ApprovalStatus.NEED_INFO,
        setter_id=111L, set_on=now, approver_ids=[111L, 222L],
        phase_id=21)
    av_12 = tracker_pb2.ApprovalValue(  # Note: no approval def, no phase.
        approval_id=12, status=tracker_pb2.ApprovalStatus.NOT_SET,
        setter_id=111L, set_on=now, approver_ids=[111L])
    av_12.subfield_values.append(tracker_pb2.FieldValue(
        field_id=1, int_value=123))
    phase_21 = tracker_pb2.Phase(phase_id=21, name='Stable', rank=1)
    actual = converters.ConvertApprovalValues(
        [av_11, av_12], [phase_21], self.users_by_id, self.config)

    expected_av_1 = issue_objects_pb2.Approval(
        field_ref=common_pb2.FieldRef(field_name='Accessibility'),
        approver_refs=[
            common_pb2.UserRef(user_id=111L, display_name='one@example.com'),
            common_pb2.UserRef(user_id=222L, display_name='two@example.com'),
            ],
        status=issue_objects_pb2.NEED_INFO,
        set_on=now,
        setter_ref=common_pb2.UserRef(
            user_id=111L, display_name='one@example.com'),
        phase_ref=issue_objects_pb2.PhaseRef(phase_name='Stable'))

    expected_av_2 = issue_objects_pb2.Approval(
        field_ref=common_pb2.FieldRef(field_name=''),
        approver_refs=[
            common_pb2.UserRef(user_id=111L, display_name='one@example.com'),
            ],
        status=issue_objects_pb2.NOT_SET,
        set_on=now,
        setter_ref=common_pb2.UserRef(
            user_id=111L, display_name='one@example.com'),
        subfield_values=[
            issue_objects_pb2.FieldValue(
                field_ref=common_pb2.FieldRef(field_name='EstDays'),
                value='123'),
            ],
        phase_ref=issue_objects_pb2.PhaseRef(),
        )

    self.assertEqual([expected_av_1, expected_av_2], actual)

  def testConvertApproval(self):
    """We can convert ApprovalValues to protoc Approvals."""
    approval_value = tracker_pb2.ApprovalValue(
        approval_id=3,
        status=tracker_pb2.ApprovalStatus.NEED_INFO,
        setter_id=222L,
        set_on=2345,
        approver_ids=[111L],
        phase_id=1
    )

    fd_1 = tracker_pb2.FieldDef(
        field_name='FirstField', field_id=1,
        field_type=tracker_pb2.FieldTypes.STR_TYPE,
        applicable_type='')
    fd_2 = tracker_pb2.FieldDef(
        field_name='SecField', field_id=2,
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        applicable_type='')
    fd_3 = tracker_pb2.FieldDef(
        field_name='LegalApproval', field_id=3,
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE,
        applicable_type='')
    self.config.field_defs = [fd_1, fd_2, fd_3]
    fv_1 = tracker_bizobj.MakeFieldValue(
        1, None, 'string', None, None, None, False)
    fv_2 = tracker_bizobj.MakeFieldValue(
        2, 34, None, None, None, None, False)
    approval_value.subfield_values = [fv_1, fv_2]

    phase = tracker_pb2.Phase(phase_id=1, name='Canary')

    actual = converters.ConvertApproval(
        approval_value, self.users_by_id, self.config, phase=phase)
    expected = issue_objects_pb2.Approval(
        field_ref=common_pb2.FieldRef(field_name='LegalApproval'),
        approver_refs=[common_pb2.UserRef(
            user_id=111L, display_name='one@example.com', is_derived=False)
          ],
        status=5,
        set_on=2345,
        setter_ref=common_pb2.UserRef(
            user_id=222L, display_name='two@example.com', is_derived=False
        ),
        subfield_values=[
            issue_objects_pb2.FieldValue(
                field_ref=common_pb2.FieldRef(field_name='FirstField'),
                value='string',
                is_derived=False
            ),
            issue_objects_pb2.FieldValue(
                field_ref=common_pb2.FieldRef(field_name='SecField'),
                value='34',
                is_derived=False
            )
        ],
        phase_ref=issue_objects_pb2.PhaseRef(phase_name='Canary')
    )

    self.assertEqual(expected, actual)

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
    actual = converters.ConvertUserRef(111L, None, self.users_by_id)
    expected = common_pb2.UserRef(
        user_id=111L, is_derived=False, display_name='one@example.com')
    self.assertEqual(expected, actual)

    # Derived user
    actual = converters.ConvertUserRef(None, 111L, self.users_by_id)
    expected = common_pb2.UserRef(
        user_id=111L, is_derived=True, display_name='one@example.com')
    self.assertEqual(expected, actual)

  def testConvertUserRefs(self):
    """We can convert lists of user_ids into UserRefs."""
    # No specified users
    actual = converters.ConvertUserRefs(
        [], [], self.users_by_id)
    expected = []
    self.assertEqual(expected, actual)

    # A mix of explicit and derived users
    actual = converters.ConvertUserRefs(
        [111L], [222L], self.users_by_id)
    expected = [
      common_pb2.UserRef(
          user_id=111L, is_derived=False, display_name='one@example.com'),
      common_pb2.UserRef(
          user_id=222L, is_derived=True, display_name='two@example.com'),
      ]
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

  def testConvertComponents(self):
    """We can convert a list of components."""
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI'),
      tracker_pb2.ComponentDef(component_id=2, path='DB'),
      ]

    # No components specified
    actual = converters.ConvertComponents([], [], self.config)
    self.assertEqual([], actual)

    # A mix of explicit and derived components
    actual = converters.ConvertComponents([1], [2], self.config)
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

  def testConvertFieldValueItem(self):
    """We can convert one FieldValueView item to a protoc FieldValue."""
    ffv = testing_helpers.Blank(val=123)
    actual = converters.ConvertFieldValueItem('Size', ffv)
    expected = issue_objects_pb2.FieldValue(
        field_ref=common_pb2.FieldRef(field_name='Size'),
        value='123')
    self.assertEqual(expected, actual)

    actual = converters.ConvertFieldValueItem('Size', ffv, is_derived=True)
    expected = issue_objects_pb2.FieldValue(
        field_ref=common_pb2.FieldRef(field_name='Size'),
        value='123', is_derived=True)
    self.assertEqual(expected, actual)

  def testConvertFieldValueViews(self):
    ffv_1 = testing_helpers.Blank(
        field_name='Size', values=[testing_helpers.Blank(val=123)],
        derived_values=[])
    ffv_2 = testing_helpers.Blank(
        field_name='Channels', values=[testing_helpers.Blank(val='Beta')],
        derived_values=[testing_helpers.Blank(val='Dev')])
    actual = converters.ConvertFieldValueViews([ffv_1, ffv_2])
    expected = [
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(field_name='Size'),
          value='123'),
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(field_name='Channels'),
          value='Beta'),
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(field_name='Channels'),
          value='Dev', is_derived=True),
      ]
    self.assertEqual(expected, actual)

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
      789, 3, 'sum', 'New', 111L, labels=['Hot'],
      derived_labels=['Scalability'], star_count=12, reporter_id=222L,
      opened_timestamp=now, component_ids=[1], project_name='proj',
      cc_ids=[111L], derived_cc_ids=[222L])
    issue.phases = [
        tracker_pb2.Phase(phase_id=1, name='Dev', rank=1),
        tracker_pb2.Phase(phase_id=2, name='Beta', rank=2),
        ]

    actual = converters.ConvertIssue(
        issue, self.users_by_id, related_refs_dict, self.config)

    expected = issue_objects_pb2.Issue(
        project_name='proj', local_id=3, summary='sum',
        status_ref=common_pb2.StatusRef(
            status='New', is_derived=False, means_open=True),
        owner_ref=common_pb2.UserRef(
            user_id=111L, display_name='one@example.com', is_derived=False),
        cc_refs=[common_pb2.UserRef(
                     user_id=111L, display_name='one@example.com',
                     is_derived=False),
                 common_pb2.UserRef(
                     user_id=222L, display_name='two@example.com',
                     is_derived=True)],
        label_refs=[common_pb2.LabelRef(label='Hot', is_derived=False),
                    common_pb2.LabelRef(label='Scalability', is_derived=True)],
        component_refs=[common_pb2.ComponentRef(path='UI', is_derived=False)],
        is_deleted=False,
        reporter_ref=common_pb2.UserRef(
            user_id=222L, display_name='two@example.com', is_derived=False),
        opened_timestamp=now, star_count=12, is_spam=False, attachment_count=0,
        phases=[
            issue_objects_pb2.PhaseDef(
              phase_ref=issue_objects_pb2.PhaseRef(phase_name='Dev'),
              rank=1),
            issue_objects_pb2.PhaseDef(
              phase_ref=issue_objects_pb2.PhaseRef(phase_name='Beta'),
              rank=2)],
        )
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
