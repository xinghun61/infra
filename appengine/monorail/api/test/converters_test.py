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
from services import service_manager


class ConverterFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.users_by_id = {
        111L: testing_helpers.Blank(
            display_name='one@example.com', banned=False),
        222L: testing_helpers.Blank(
            display_name='two@example.com', banned=False),
        333L: testing_helpers.Blank(
            display_name='banned@example.com', banned=True),
        }

    self.services = service_manager.Services(
        user = fake.UserService()
    )

    self.cnxn = fake.MonorailConnection()

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
        field_ref=common_pb2.FieldRef(
            field_name='Accessibility', type=common_pb2.APPROVAL_TYPE),
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
        field_ref=common_pb2.FieldRef(
            field_name='', type=common_pb2.APPROVAL_TYPE),
        approver_refs=[
            common_pb2.UserRef(user_id=111L, display_name='one@example.com'),
            ],
        status=issue_objects_pb2.NOT_SET,
        set_on=now,
        setter_ref=common_pb2.UserRef(
            user_id=111L, display_name='one@example.com'),
        subfield_values=[
            issue_objects_pb2.FieldValue(
                field_ref=common_pb2.FieldRef(
                    field_name='EstDays', type=common_pb2.INT_TYPE),
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

    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3]
    fv_1 = tracker_bizobj.MakeFieldValue(
        1, None, 'string', None, None, None, False)
    fv_2 = tracker_bizobj.MakeFieldValue(
        2, 34, None, None, None, None, False)
    approval_value.subfield_values = [fv_1, fv_2]

    phase = tracker_pb2.Phase(phase_id=1, name='Canary')

    actual = converters.ConvertApproval(
        approval_value, self.users_by_id, self.config, phase=phase)
    expected = issue_objects_pb2.Approval(
        field_ref=common_pb2.FieldRef(
            field_name='LegalApproval', type=common_pb2.APPROVAL_TYPE),
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
                field_ref=common_pb2.FieldRef(
                    field_name='FirstField', type=common_pb2.STR_TYPE),
                value='string',
                is_derived=False
            ),
            issue_objects_pb2.FieldValue(
                field_ref=common_pb2.FieldRef(
                    field_name='SecField', type=common_pb2.INT_TYPE),
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

  def testConvertFieldType(self):
    self.assertEqual(
        common_pb2.STR_TYPE,
        converters.ConvertFieldType(tracker_pb2.FieldTypes.STR_TYPE))

    self.assertEqual(
        common_pb2.URL_TYPE,
        converters.ConvertFieldType(tracker_pb2.FieldTypes.URL_TYPE))

  def testConvertFieldRef(self):
    actual = converters.ConvertFieldRef(
        'SomeName', tracker_pb2.FieldTypes.ENUM_TYPE)
    self.assertEqual(
        actual,
        common_pb2.FieldRef(field_name='SomeName', type=common_pb2.ENUM_TYPE))

  def testConvertFieldValue(self):
    """We can convert one FieldValueView item to a protoc FieldValue."""
    actual = converters.ConvertFieldValue(
        'Size', 123, tracker_pb2.FieldTypes.INT_TYPE, 'Canary')
    expected = issue_objects_pb2.FieldValue(
        field_ref=common_pb2.FieldRef(
            field_name='Size', type=common_pb2.INT_TYPE),
        value='123',
        phase_ref=issue_objects_pb2.PhaseRef(phase_name='Canary'))
    self.assertEqual(expected, actual)

    actual = converters.ConvertFieldValue(
        'Size', 123, tracker_pb2.FieldTypes.INT_TYPE, '', is_derived=True)
    expected = issue_objects_pb2.FieldValue(
        field_ref=common_pb2.FieldRef(
            field_name='Size', type=common_pb2.INT_TYPE),
        value='123',
        is_derived=True)
    self.assertEqual(expected, actual)

  def testConvertFieldValues(self):
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_4, self.fd_5]
    fv_1 = tracker_bizobj.MakeFieldValue(
        1, None, 'string', None, None, None, False)
    fv_2 = tracker_bizobj.MakeFieldValue(
        2, 34, None, None, None, None, False)
    labels = ['Pre-label', 'not-label-enum', 'prenot-label']
    der_labels =  ['Pre-label2']
    phases = [tracker_pb2.Phase(name='Canary', phase_id=17)]
    fv_1.phase_id=17

    actual = converters.ConvertFieldValues(
        self.config, labels, der_labels, [fv_1, fv_2], {}, phases=phases)

    expected = [
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(
              field_name='FirstField',
              type=common_pb2.STR_TYPE),
          value='string',
          phase_ref=issue_objects_pb2.PhaseRef(phase_name='Canary')),
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(
              field_name='SecField',
              type=common_pb2.INT_TYPE),
          value='34'),
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(
              field_name='Pre', type=common_pb2.ENUM_TYPE),
          value='label'),
      issue_objects_pb2.FieldValue(
          field_ref=common_pb2.FieldRef(
              field_name='Pre', type=common_pb2.ENUM_TYPE),
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

  def testConvertAmendment(self):
    pass  # TODO(jrobbins): Implement this.

  def testConvertAttachment(self):
    pass  # TODO(jrobbins): Implement this.

  def testConvertComment(self):
    """We can convert a protorpc IssueComment to a protoc Comment."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111L, project_name='proj')
    comment = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=111L, timestamp=now,
        content='a comment', sequence=12)

    # Normal comment.
    actual = converters.ConvertComment(
        issue, comment, self.users_by_id, self.config, {}, None)
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111L, display_name='one@example.com'),
        timestamp=now, content='a comment', is_spam=False)
    self.assertEqual(expected, actual)

    # Comment that was deleted and now viewed by comment author.
    comment.deleted_by = 111L
    actual = converters.ConvertComment(
        issue, comment, self.users_by_id, self.config, {}, 111L)
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=True,
        commenter=common_pb2.UserRef(
            user_id=111L, display_name='one@example.com'),
        timestamp=now, content='a comment', is_spam=False)
    self.assertEqual(expected, actual)

    # Comment that was deleted and now viewed by some other user.
    actual = converters.ConvertComment(
        issue, comment, self.users_by_id, self.config, {}, 222L)
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=True,
        timestamp=now, is_spam=False)
    self.assertEqual(expected, actual)
    comment.deleted_by = None

    # Description.
    comment.is_description = True
    actual = converters.ConvertComment(
        issue, comment, self.users_by_id, self.config, {101: 1}, None)
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111L, display_name='one@example.com'),
        timestamp=now, content='a comment', is_spam=False, description_num=1)
    self.assertEqual(expected, actual)
    comment.is_description = False

    # Comment on an approval.
    self.config.field_defs.append(tracker_pb2.FieldDef(
        field_id=11, project_id=789, field_name='Accessibility',
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE,
        applicable_type='Launch'))
    self.config.approval_defs.append(tracker_pb2.ApprovalDef(
        approval_id=11, approver_ids=[111L], survey='survey 1'))
    comment.approval_id = 11
    actual = converters.ConvertComment(
        issue, comment, self.users_by_id, self.config, {}, None)
    expected = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=12, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111L, display_name='one@example.com'),
        timestamp=now, content='a comment', is_spam=False,
        approval_ref=common_pb2.FieldRef(field_name='Accessibility'))
    self.assertEqual(expected, actual)

  def testConvertCommentList(self):
    """We can convert a list of comments."""
    now = 1234567890
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111L, project_name='proj')
    comment_0 = tracker_pb2.IssueComment(
        id=100, project_id=789, user_id=111L, timestamp=now,
        content='a description', sequence=0, is_description=True)
    comment_1 = tracker_pb2.IssueComment(
        id=101, project_id=789, user_id=222L, timestamp=now,
        content='a comment', sequence=1)
    comment_2 = tracker_pb2.IssueComment(
        id=102, project_id=789, user_id=222L, timestamp=now,
        content='deleted comment', sequence=2, deleted_by=111L)
    comment_3 = tracker_pb2.IssueComment(
        id=103, project_id=789, user_id=111L, timestamp=now,
        content='another desc', sequence=3, is_description=True)

    actual = converters.ConvertCommentList(
        issue, [comment_0, comment_1, comment_2, comment_3], self.users_by_id,
        self.config, 222L)

    expected_0 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=0, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111L, display_name='one@example.com'),
        timestamp=now, content='a description', is_spam=False,
        description_num=1)
    expected_1 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=1, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=222L, display_name='two@example.com'),
        timestamp=now, content='a comment', is_spam=False)
    expected_2 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=2, is_deleted=True,
        commenter=common_pb2.UserRef(
            user_id=222L, display_name='two@example.com'),
        timestamp=now, content='deleted comment', is_spam=False)
    expected_3 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=3, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111L, display_name='one@example.com'),
        timestamp=now, content='another desc', is_spam=False,
        description_num=2)
    self.assertEqual(expected_0, actual[0])
    self.assertEqual(expected_1, actual[1])
    self.assertEqual(expected_2, actual[2])
    self.assertEqual(expected_3, actual[3])

  def testIngestApprovalDelta(self):
    self.services.user.TestAddUser('user1@example.com', 111L)
    self.services.user.TestAddUser('user2@example.com', 222L)

    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3, self.fd_4]

    approval_delta = issue_objects_pb2.ApprovalDelta(
        status=issue_objects_pb2.APPROVED,
        approver_refs_add=[common_pb2.UserRef(user_id=111L)],
        approver_refs_remove=[common_pb2.UserRef(user_id=222L)],
        field_vals_add=[
            issue_objects_pb2.FieldValue(
                value='string', field_ref=common_pb2.FieldRef(
                    field_name='FirstField'))],
        field_vals_remove=[
            issue_objects_pb2.FieldValue(
                value='34', field_ref=common_pb2.FieldRef(
                    field_name='SecField'))],
        )

    actual = converters.IngestApprovalDelta(
        self.cnxn, self.services.user, approval_delta, 333L, self.config)
    self.assertEqual(
        actual.status, tracker_pb2.ApprovalStatus.APPROVED,)
    self.assertEqual(actual.setter_id, 333L)
    self.assertEqual(actual.approver_ids_add, [111L])
    self.assertEqual(actual.approver_ids_remove, [222L])
    self.assertEqual(actual.subfield_vals_add, [tracker_pb2.FieldValue(
        str_value='string', field_id=1, derived=False)])
    self.assertEqual(actual.subfield_vals_remove, [tracker_pb2.FieldValue(
        int_value=34, field_id=2, derived=False)])

    # test a NOT_SET status is registered as None.
    approval_delta.status = issue_objects_pb2.NOT_SET
    actual = converters.IngestApprovalDelta(
        self.cnxn, self.services.user, approval_delta, 333L, self.config)
    self.assertIsNone(actual.status)

  def testIngestApprovalStatus(self):
    actual = converters.IngestApprovalStatus(issue_objects_pb2.NOT_SET)
    self.assertEqual(actual, tracker_pb2.ApprovalStatus.NOT_SET)

    actual = converters.IngestApprovalStatus(issue_objects_pb2.NOT_APPROVED)
    self.assertEqual(actual, tracker_pb2.ApprovalStatus.NOT_APPROVED)

  def testIngestFieldValues(self):
    self.services.user.TestAddUser('user1@example.com', 111L)
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_4]

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
          field_ref=common_pb2.FieldRef(field_name='UserField')
        )
    ]

    actual = converters.IngestFieldValues(
        self.cnxn, self.services.user, field_values, self.config)
    self.assertEqual(
        actual,
        [
            tracker_pb2.FieldValue(
                str_value='string', field_id=1, derived=False),
            tracker_pb2.FieldValue(int_value=34, field_id=2, derived=False),
            tracker_pb2.FieldValue(user_id=111L, field_id=4, derived=False)
        ]
    )
