# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the flt launch issues conversion task."""

import unittest
import settings
import mock

from framework import exceptions
from framework import permissions
from services import service_manager
from tracker import fltconversion
from tracker import tracker_bizobj
from testing import fake
from testing import testing_helpers
from proto import tracker_pb2

class FLTConvertTask(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        issue=fake.IssueService(),
        user=fake.UserService())
    self.mr = testing_helpers.MakeMonorailRequest()
    self.task = fltconversion.FLTConvertTask(
        'req', 'res', services=self.services)
    self.task.mr = self.mr
    self.issue = fake.MakeTestIssue(
        789, 1, 'summary', 'New', 111L, issue_id=78901)
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

  def testAssertBasePermission(self):
    self.mr.auth.user_pb.is_site_admin = True
    settings.app_id = 'monorail-staging'
    self.task.AssertBasePermission(self.mr)

    self.mr.auth.user_pb.is_site_admin = False
    self.assertRaises(permissions.PermissionException,
                      self.task.AssertBasePermission, self.mr)

    self.mr.auth.user_pb.is_site_admin = True
    settings.app_id = 'monorail-prod'
    self.assertRaises(exceptions.ActionNotSupported,
                      self.task.AssertBasePermission, self.mr)

  def testExecuteIssueChanges(self):
    self.task.services.issue._UpdateIssuesApprovals = mock.Mock()
    self.task.services.issue.DeltaUpdateIssue = mock.Mock(
        return_value=([], None))
    self.task.services.issue.InsertComment = mock.Mock()
    self.config.approval_defs = [
        tracker_pb2.ApprovalDef(approval_id=1, survey=''), # test empty survey
        tracker_pb2.ApprovalDef(approval_id=2), # test missing survey
        tracker_pb2.ApprovalDef(survey='Missing approval_id should not error.'),
        tracker_pb2.ApprovalDef(approval_id=3, survey='Q1\nQ2\n\nQ3'),
        tracker_pb2.ApprovalDef(approval_id=4, survey='Q1\nQ2\n\nQ3 two'),
        tracker_pb2.ApprovalDef()]

    new_avs = [tracker_pb2.ApprovalValue(
        approval_id=1, status=tracker_pb2.ApprovalStatus.APPROVED,
        approver_ids=[111L, 222L]),
               tracker_pb2.ApprovalValue(approval_id=4),
               tracker_pb2.ApprovalValue(approval_id=2),
               tracker_pb2.ApprovalValue(approval_id=3)]

    phases = [tracker_pb2.Phase(phase_id=1, name='Phase1', rank=1)]
    new_fvs = [tracker_bizobj.MakeFieldValue(
        11, 70, None, None, None, None, False, phase_id=1),
               tracker_bizobj.MakeFieldValue(
                   12, None, 'strfield', None, None, None, False)]
    _amendments = self.task.ExecuteIssueChanges(
        self.config, self.issue, new_avs, phases, new_fvs)

    self.issue.approval_values = new_avs
    self.issue.phases = phases
    delta = tracker_pb2.IssueDelta(
        labels_add=['Type-FLT-Launch', 'FLT-Conversion'],
        labels_remove=['Type-Launch'], field_vals_add=new_fvs)
    cmt_1 = tracker_pb2.IssueComment(
        issue_id=78901, project_id=789, user_id=self.mr.auth.user_id,
        content='', is_description=True, approval_id=1)
    cmt_2 = tracker_pb2.IssueComment(
        issue_id=78901, project_id=789, user_id=self.mr.auth.user_id,
        content='', is_description=True, approval_id=2)
    cmt_3 = tracker_pb2.IssueComment(
        issue_id=78901, project_id=789, user_id=self.mr.auth.user_id,
        content='<b>Q1</b>\n<b>Q2</b>\n<b></b>\n<b>Q3</b>',
        is_description=True, approval_id=3)
    cmt_4 = tracker_pb2.IssueComment(
        issue_id=78901, project_id=789, user_id=self.mr.auth.user_id,
        content='<b>Q1</b>\n<b>Q2</b>\n<b></b>\n<b>Q3 two</b>',
        is_description=True, approval_id=4)


    comment_calls = [mock.call(self.mr.cnxn, cmt_1),
                     mock.call(self.mr.cnxn, cmt_4),
                     mock.call(self.mr.cnxn, cmt_2),
                     mock.call(self.mr.cnxn, cmt_3)]
    self.task.services.issue.InsertComment.assert_has_calls(comment_calls)

    self.task.services.issue._UpdateIssuesApprovals.assert_called_once_with(
        self.mr.cnxn, self.issue)
    self.task.services.issue.DeltaUpdateIssue.assert_called_once_with(
        self.mr.cnxn, self.task.services, self.mr.auth.user_id, 789,
        self.config, self.issue, delta,
        comment=fltconversion.CONVERSION_COMMENT)

  def testConvertPeopleLabels(self):
    self.task.services.user.LookupUserID = mock.Mock(side_effect=[1, 2, 3, 4])
    self.issue.labels = [
        'pm-u1', 'pm-u2', 'tl-u2', 'test-3', 'test-4']
    fvs = self.task.ConvertPeopleLabels(self.mr, self.issue, 11, 12, 13)
    expected = [
        tracker_bizobj.MakeFieldValue(11, None, None, 1, None, None, False),
        tracker_bizobj.MakeFieldValue(12, None, None, 2, None, None, False),
        tracker_bizobj.MakeFieldValue(13, None, None, 3, None, None, False),
        tracker_bizobj.MakeFieldValue(13, None, None, 4, None, None, False),
        ]
    self.assertEqual(fvs, expected)

  def testConvertPeopleLabels_NoUsers(self):
    def side_effect(_cnxn, _email):
      raise exceptions.NoSuchUserException()
    self.task.services.user.LookupUserID = mock.Mock(side_effect=side_effect)
    self.assertFalse(
        len(self.task.ConvertPeopleLabels(self.mr, self.issue, 11, 12, 13)))

  def testCreateUserFieldValue_Chromium(self):
    self.task.services.user.LookupUserID = mock.Mock(return_value=1)
    actual = self.task.CreateUserFieldValue(self.mr, 'ldap', 11)
    expected = tracker_bizobj.MakeFieldValue(
        11, None, None, 1, None, None, False)
    self.assertEqual(actual, expected)
    self.task.services.user.LookupUserID.assert_called_once_with(
        self.mr.cnxn, 'ldap@chromium.org')

  def testCreateUserFieldValue_Goog(self):
    def side_effect(_cnxn, email):
      if email.endswith('chromium.org'):
        raise exceptions.NoSuchUserException()
      else:
        return 2
    self.task.services.user.LookupUserID = mock.Mock(side_effect=side_effect)
    actual = self.task.CreateUserFieldValue(self.mr, 'ldap', 11)
    expected = tracker_bizobj.MakeFieldValue(
        11, None, None, 2, None, None, False)
    self.assertEqual(actual, expected)
    self.task.services.user.LookupUserID.assert_any_call(
        self.mr.cnxn, 'ldap@chromium.org')
    self.task.services.user.LookupUserID.assert_any_call(
        self.mr.cnxn, 'ldap@google.com')

  def testCreateUserFieldValue_NoUserFound(self):
    def side_effect(_cnxn, _email):
      raise exceptions.NoSuchUserException()
    self.task.services.user.LookupUserID = mock.Mock(side_effect=side_effect)
    self.assertIsNone(self.task.CreateUserFieldValue(self.mr, 'ldap', 11))

