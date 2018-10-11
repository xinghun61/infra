# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the flt launch issues conversion task."""

import unittest
import settings

from framework import exceptions
from framework import permissions
from services import service_manager
from tracker import fltconversion
from testing import fake
from testing import testing_helpers
from proto import tracker_pb2

class FLTConvertTask(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services()
    self.mr = testing_helpers.MakeMonorailRequest()
    self.task = fltconversion.FLTConvertTask(
        'req', 'res', services=self.services)

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
