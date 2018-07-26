# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for converting internal protorpc to external protoc."""

from mock import Mock, patch
import unittest

from google.protobuf import wrappers_pb2

from api import converters
from api.api_proto import common_pb2
from api.api_proto import issue_objects_pb2
from api.api_proto import issues_pb2
from api.api_proto import users_pb2
from framework import exceptions
from proto import tracker_pb2
from proto import user_pb2
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj
from services import service_manager


class ConverterFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.users_by_id = {
        111L: testing_helpers.Blank(
            display_name='one@example.com', banned=False),
        222L: testing_helpers.Blank(
            display_name='two@example.com', banned=False),
        333L: testing_helpers.Blank(
            display_name='banned@example.com', banned=True),
        }

    self.services = service_manager.Services(
        issue=fake.IssueService(),
        project=fake.ProjectService(),
        user=fake.UserService())
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

  def testConvertUser(self):
    """We can convert lists of protorpc Users to protoc Users."""
    user1 = user_pb2.User(user_id=1, email='user1@example.com')
    user2 = user_pb2.User(user_id=2, email='user2@example.com')
    actual = converters.ConvertUsers([user1, user2])
    self.assertEqual(len(actual), 2)
    self.assertItemsEqual(
        actual,
        [users_pb2.User(user_id=1, email='user1@example.com'),
         users_pb2.User(user_id=2, email='user2@example.com')])

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
        'SomeName', tracker_pb2.FieldTypes.ENUM_TYPE, None)
    self.assertEqual(
        actual,
        common_pb2.FieldRef(field_name='SomeName', type=common_pb2.ENUM_TYPE))

  def testConvertFieldValue(self):
    """We can convert one FieldValueView item to a protoc FieldValue."""
    actual = converters.ConvertFieldValue(
        'Size', 123, tracker_pb2.FieldTypes.INT_TYPE, phase_name='Canary')
    expected = issue_objects_pb2.FieldValue(
        field_ref=common_pb2.FieldRef(
            field_name='Size', type=common_pb2.INT_TYPE),
        value='123',
        phase_ref=issue_objects_pb2.PhaseRef(phase_name='Canary'))
    self.assertEqual(expected, actual)

    actual = converters.ConvertFieldValue(
        'Size', 123, tracker_pb2.FieldTypes.INT_TYPE, 'Legal', '',
        is_derived=True)
    expected = issue_objects_pb2.FieldValue(
        field_ref=common_pb2.FieldRef(
            field_name='Size', type=common_pb2.INT_TYPE, approval_name='Legal'),
        value='123',
        is_derived=True)
    self.assertEqual(expected, actual)

  def testConvertFieldValues(self):
    self.fd_2.approval_id = 3
    self.config.field_defs = [
        self.fd_1, self.fd_2, self.fd_3, self.fd_4, self.fd_5]
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
              type=common_pb2.INT_TYPE,
              approval_name='LegalApproval'),
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
    """We can convert various kinds of Amendments."""
    amend = tracker_pb2.Amendment(
        field=tracker_pb2.FieldID.SUMMARY, newvalue='new', oldvalue='old')
    actual = converters.ConvertAmendment(amend, self.users_by_id)
    self.assertEqual('Summary', actual.field_name)
    self.assertEqual('new', actual.new_or_delta_value)
    self.assertEqual('old', actual.old_value)

    amend = tracker_pb2.Amendment(
        field=tracker_pb2.FieldID.OWNER, added_user_ids=[111L])
    actual = converters.ConvertAmendment(amend, self.users_by_id)
    self.assertEqual('Owner', actual.field_name)
    self.assertEqual('one@example.com', actual.new_or_delta_value)
    self.assertEqual('', actual.old_value)

    amend = tracker_pb2.Amendment(
        field=tracker_pb2.FieldID.CC,
        added_user_ids=[111L], removed_user_ids=[222L])
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

  def testIngestUserRefs_ClearTheOwnerField(self):
    """We can look up user IDs for protoc UserRefs."""
    ref = common_pb2.UserRef(user_id=0)
    actual = converters.IngestUserRefs(self.cnxn, [ref], self.services.user)
    self.assertEqual([0], actual)

  def testIngestUserRefs_ByExistingID(self):
    """Users can be specified by user_id."""
    self.services.user.TestAddUser('user1@example.com', 111L)
    ref = common_pb2.UserRef(user_id=111L)
    actual = converters.IngestUserRefs(self.cnxn, [ref], self.services.user)
    self.assertEqual([111L], actual)

  def testIngestUserRefs_ByNonExistingID(self):
    """We reject references to non-existing user IDs."""
    ref = common_pb2.UserRef(user_id=999L)
    with self.assertRaises(exceptions.NoSuchUserException):
      converters.IngestUserRefs(self.cnxn, [ref], self.services.user)

  def testIngestUserRefs_ByExistingEmail(self):
    """Existing users can be specified by email address."""
    self.services.user.TestAddUser('user1@example.com', 111L)
    ref = common_pb2.UserRef(display_name='user1@example.com')
    actual = converters.IngestUserRefs(self.cnxn, [ref], self.services.user)
    self.assertEqual([111L], actual)

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
    ref = common_pb2.UserRef(display_name='Bob')
    converters.IngestUserRefs(
        self.cnxn, [ref], self.services.user, autocreate=True)
    with self.assertRaises(exceptions.NoSuchUserException):
      self.services.user.LookupUserID(self.cnxn, 'Bob')

  def testIngestUserRefs_MixOfIDAndEmail(self):
    """Requests can specify some users by ID and others by email."""
    self.services.user.TestAddUser('user1@example.com', 111L)
    self.services.user.TestAddUser('user2@example.com', 222L)
    self.services.user.TestAddUser('user3@example.com', 333L)
    ref1 = common_pb2.UserRef(display_name='user1@example.com')
    ref2 = common_pb2.UserRef(display_name='user2@example.com')
    ref3 = common_pb2.UserRef(user_id=333L)
    actual = converters.IngestUserRefs(
        self.cnxn, [ref1, ref2, ref3], self.services.user)
    self.assertEqual([111L, 222L, 333L], actual)

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

  def testIngestIssueDelta_Empty(self):
    """An empty protorpc IssueDelta makes an empty protoc IssueDelta."""
    delta = issues_pb2.IssueDelta()
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, [])
    expected = tracker_pb2.IssueDelta()
    self.assertEqual(expected, actual)

  def testIngestIssueDelta_BuiltInFields(self):
    """We can create a protorpc IssueDelta from a protoc IssueDelta."""
    self.services.user.TestAddUser('user1@example.com', 111L)
    self.services.user.TestAddUser('user2@example.com', 222L)
    self.services.user.TestAddUser('user3@example.com', 333L)
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI')]
    delta = issues_pb2.IssueDelta(
        status=wrappers_pb2.StringValue(value='Fixed'),
        owner_ref=common_pb2.UserRef(user_id=222L),
        summary=wrappers_pb2.StringValue(value='New summary'),
        cc_refs_add=[common_pb2.UserRef(user_id=333L)],
        comp_refs_add=[common_pb2.ComponentRef(path='UI')],
        label_refs_add=[common_pb2.LabelRef(label='Hot')])
    actual = converters.IngestIssueDelta(
        self.cnxn, self.services, delta, self.config, [])
    expected = tracker_pb2.IssueDelta(
        status='Fixed', owner_id=222L, summary='New summary',
        cc_ids_add=[333L], comp_ids_add=[1],
        labels_add=['Hot'])
    self.assertEqual(expected, actual)

  def testIngestIssueDelta_InvalidComponent(self):
    """We reject a protorpc IssueDelta that has an invalid component."""
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI')]
    delta = issues_pb2.IssueDelta(
        comp_refs_add=[common_pb2.ComponentRef(path='XYZ')])
    with self.assertRaises(exceptions.NoSuchComponentException):
      converters.IngestIssueDelta(
          self.cnxn, self.services, delta, self.config, [])

  def testIngestIssueDelta_CustomFields(self):
    """We can create a protorpc IssueDelta from a protoc IssueDelta."""
    self.config.field_defs = [
        self.fd_1, self.fd_2, self.fd_3, self.fd_4, self.fd_6]
    phases = [tracker_pb2.Phase(phase_id=1, name="Beta")]
    delta = issues_pb2.IssueDelta(
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
    delta = issues_pb2.IssueDelta(
        fields_clear=[common_pb2.FieldRef(field_name='FirstField')])
    with self.assertRaises(exceptions.NoSuchFieldDefException):
      converters.IngestIssueDelta(
          self.cnxn, self.services, delta, self.config, [])

  def testIngestIssueDelta_RelatedIssues(self):
    """We can create a protorpc IssueDelta that references related issues."""
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111L)
    self.services.issue.TestAddIssue(issue)
    delta = issues_pb2.IssueDelta(
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
    delta = issues_pb2.IssueDelta(
        merged_into_ref=common_pb2.IssueRef(
            project_name='not-a-proj', local_id=8))
    with self.assertRaises(exceptions.NoSuchProjectException):
      converters.IngestIssueDelta(
          self.cnxn, self.services, delta, self.config, [])

    delta = issues_pb2.IssueDelta(
        merged_into_ref=common_pb2.IssueRef(
            project_name='proj', local_id=999))
    with self.assertRaises(exceptions.NoSuchIssueException):
      converters.IngestIssueDelta(
          self.cnxn, self.services, delta, self.config, [])

  def testIngestAttachmentUploads_Empty(self):
    """Uploading zero files results in an empty list of attachments."""
    self.assertEqual([], converters.IngestAttachmentUploads([]))

  def testIngestAttachmentUploads_Normal(self):
    """Uploading files results in a list of attachments."""
    uploads = [
        issues_pb2.AttachmentUpload(
            filename='hello.c', content='int main() {}'),
        issues_pb2.AttachmentUpload(
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
          issues_pb2.AttachmentUpload(content='name is mssing')])

    with self.assertRaises(exceptions.InputException):
      converters.IngestAttachmentUploads([
          issues_pb2.AttachmentUpload(filename='content is mssing')])

  def testIngestApprovalDelta(self):
    self.services.user.TestAddUser('user1@example.com', 111L)
    self.services.user.TestAddUser('user2@example.com', 222L)

    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3, self.fd_4]

    approval_delta = issues_pb2.ApprovalDelta(
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
        fields_clear=[common_pb2.FieldRef(field_name='FirstField')]
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
    self.assertEqual(actual.subfields_clear, [1])

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
            tracker_pb2.FieldValue(user_id=111L, field_id=4, derived=False),
            tracker_pb2.FieldValue(
                int_value=2, field_id=6, phase_id=1, derived=False)
        ]
    )

  def testConvertStatusDef(self):
    """We can convert a status definition to protoc."""
    status_def = tracker_pb2.StatusDef(status='Started')
    actual = converters.ConvertStatusDef(status_def, 1)
    self.assertEqual('Started', actual.status)
    self.assertFalse(actual.means_open)
    self.assertEqual('', actual.docstring)
    self.assertFalse(actual.deprecated)
    self.assertEqual(1, actual.rank)

    status_def = tracker_pb2.StatusDef(
        status='New', means_open=True, status_docstring='doc', deprecated=True)
    actual = converters.ConvertStatusDef(status_def, 2)
    self.assertEqual('New', actual.status)
    self.assertTrue(actual.means_open)
    self.assertEqual('doc', actual.docstring)
    self.assertTrue(actual.deprecated)
    self.assertEqual(2, actual.rank)

  def testConvertLabelDef(self):
    """We can convert a label definition to protoc."""
    label_def = tracker_pb2.LabelDef(label='Security')
    actual = converters.ConvertLabelDef(label_def, 1)
    self.assertEqual('Security', actual.label)
    self.assertEqual('', actual.docstring)
    self.assertFalse(actual.deprecated)
    self.assertEqual(1, actual.rank)

    label_def = tracker_pb2.LabelDef(
        label='UI', label_docstring='doc', deprecated=True)
    actual = converters.ConvertLabelDef(label_def, 2)
    self.assertEqual('UI', actual.label)
    self.assertEqual('doc', actual.docstring)
    self.assertTrue(actual.deprecated)
    self.assertEqual(2, actual.rank)

  def testConvertComponentDef_Simple(self):
    """We can convert a minimal component definition to protoc."""
    now = 1234567890
    component_def = tracker_pb2.ComponentDef(
        path='Frontend', docstring='doc', created=now, creator_id=111L,
        modified=now + 1, modifier_id=111L)
    actual = converters.ConvertComponentDef(
        component_def, self.users_by_id, {})
    self.assertEqual('Frontend', actual.path)
    self.assertEqual('doc', actual.docstring)
    self.assertEqual(now, actual.created)
    self.assertEqual(111L, actual.creator_ref.user_id)
    self.assertEqual(now + 1, actual.modified)
    self.assertEqual(111L, actual.modifier_ref.user_id)
    self.assertEqual('one@example.com', actual.creator_ref.display_name)

  def testConvertComponentDef_Normal(self):
    """We can convert a component def that has CC'd users and adds labels."""
    labels_by_id = {1: 'Security', 2: 'Usability'}
    component_def = tracker_pb2.ComponentDef(
        path='Frontend', admin_ids=[111L], cc_ids=[222L], label_ids=[1, 2])
    actual = converters.ConvertComponentDef(
        component_def, self.users_by_id, labels_by_id)
    self.assertEqual('Frontend', actual.path)
    self.assertEqual(1, len(actual.admin_refs))
    self.assertEqual(111L, actual.admin_refs[0].user_id)
    self.assertEqual(1, len(actual.cc_refs))
    self.assertEqual(222L, actual.cc_refs[0].user_id)
    self.assertEqual(2, len(actual.label_refs))
    self.assertEqual('Security', actual.label_refs[0].label)
    self.assertEqual('Usability', actual.label_refs[1].label)

  def testConvertFieldDef_Simple(self):
    """We can convert a minimal field definition to protoc."""
    field_def = tracker_pb2.FieldDef(
        field_name='EstDays', field_type=tracker_pb2.FieldTypes.INT_TYPE)
    actual = converters.ConvertFieldDef(
        field_def, self.users_by_id, self.config)
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
        is_multivalued=True, docstring='doc', admin_ids=[111L],
        is_phase_field=True)
    actual = converters.ConvertFieldDef(
        field_def, self.users_by_id, self.config)
    self.assertEqual('DesignDocs', actual.field_ref.field_name)
    self.assertEqual(common_pb2.URL_TYPE, actual.field_ref.type)
    self.assertEqual('', actual.field_ref.approval_name)
    self.assertEqual('Enhancement', actual.applicable_type)
    self.assertEqual('doc', actual.docstring)
    self.assertEqual(1, len(actual.admin_refs))
    self.assertEqual(111L, actual.admin_refs[0].user_id)
    self.assertTrue(actual.is_required)
    self.assertTrue(actual.is_niche)
    self.assertTrue(actual.is_multivalued)
    self.assertTrue(actual.is_phase_field)

  def testConvertFieldDef_FieldOfAnApproval(self):
    """We can convert a field that is part of an approval."""
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3]
    field_def = tracker_pb2.FieldDef(
        field_name='Waiver', field_type=tracker_pb2.FieldTypes.URL_TYPE,
        approval_id=self.fd_3.field_id)
    actual = converters.ConvertFieldDef(
        field_def, self.users_by_id, self.config)
    self.assertEqual('Waiver', actual.field_ref.field_name)
    self.assertEqual('LegalApproval', actual.field_ref.approval_name)

  def testConvertApprovalDef(self):
    """We can convert an ApprovalDef to protoc."""
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3]
    approval_def = tracker_pb2.ApprovalDef(approval_id=3)
    actual = converters.ConvertApprovalDef(
        approval_def, self.users_by_id, self.config)
    self.assertEqual('LegalApproval', actual.field_ref.field_name)
    self.assertEqual(common_pb2.APPROVAL_TYPE, actual.field_ref.type)
    self.assertEqual(0, len(actual.approver_refs))
    self.assertEqual('', actual.survey)

    approval_def = tracker_pb2.ApprovalDef(
        approval_id=3, approver_ids=[111L], survey='What?')
    actual = converters.ConvertApprovalDef(
        approval_def, self.users_by_id, self.config)
    self.assertEqual('LegalApproval', actual.field_ref.field_name)
    self.assertEqual(common_pb2.APPROVAL_TYPE, actual.field_ref.type)
    self.assertEqual(1, len(actual.approver_refs))
    self.assertEqual(111L, actual.approver_refs[0].user_id)
    self.assertEqual('What?', actual.survey)

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

  def testConvertConfig_Normal(self):
    """We can convert a config with fields and components to protoc."""
    labels_by_id = {1: 'Security', 2: 'Usability'}
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3]
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=1, path='UI', label_ids=[2])]
    self.config.approval_defs.append(tracker_pb2.ApprovalDef(
        approval_id=3, approver_ids=[111L], survey='What?'))
    self.config.restrict_to_known = True
    actual = converters.ConvertConfig(
        self.project, self.config, self.users_by_id, labels_by_id)
    self.assertEqual(1, len(actual.component_defs))
    self.assertEqual(3, len(actual.field_defs))
    self.assertEqual(1, len(actual.approval_defs))
    self.assertEqual('proj', actual.project_name)
    self.assertEqual(True, actual.restrict_to_known)

  def testConvertHotlist(self):
    """We can convert a hotlist to protoc."""
    hotlist = testing_helpers.Blank(
        owner_ids=[111L],
        name='Fake Hotlist',
        summary='A fake hotlist.',
        description='Detailed description of the fake hotlist.')
    actual = converters.ConvertHotlist(hotlist, self.users_by_id)
    self.assertEqual(111L, actual.owner_ref.user_id)
    self.assertEqual('one@example.com', actual.owner_ref.display_name)
    self.assertEqual('Fake Hotlist', actual.name)
    self.assertEqual('A fake hotlist.', actual.summary)
    self.assertEqual(
        'Detailed description of the fake hotlist.', actual.description)

  def testConvertFieldOptions(self):
    """We can convert a field def an a list of users to FieldOptions protoc."""
    self.config.field_defs = [self.fd_1, self.fd_2, self.fd_3]
    field_def = tracker_pb2.FieldDef(
        field_name='Waiver', field_type=tracker_pb2.FieldTypes.URL_TYPE,
        approval_id=self.fd_3.field_id)
    actual = converters.ConvertFieldOptions(
        field_def, [111L, 333L], self.users_by_id, self.config)
    self.assertEqual('Waiver', actual.field_ref.field_name)
    self.assertEqual('LegalApproval', actual.field_ref.approval_name)
    self.assertEqual(common_pb2.URL_TYPE, actual.field_ref.type)
    self.assertEqual([111L, 333L],
                     [user_ref.user_id for user_ref in actual.user_refs])
    self.assertEqual(['one@example.com', 'banned@example.com'],
                     [user_ref.display_name for user_ref in actual.user_refs])
