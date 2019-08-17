# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.feature.alert2issue."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import email
import unittest
from mock import patch
import mox
from parameterized import parameterized

from features import alert2issue
from framework import authdata
from framework import emailfmt
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import tracker_helpers

AlertEmailHeader = emailfmt.AlertEmailHeader


class TestData(object):
  """Contains constants or such objects that are intended to be read-only."""
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

  incident_id = msg.get(AlertEmailHeader.INCIDENT_ID)
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
        self.incident_label, self.msg, self.trooper_queue)
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
          self.incident_label, self.msg, self.trooper_queue)

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
        self.trooper_queue, self.msg_body, self.msg).AndReturn(self.alert_props)

    self.mox.ReplayAll()
    alert2issue.ProcessEmailNotification(
        self.services, self.cnxn, self.project, self.project_addr,
        self.from_addr, self.auth, self.msg_subject, self.msg_body,
        self.incident_id, self.msg, self.trooper_queue)

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
        self.trooper_queue, self.msg_body, self.msg).AndReturn(self.alert_props)

    self.mox.ReplayAll()

    # Before processing the notification, ensures that there is only 1 comment
    # in the test issue.
    comments = self._verifyIssue(self.test_issue_local_id, self.alert_props)
    self.assertEqual(len(comments), 1)

    # Process
    alert2issue.ProcessEmailNotification(
        self.services, self.cnxn, self.project, self.project_addr,
        self.from_addr, self.auth, self.msg_subject, self.msg_body,
        self.incident_id, self.msg, self.trooper_queue)

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

  def assertCaseInsensitiveEqual(self, lhs, rhs):
    self.assertEqual(lhs if lhs is None else lhs.lower(),
                     rhs if lhs is None else rhs.lower())

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

    proj_config = fake.MakeTestConfig(
        self.project_id,
        [
            # test labels for Pri field
            'Pri-0', 'Pri-1', 'Pri-2', 'Pri-3',
            # test labels for OS field
            'OS-Android', 'OS-Windows',
            # test labels for Type field
            'Type-Bug', 'Type-Bug-Regression', 'Type-Bug-Security', 'Type-Task',
        ],
        ['Assigned', 'Available', 'Unconfirmed']
    )
    self.services.config.StoreConfig(self.cnxn, proj_config)

    # create a test email message, which tests can alternate the header values
    # to verify the behaviour of a given parser function.
    self.test_msg = email.Message.Message()
    for key, value in self.msg.items():
      self.test_msg[key] = value

    self.mox = mox.Mox()

  @parameterized.expand([
      ('',),
      ('Infra,Project-Foo',),
      ('Infra>Codesearch',),
      ('Codesearch',),
      ('Infra>Codesearch,Infra',),
  ])
  def testComponentWithCodesearch(self, header_value):
    """Checks if the component is Infra>Codesearch, if the body with codesearch.
    """
    self.test_msg.replace_header(AlertEmailHeader.COMPONENT, header_value)
    msg_body = self.msg_body + 'codesearch'
    self.mox.StubOutWithMock(tracker_helpers, 'LookupComponentIDs')
    tracker_helpers.LookupComponentIDs(
        ['Infra>Codesearch'],
        mox.IgnoreArg()).AndReturn([self.component_id])

    self.mox.ReplayAll()
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, msg_body, self.test_msg)
    self.assertEqual(props['component_ids'], [self.component_id])
    self.mox.VerifyAll()

  @parameterized.expand([
      (None,),
      ('',),
  ])
  def testDefaultComponent(self, header_value):
    """Checks if the default component is Infra."""
    self.test_msg.replace_header(AlertEmailHeader.COMPONENT, header_value)
    self.mox.StubOutWithMock(tracker_helpers, 'LookupComponentIDs')
    tracker_helpers.LookupComponentIDs(
        ['Infra'],
        mox.IgnoreArg()).AndReturn([self.component_id])

    self.mox.ReplayAll()
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.assertEqual(props['component_ids'], [self.component_id])
    self.mox.VerifyAll()

  @parameterized.expand([
      # an existing single component with componentID 1
      ({'Infra': 1}, [1]),
      # 3 of existing components
      ({'Infra': 1, 'Foo': 2, 'Bar': 3}, [1, 2, 3]),
      # a non-existing component
      ({'Infra': None}, []),
      # 3 of non-existing components
      ({'Infra': None, 'Foo': None, 'Bar': None}, []),
      # a mix of existing and non-existing components
      ({'Infra': 1, 'Foo': None, 'Bar': 2}, [1, 2]),
  ])
  def testGetComponentIDs(self, components, expected_component_ids):
    """Tests _GetComponentIDs."""
    self.test_msg.replace_header(
        AlertEmailHeader.COMPONENT, ','.join(sorted(components.keys())))

    self.mox.StubOutWithMock(tracker_helpers, 'LookupComponentIDs')
    tracker_helpers.LookupComponentIDs(
        sorted(components.keys()),
        mox.IgnoreArg()).AndReturn(
            [components[key] for key in sorted(components.keys())
             if components[key]]
        )

    self.mox.ReplayAll()
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.assertEqual(sorted(props['component_ids']),
                     sorted(expected_component_ids))
    self.mox.VerifyAll()


  def testLabelsWithNecessaryValues(self):
    """Checks if the labels contain all the necessary values."""
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)

    # This test assumes that the test message contains non-empty values for
    # all the headers.
    self.assertTrue(props['incident_label'])
    self.assertTrue(props['priority'])
    self.assertTrue(props['issue_type'])
    self.assertTrue(props['oses'])

    # Here are a list of the labels that props['labels'] should contain
    self.assertIn('Restrict-View-Google', props['labels'])
    self.assertIn(self.trooper_queue, props['labels'])
    self.assertIn(props['incident_label'], props['labels'])
    self.assertIn(props['priority'], props['labels'])
    self.assertIn(props['issue_type'], props['labels'])
    for os in props['oses']:
      self.assertIn(os, props['labels'])

  @parameterized.expand([
      (None, None),
      ('', None),
  ])
  def testDefaultOwnerID(self, header_value, expected_owner_id):
    """Checks if _GetOwnerID returns None in default."""
    self.test_msg.replace_header(AlertEmailHeader.OWNER, header_value)
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.assertEqual(props['owner_id'], expected_owner_id)

  @parameterized.expand([
      # an existing user with userID 1.
      ('owner@example.org', 1),
      # a non-existing user.
      ('owner@example.org', None),
  ])
  def testGetOwnerID(self, owner, expected_owner_id):
    """Tests _GetOwnerID returns the ID of the owner."""
    self.test_msg.replace_header(AlertEmailHeader.CC, '')
    self.test_msg.replace_header(AlertEmailHeader.OWNER, owner)

    self.mox.StubOutWithMock(self.services.user, 'LookupExistingUserIDs')
    self.services.user.LookupExistingUserIDs(self.cnxn, [owner]).AndReturn(
        {owner: expected_owner_id})

    self.mox.ReplayAll()
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.mox.VerifyAll()
    self.assertEqual(props['owner_id'], expected_owner_id)

  @parameterized.expand([
      (None, []),
      ('', []),
  ])
  def testDefaultCCIDs(self, header_value, expected_cc_ids):
    """Checks if _GetCCIDs returns an empty list in default."""
    self.test_msg.replace_header(AlertEmailHeader.OWNER, header_value)
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.assertEqual(props['cc_ids'], expected_cc_ids)

  @parameterized.expand([
      # with one existing user cc-ed.
      ({'user1@example.org': 1}, [1]),
      # with two of existing users.
      ({'user1@example.org': 1, 'user2@example.org': 2}, [1, 2]),
      # with one non-existing user.
      ({'user1@example.org': None}, []),
      # with two of non-existing users.
      ({'user1@example.org': None, 'user2@example.org': None}, []),
      # with a mix of existing and non-existing users.
      ({'user1@example.org': 1, 'user2@example.org': None}, [1]),
  ])
  def testGetCCIDs(self, ccers, expected_cc_ids):
    """Tests _GetCCIDs returns the IDs of the email addresses to be cc-ed."""
    self.test_msg.replace_header(
        AlertEmailHeader.CC, ','.join(sorted(ccers.keys())))
    self.test_msg.replace_header(AlertEmailHeader.OWNER, '')

    self.mox.StubOutWithMock(self.services.user, 'LookupExistingUserIDs')
    self.services.user.LookupExistingUserIDs(
        self.cnxn, sorted(ccers.keys())).AndReturn(ccers)

    self.mox.ReplayAll()
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.mox.VerifyAll()
    self.assertEqual(sorted(props['cc_ids']), sorted(expected_cc_ids))

  @parameterized.expand([
      # None and '' should result in the default priority returned.
      (None, 'Pri-2'),
      ('', 'Pri-2'),

      # Tests for valid priority values
      ('0', 'Pri-0'),
      ('1', 'Pri-1'),
      ('2', 'Pri-2'),
      ('3', 'Pri-3'),

      # Tests for invalid priority values
      ('test', 'Pri-2'),
      ('foo', 'Pri-2'),
      ('critical', 'Pri-2'),
      ('4', 'Pri-2'),
      ('3x', 'Pri-2'),
      ('00', 'Pri-2'),
      ('01', 'Pri-2'),
  ])
  def testGetPriority(self, header_value, expected_priority):
    """Tests _GetPriority."""
    self.test_msg.replace_header(AlertEmailHeader.PRIORITY, header_value)
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.assertCaseInsensitiveEqual(props['priority'], expected_priority)

  @parameterized.expand([
      (None, 'Available'),
      ('', 'Available'),
  ])
  def testDefaultStatus(self, header_value, expected_status):
    """Checks if _GetStatus return Available in default."""
    self.test_msg.replace_header(AlertEmailHeader.STATUS, header_value)
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.assertCaseInsensitiveEqual(props['status'], expected_status)

  @parameterized.expand([
      ('random_status', True, 'random_status'),
      # If the status is not one of the open statuses, the default status
      # should be returned instead.
      ('random_status', False, 'Available'),
  ])
  def testGetStatusWithoutOwner(self, status, means_open, expected_status):
    """Tests GetStatus without an owner."""
    self.test_msg.replace_header(AlertEmailHeader.STATUS, status)
    self.mox.StubOutWithMock(tracker_helpers, 'MeansOpenInProject')
    tracker_helpers.MeansOpenInProject(status, mox.IgnoreArg()).AndReturn(
        means_open)

    self.mox.ReplayAll()
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.assertCaseInsensitiveEqual(props['status'], expected_status)
    self.mox.VerifyAll()

  @parameterized.expand([
      ('random_status', 'Assigned'),
      ('Available', 'Assigned'),
      ('Unconfirmed', 'Assigned'),
      ('Fixed', 'Assigned'),
  ])
  def testGetStatusWithOwner(self, status, expected_status):
    """Tests GetStatus with an owner."""
    owner = 'owner@example.org'
    self.test_msg.replace_header(AlertEmailHeader.OWNER, owner)
    self.test_msg.replace_header(AlertEmailHeader.CC, '')
    self.test_msg.replace_header(AlertEmailHeader.STATUS, status)

    self.mox.StubOutWithMock(self.services.user, 'LookupExistingUserIDs')
    self.services.user.LookupExistingUserIDs(self.cnxn, [owner]).AndReturn(
        {owner: 1})

    self.mox.ReplayAll()
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.assertCaseInsensitiveEqual(props['status'], expected_status)
    self.mox.VerifyAll()

  @parameterized.expand([
      # None and '' should result in None returned.
      (None, None),
      ('', None),

      # whitelisted issue types
      ('Bug', 'Type-Bug'),
      ('Bug-Regression', 'Type-Bug-Regression'),
      ('Bug-Security', 'Type-Bug-Security'),
      ('Task', 'Type-Task'),

      # non-whitelisted issue types
      ('foo', None),
      ('bar', None),
      ('Bug,Bug-Regression', None),
      ('Bug,', None),
      (',Task', None),
  ])
  def testGetIssueType(self, header_value, expected_issue_type):
    """Tests _GetIssueType."""
    self.test_msg.replace_header(AlertEmailHeader.TYPE, header_value)
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.assertCaseInsensitiveEqual(props['issue_type'], expected_issue_type)

  @parameterized.expand([
      # None and '' should result in an empty list returned.
      (None, []),
      ('', []),

      # a single, whitelisted os
      ('Android', ['OS-Android']),
      # a single, non-whitelisted OS
      ('Bendroid', []),
      # multiple, whitelisted oses
      ('Android,Windows', ['OS-Android', 'OS-Windows']),
      # multiple, non-whitelisted oses
      ('Bendroid,Findows', []),
      # a mix of whitelisted and non-whitelisted oses
      ('Android,Findows,Windows,Bendroid', ['OS-Android', 'OS-Windows']),
      # a mix of whitelisted and non-whitelisted oses with trailing commas.
      ('Android,Findows,Windows,Bendroid,,', ['OS-Android', 'OS-Windows']),
      # a mix of whitelisted and non-whitelisted oses with commas at the
      # beginning.
      (',,Android,Findows,Windows,Bendroid,,', ['OS-Android', 'OS-Windows']),
  ])
  def testGetOS(self, header_value, expected_oses):
    """Tests _GetOSes."""
    self.test_msg.replace_header(AlertEmailHeader.OS, header_value)
    props = alert2issue.GetAlertProperties(
        self.services, self.cnxn, self.project_id, self.incident_id,
        self.trooper_queue, self.msg_body, self.test_msg)
    self.assertEqual(sorted(os if os is None else os.lower()
                            for os in props['oses']),
                     sorted(os if os is None else os.lower()
                            for os in expected_oses))
