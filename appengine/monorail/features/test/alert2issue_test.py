# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.feature.alert2issue."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
from mock import patch

import mox

from features import alert2issue
from features import commitlogcommands
from framework import authdata
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import tracker_helpers


class Alert2IssueTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=987, process_inbound_email=True,
        contrib_ids=[111])
    self.project_addr = 'proj@monorail.example.com'

    self.issue = tracker_pb2.Issue()
    self.issue.project_id = 987
    self.issue.local_id = 100
    self.services.issue.TestAddIssue(self.issue)

    self.msg = testing_helpers.MakeMessage(
        testing_helpers.ALERT_EMAIL_HEADER_LINES, 'awesome!')

    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testGoogleAddrsAreWhitelistedSender(self):
    self.assertTrue(alert2issue.IsWhitelisted('test@google.com'))
    self.assertFalse(alert2issue.IsWhitelisted('test@notgoogle.com'))

  def testProcessEmailNotification_NoIssueUpdatedIfNonWhitelistedSender(self):
    sender = 'user@malicious.com'
    self.assertFalse(alert2issue.IsWhitelisted(sender))
    self.mox.StubOutWithMock(alert2issue, 'IsWhitelisted')
    alert2issue.IsWhitelisted(sender).AndReturn(False)

    incident_label = alert2issue._GetIncidentLabel(
        self.msg.get('X-Incident-Id'))
    self.assertTrue(incident_label)

    # None of the below methods should be called if it is from a non-whitelisted
    # sender.
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssueComment')
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssue')
    self.mox.ReplayAll()
    auth = authdata.AuthData(user_id=111, email=sender)
    alert2issue.ProcessEmailNotification(
        self.services, self.cnxn, self.project, self.project_addr,
        sender, auth, 'issue title', 'issue body', incident_label)
    self.mox.VerifyAll()

  @patch('features.send_notifications.PrepareAndSendIssueBlockingNotification')
  @patch('features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testProcessEmailNotification_NewIssue(self, fake_pasicn, fake_pasibn):
    """When an alert for a new incident comes in, create a new issue."""
    incident_id = self.msg.get('X-Incident-Id')
    incident_label = alert2issue._GetIncidentLabel(incident_id)
    self.assertTrue(incident_label)

    self.mox.StubOutWithMock(tracker_helpers, 'LookupComponentIDs')
    tracker_helpers.LookupComponentIDs(
        ['Infra'],
        mox.IgnoreArg()).AndReturn([1])

    self.mox.StubOutWithMock(self.services.config, 'LookupLabelID')
    self.services.config.LookupLabelID(
        self.cnxn, self.project.project_id, incident_label).AndReturn(None)

    # Mock command parsing.
    mock_uia = commitlogcommands.UpdateIssueAction(101)
    self.mox.StubOutWithMock(commitlogcommands, 'UpdateIssueAction')
    commitlogcommands.UpdateIssueAction(101).AndReturn(mock_uia)

    self.mox.StubOutWithMock(mock_uia, 'Parse')
    mock_uia.Parse(
        self.cnxn, self.project.project_name, 111, ['issue body'],
        self.services, strip_quoted_lines=True)

    self.mox.ReplayAll()

    auth = authdata.AuthData(user_id=111, email='user@example.com')
    alert2issue.ProcessEmailNotification(
        self.services, self.cnxn, self.project, self.project_addr,
        'user@google.com', auth, 'issue title', 'issue body', incident_id)

    self.mox.VerifyAll()

    actual_issue = self.services.issue.GetIssueByLocalID(
        self.cnxn, self.project.project_id, 101)
    actual_comments = self.services.issue.GetCommentsForIssue(
        self.cnxn, actual_issue.issue_id)
    self.assertEqual('issue title', actual_issue.summary)
    self.assertEqual('Available', actual_issue.status)
    self.assertEqual(111, actual_issue.reporter_id)
    self.assertEqual([1], actual_issue.component_ids)
    self.assertEqual(None, actual_issue.owner_id)
    self.assertEqual(
        sorted(['Infra-Troopers-Alerts', 'Restrict-View-Google',
                'Pri-2', incident_label]),
        sorted(actual_issue.labels))
    self.assertEqual(
        'Filed by user@example.com on behalf of user@google.com\n\nissue body',
        actual_comments[0].content)
    self.assertEqual(1, len(fake_pasicn.mock_calls))
    self.assertEqual(1, len(fake_pasibn.mock_calls))

  @patch('features.send_notifications.PrepareAndSendIssueBlockingNotification')
  @patch('features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testProcessEmailNotification_NewIssue_Codesearch(
      self, fake_pasicn, fake_pasibn):
    """When an alert for a new incident comes in, create a new issue.

    If the body contains the string 'codesearch' then we should auto-assign to
    the Infra>Codesearch component."""
    incident_id = self.msg.get('X-Incident-Id')
    incident_label = alert2issue._GetIncidentLabel(incident_id)
    self.assertTrue(incident_label)

    self.mox.StubOutWithMock(tracker_helpers, 'LookupComponentIDs')
    tracker_helpers.LookupComponentIDs(
        ['Infra>Codesearch'],
        mox.IgnoreArg()).AndReturn([2])

    self.mox.StubOutWithMock(self.services.config, 'LookupLabelID')
    self.services.config.LookupLabelID(
        self.cnxn, self.project.project_id, incident_label,
    ).AndReturn(None)

    # Mock command parsing.
    mock_uia = commitlogcommands.UpdateIssueAction(101)
    self.mox.StubOutWithMock(commitlogcommands, 'UpdateIssueAction')
    commitlogcommands.UpdateIssueAction(101).AndReturn(mock_uia)

    self.mox.StubOutWithMock(mock_uia, 'Parse')
    mock_uia.Parse(
        self.cnxn, self.project.project_name, 111, ['issue body codesearch'],
        self.services, strip_quoted_lines=True)

    self.mox.ReplayAll()

    auth = authdata.AuthData(user_id=111, email='user@example.com')
    alert2issue.ProcessEmailNotification(
        self.services, self.cnxn, self.project, self.project_addr,
        'user@google.com', auth, 'issue title', 'issue body codesearch',
        incident_id)

    self.mox.VerifyAll()

    actual_issue = self.services.issue.GetIssueByLocalID(
        self.cnxn, self.project.project_id, 101)
    self.assertEqual([2], actual_issue.component_ids)
    self.assertEqual(1, len(fake_pasicn.mock_calls))
    self.assertEqual(1, len(fake_pasibn.mock_calls))

  def testProcessEmailNotification_ExistingIssue(self):
    """When an alert for an ongoing incident comes in, add a comment."""
    incident_id = self.msg.get('X-Incident-Id')
    incident_label = alert2issue._GetIncidentLabel(incident_id)
    self.assertTrue(incident_label)

    self.mox.StubOutWithMock(self.services.config, 'LookupLabelID')
    self.services.config.LookupLabelID(
        self.cnxn, self.project.project_id, incident_label,
    ).AndReturn(1234)

    self.mox.StubOutWithMock(self.services.issue, 'GetIIDsByLabelIDs')
    self.services.issue.GetIIDsByLabelIDs(
        self.cnxn, [1234], self.project.project_id, None
        ).AndReturn([1])

    self.mox.StubOutWithMock(self.services.issue, 'GetIssues')
    self.services.issue.GetIssues(
        self.cnxn, [1]).AndReturn([self.issue])

    self.mox.StubOutWithMock(self.services.issue, 'CreateIssueComment')
    self.services.issue.CreateIssueComment(
        self.cnxn, self.issue, 111,
        'Filed by user@example.com on behalf of user@google.com\n\nissue body'
        ).AndReturn(None)

    # Mock command parsing.
    mock_uia = commitlogcommands.UpdateIssueAction(self.issue.local_id)
    self.mox.StubOutWithMock(commitlogcommands, 'UpdateIssueAction')
    commitlogcommands.UpdateIssueAction(self.issue.local_id).AndReturn(mock_uia)

    self.mox.StubOutWithMock(mock_uia, 'Parse')
    mock_uia.Parse(
        self.cnxn, self.project.project_name, 111, ['issue body'],
        self.services, strip_quoted_lines=True)

    self.mox.ReplayAll()

    auth = authdata.AuthData(user_id=111, email='user@example.com')
    alert2issue.ProcessEmailNotification(
        self.services, self.cnxn, self.project, self.project_addr,
        'user@google.com', auth, 'issue title', 'issue body', incident_id)

    self.mox.VerifyAll()
