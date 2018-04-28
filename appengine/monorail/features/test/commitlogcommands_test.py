# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.features.commitlogcommands."""

import unittest

import mox

from features import commitlogcommands
from features import send_notifications
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class InboundEmailTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        issue=fake.IssueService(),
        project=fake.ProjectService(),
        config=fake.ConfigService())

    self.project = self.services.project.TestAddProject(
        'proj', project_id=987, process_inbound_email=True)
    self.issue = tracker_pb2.Issue()
    self.issue.project_id = 987
    self.issue.summary = 'summary'
    self.issue.status = 'Assigned'
    self.services.issue.TestAddIssue(self.issue)

    self.uia = commitlogcommands.UpdateIssueAction(self.issue.local_id)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testParse_NoCommandLines(self):
    commands_found = self.uia.Parse(self.cnxn, self.project.project_name, 101,
                   ['line 1'], self.services,
                   hostport=80, strip_quoted_lines=True)
    self.assertEquals(False, commands_found)
    self.assertEquals('line 1', self.uia.description)
    self.assertEquals('line 1', self.uia.inbound_message)

  def testParse_StripQuotedLines(self):
    commands_found = self.uia.Parse(self.cnxn, self.project.project_name, 101,
                   ['summary:something', '> line 1', 'line 2'], self.services,
                   hostport=80, strip_quoted_lines=True)
    self.assertEquals(True, commands_found)
    self.assertEquals('line 2', self.uia.description)
    self.assertEquals('summary:something\n> line 1\nline 2',
                      self.uia.inbound_message)

  def testParse_NoStripQuotedLines(self):
    commands_found = self.uia.Parse(self.cnxn, self.project.project_name, 101,
                   ['summary:something', '> line 1', 'line 2'], self.services,
                   hostport=80)
    self.assertEquals(True, commands_found)
    self.assertEquals('> line 1\nline 2', self.uia.description)
    self.assertIsNone(self.uia.inbound_message)

  def setupAndCallRun(self, allow_edit):
    comments = ['comment 1', 'comment 2', 'comment 3']

    self.mox.StubOutWithMock(
        send_notifications, 'PrepareAndSendIssueChangeNotification')
    send_notifications.PrepareAndSendIssueChangeNotification(
        self.issue.issue_id, 80, 101,
        old_owner_id=self.issue.owner_id, comment_id=1)
    self.mox.ReplayAll()

    self.uia.Parse(self.cnxn, self.project.project_name, 101,
                   ['summary:something', 'status:New', '> line 1', '> line 2'],
                   self.services, hostport=80)
    self.uia.Run(self.cnxn, self.services, allow_edit=allow_edit)
    self.mox.VerifyAll()

  def testRun_AllowEdit(self):
    self.setupAndCallRun(allow_edit=True)

    self.assertEquals('> line 1\n> line 2', self.uia.description)
    # Assert that ammendments were made to the issue.
    self.assertEquals('something', self.issue.summary)
    self.assertEquals('New', self.issue.status)


  def testRun_NoAllowEdit(self):
    self.setupAndCallRun(allow_edit=False)

    self.assertEquals('> line 1\n> line 2', self.uia.description)
    # Assert that ammendments were *not* made to the issue.
    self.assertEquals('summary', self.issue.summary)
    self.assertEquals('Assigned', self.issue.status)