class ConvertLaunchLabels(unittest.TestCase):

  def setUp(self):
    self.project_fds = [
        tracker_pb2.FieldDef(
            field_id=1, project_id=789, field_name='String',
            field_type=tracker_pb2.FieldTypes.STR_TYPE),
        tracker_pb2.FieldDef(
            field_id=2, project_id=789, field_name='Chrome-UX',
            field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
        tracker_pb2.FieldDef(
            field_id=3, project_id=789, field_name='Chrome-Privacy',
            field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
        ]
    approvalUX = tracker_pb2.ApprovalValue(
        approval_id=2, status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    approvalPrivacy = tracker_pb2.ApprovalValue(approval_id=3)
    self.approvals = [approvalUX, approvalPrivacy]
    self.issue = fake.MakeTestIssue(001, 1, 'summary', 'New', 111L)

  def testConvertLaunchLabels_Normal(self):
    self.issue.labels = [
        'Launch-UX-NotReviewed', 'Launch-Privacy-Yes', 'Launch-NotRelevant']
    actual = fltconversion.ConvertLaunchLabels(
        self.issue, self.approvals, self.project_fds)
    expected = [
      tracker_pb2.ApprovalValue(
          approval_id=2, status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW),
      tracker_pb2.ApprovalValue(
          approval_id=3, status=tracker_pb2.ApprovalStatus.APPROVED)
    ]
    self.assertEqual(actual, expected)

  def testConvertLaunchLabels_ExtraAndMissingLabels(self):
    self.issue.labels = [
        'Blah-Launch-Privacy-Yes',  # Missing, this is not a valid Label
        'Launch-Security-Yes',  # Extra, no matching approval in given approvals
        'Launch-UI-Yes']  # Missing Launch-Privacy
    actual = fltconversion.ConvertLaunchLabels(
        self.issue, self.approvals, self.project_fds)
    expected = [
        tracker_pb2.ApprovalValue(
            approval_id=2, status=tracker_pb2.ApprovalStatus.APPROVED),
      tracker_pb2.ApprovalValue(
          approval_id=3, status=tracker_pb2.ApprovalStatus.NOT_SET)
        ]
    self.assertEqual(actual, expected)

class ExtractLabelLDAPs(unittest.TestCase):

  def testExtractLabelLDAPs_Normal(self):
    labels = [
        'tl-USER1',
        'pm-',
        'tL-User2',
        'test-user4',
        'PM-USER3',
        'pm',
        'test-user5',
        'test-']
    actual_pm, actual_tl, actual_tests = fltconversion.ExtractLabelLDAPs(labels)
    self.assertEqual(actual_pm, 'user3')
    self.assertEqual(actual_tl, 'user2')
    self.assertEqual(actual_tests, ['user4', 'user5'])

  def testExtractLabelLDAPs_NoLabels(self):
    actual_pm, actual_tl, actual_tests = fltconversion.ExtractLabelLDAPs([])
    self.assertIsNone(actual_pm)
    self.assertIsNone(actual_tl)
    self.assertFalse(len(actual_tests))
