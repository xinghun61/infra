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


class TestData(object):
  # Constants or such objects that are intended to be read-only.
  cnxn = 'fake cnxn'
  test_issue_local_id = 100
  component_id = 123
  trooper_queue = 'my-trooper-bug-queue'

  project_name = 'proj'
  project_addr = '%s+ALERT+%s@monorail.example.com' % (
      project_name, trooper_queue)
  project_id = 987

  from_addr = 'user@monorail.example.com'
  user_id = 111

  msg_body = 'this is the body'
  msg_subject = 'this is the subject'
  msg = testing_helpers.MakeMessage(
      testing_helpers.ALERT_EMAIL_HEADER_LINES, msg_body)

  incident_id = msg.get('X-Incident-Id')
  incident_label = alert2issue._GetIncidentLabel(incident_id)

  # All the tests in this class use the following alert properties, and
  # the generator functions/logic should be tested in a separate class.
  alert_props = {
      'owner_id': None,
      'cc_ids': [],
      'status': 'Available',
      'incident_label': incident_label,
      'priority': 'Pri-0',
      'trooper_queue': trooper_queue,
      'field_values': [],
      'labels': ['Restrict-View-Google', 'Pri-0', incident_label,
                 trooper_queue],
      'component_ids': [component_id],
  }


class ProcessEmailNotificationTests(unittest.TestCase, TestData):
  """Implements unit tests for alert2issue.ProcessEmailNotification."""

  def setUp(self):
    # services
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService())

    # project
    self.project = self.services.project.TestAddProject(
        self.project_name, project_id=self.project_id,
        process_inbound_email=True, contrib_ids=[self.user_id])

    # sender
    self.auth = authdata.AuthData(user_id=self.user_id, email=self.from_addr)

    # issue
    self.issue = tracker_pb2.Issue(
        project_id=self.project_id,
        local_id=self.test_issue_local_id,
        summary=self.msg_subject,
        reporter_id=self.user_id,
        component_ids=[self.component_id],
        status=self.alert_props['status'],
        labels=self.alert_props['labels'],
    )
    self.services.issue.TestAddIssue(self.issue)

    # Patch send_notifications functions.
    self.notification_patchers = [
        patch('features.send_notifications.%s' % func, spec=True)
        for func in [
            'PrepareAndSendIssueBlockingNotification',
            'PrepareAndSendIssueChangeNotification',
        ]
    ]
    self.blocking_notification = self.notification_patchers[0].start()
    self.blocking_notification = self.notification_patchers[1].start()

    self.mox = mox.Mox()

  def tearDown(self):
    self.notification_patchers[0].stop()
    self.notification_patchers[1].stop()

    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testGoogleAddrsAreWhitelistedSender(self):
    self.assertTrue(alert2issue.IsWhitelisted('test@google.com'))
    self.assertFalse(alert2issue.IsWhitelisted('test@notgoogle.com'))

  def testSkipNotification_IfFromNonWhitelistedSender(self):
    self.mox.StubOutWithMock(alert2issue, 'IsWhitelisted')
    alert2issue.IsWhitelisted(self.from_addr).AndReturn(False)

    # None of them should be called, if the sender has not been whitelisted.
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssueComment')
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssue')
    self.mox.ReplayAll()

    alert2issue.ProcessEmailNotification(
        self.services, self.cnxn, self.project, self.project_addr,
        self.from_addr, self.auth, self.msg_subject, self.msg_body,
        self.incident_label)
    self.mox.VerifyAll()

  def testProcessNotification_IfFromWhitelistedSender(self):
    self.mox.StubOutWithMock(alert2issue, 'IsWhitelisted')
    alert2issue.IsWhitelisted(self.from_addr).AndReturn(True)

    self.mox.StubOutWithMock(tracker_helpers, 'LookupComponentIDs')
    tracker_helpers.LookupComponentIDs(
        ['Infra'],
        mox.IgnoreArg()).AndReturn([1])
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssueComment')
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssue')
    self.mox.ReplayAll()

    # Either of the methods should be called, if the sender is whitelisted.
    with self.assertRaises(mox.UnexpectedMethodCallError):
      alert2issue.ProcessEmailNotification(
          self.services, self.cnxn, self.project, self.project_addr,
          self.from_addr, self.auth, self.msg_subject, self.msg_body,
          self.incident_label, self.trooper_queue)

    self.mox.VerifyAll()

  def testIssueCreated_ForNewIncident(self):
    """Tests if a new issue is created for a new incident."""
    self.mox.StubOutWithMock(alert2issue, 'IsWhitelisted')
    alert2issue.IsWhitelisted(self.from_addr).AndReturn(True)

    # FindAlertIssue() returns None for a new incident.
    self.mox.StubOutWithMock(alert2issue, 'FindAlertIssue')
    alert2issue.FindAlertIssue(
        self.services, self.cnxn, self.project.project_id,
        self.incident_label).AndReturn(None)

    # Mock GetAlertProperties() to create the issue with the expected
    # properties.
    self.mox.StubOutWithMock(alert2issue, 'GetAlertProperties')
    alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body).AndReturn(self.alert_props)

    self.mox.ReplayAll()
    alert2issue.ProcessEmailNotification(
        self.services, self.cnxn, self.project, self.project_addr,
        self.from_addr, self.auth, self.msg_subject, self.msg_body,
        self.incident_id, self.trooper_queue)

    # the local ID of the newly created issue should be +1 from the highest ID
    # in the existing issues.
    comments = self._verifyIssue(self.test_issue_local_id + 1, self.alert_props)
    self.assertEqual(comments[0].content,
                     'Filed by %s on behalf of %s\n\n%s' % (
                         self.from_addr, self.from_addr, self.msg_body))

    self.mox.VerifyAll()

  def testProcessEmailNotification_ExistingIssue(self):
    """When an alert for an ongoing incident comes in, add a comment."""
    self.mox.StubOutWithMock(alert2issue, 'IsWhitelisted')
    alert2issue.IsWhitelisted(self.from_addr).AndReturn(True)

    # FindAlertIssue() returns None for a new incident.
    self.mox.StubOutWithMock(alert2issue, 'FindAlertIssue')
    alert2issue.FindAlertIssue(
        self.services, self.cnxn, self.project.project_id,
        self.incident_label).AndReturn(self.issue)

    # Mock GetAlertProperties() to create the issue with the expected
    # properties.
    self.mox.StubOutWithMock(alert2issue, 'GetAlertProperties')
    alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body).AndReturn(self.alert_props)

    self.mox.ReplayAll()

    # Before processing the notification, ensures that there is only 1 comment
    # in the test issue.
    comments = self._verifyIssue(self.test_issue_local_id, self.alert_props)
    self.assertEqual(len(comments), 1)

    # Process
    alert2issue.ProcessEmailNotification(
        self.services, self.cnxn, self.project, self.project_addr,
        self.from_addr, self.auth, self.msg_subject, self.msg_body,
        self.incident_id, self.trooper_queue)

    # Now, it should have a new comment added.
    comments = self._verifyIssue(self.test_issue_local_id, self.alert_props)
    self.assertEqual(len(comments), 2)
    self.assertEqual(comments[1].content,
                     'Filed by %s on behalf of %s\n\n%s' % (
                         self.from_addr, self.from_addr, self.msg_body))

    self.mox.VerifyAll()

  def _verifyIssue(self, local_issue_id, alert_props):
    actual_issue = self.services.issue.GetIssueByLocalID(
        self.cnxn, self.project.project_id, local_issue_id)
    actual_comments = self.services.issue.GetCommentsForIssue(
        self.cnxn, actual_issue.issue_id)

    self.assertEqual(actual_issue.summary, self.msg_subject)
    self.assertEqual(actual_issue.status, alert_props['status'])
    self.assertEqual(actual_issue.reporter_id, self.user_id)
    self.assertEqual(actual_issue.component_ids, [self.component_id])
    self.assertEqual(actual_issue.owner_id, alert_props['owner_id'])
    self.assertEqual(sorted(actual_issue.labels), sorted(alert_props['labels']))
    return actual_comments


