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
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

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
    config.field_defs = [fd_1, fd_2, fd_3]
    fv_1 = tracker_bizobj.MakeFieldValue(
        1, None, 'string', None, None, None, False)
    fv_2 = tracker_bizobj.MakeFieldValue(
        2, 34, None, None, None, None, False)
    approval_value.subfield_values = [fv_1, fv_2]

    users_by_id = {
        111L: testing_helpers.Blank(display_name='one@example.com'),
        222L: testing_helpers.Blank(display_name='two@example.com'),
        }

    phase = tracker_pb2.Phase(phase_id=1, name='Canary')

    actual = converters.ConvertApproval(
        approval_value, users_by_id, config, phase=phase)
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
    users_by_id = {
        111L: testing_helpers.Blank(display_name='user@example.com'),
        }
    # No specified user
    actual = converters.ConvertUserRef(None, None, users_by_id)
    expected = common_pb2.UserRef(
        user_id=0, is_derived=False, display_name='----')
    self.assertEqual(expected, actual)

    # Explicitly specified user
    actual = converters.ConvertUserRef(111L, None, users_by_id)
    expected = common_pb2.UserRef(
        user_id=111L, is_derived=False, display_name='user@example.com')
    self.assertEqual(expected, actual)

    # Derived user
    actual = converters.ConvertUserRef(None, 111L, users_by_id)
    expected = common_pb2.UserRef(
        user_id=111L, is_derived=True, display_name='user@example.com')
    self.assertEqual(expected, actual)

  def testConvertUserRefs(self):
    """We can convert lists of user_ids into UserRefs."""
    users_by_id = {
        111L: testing_helpers.Blank(display_name='one@example.com'),
        222L: testing_helpers.Blank(display_name='two@example.com'),
        }
    # No specified users
    actual = converters.ConvertUserRefs(
        [], [], users_by_id)
    expected = []
    self.assertEqual(expected, actual)

    # A mix of explicit and derived users
    actual = converters.ConvertUserRefs(
        [111L], [222L], users_by_id)
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
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI'),
      tracker_pb2.ComponentDef(component_id=2, path='DB'),
      ]

    # No components specified
    actual = converters.ConvertComponents([], [], config)
    self.assertEqual([], actual)

    # A mix of explicit and derived components
    actual = converters.ConvertComponents([1], [2], config)
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
    users_by_id = {
        111L: testing_helpers.Blank(display_name='one@example.com'),
        222L: testing_helpers.Blank(display_name='two@example.com'),
        }
    related_refs_dict = {
        78901: ('proj', 1),
        78902: ('proj', 2),
        }
    now = 12345678
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI'),
      tracker_pb2.ComponentDef(component_id=2, path='DB'),
      ]
    issue = fake.MakeTestIssue(
      789, 3, 'sum', 'New', 111L, labels=['Hot'],
      derived_labels=['Scalability'], star_count=12, reporter_id=222L,
      opened_timestamp=now, component_ids=[1], project_name='proj',
      cc_ids=[111L], derived_cc_ids=[222L])

    actual = converters.ConvertIssue(
        issue, users_by_id, related_refs_dict, config)

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
        opened_timestamp=now, star_count=12, is_spam=False, attachment_count=0
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