class GetAlertPropertiesTests(unittest.TestCase, TestData):
  """Implements unit tests for alert2issue.GetAlertProperties."""

  def setUp(self):
    # services
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService())

    # project
    self.project = self.services.project.TestAddProject(
        self.project_name, project_id=self.project_id,
        process_inbound_email=True, contrib_ids=[self.user_id])

    self.mox = mox.Mox()

  def testComponentWithCodesearch(self):
    """Checks if the component is Infra>Codesearch, if msg contains codesearch.
    """
    component_id = self.component_id + 1
    self.mox.StubOutWithMock(tracker_helpers, 'LookupComponentIDs')
    tracker_helpers.LookupComponentIDs(
        ['Infra>Codesearch'],
        mox.IgnoreArg()).AndReturn([component_id])

    self.mox.ReplayAll()
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body + 'codesearch')
    self.assertEqual(props['component_ids'], [component_id])
    self.mox.VerifyAll()

  def testDefaultComponent(self):
    """Checks if the default component is Infra."""
    component_id = self.component_id
    self.mox.StubOutWithMock(tracker_helpers, 'LookupComponentIDs')
    tracker_helpers.LookupComponentIDs(
        ['Infra'],
        mox.IgnoreArg()).AndReturn([component_id])

    self.mox.ReplayAll()
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body)
    self.assertEqual(props['component_ids'], [component_id])
    self.mox.VerifyAll()

  def testLabelsWithNecessaryValues(self):
    """Checks if the labels contain all the necessary values."""
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body)

    self.assertTrue('Restrict-View-Google' in props['labels'])
    self.assertTrue(self.incident_label in props['labels'])
    self.assertTrue(self.trooper_queue in props['labels'])
    self.assertTrue(props['priority'] in props['labels'])
