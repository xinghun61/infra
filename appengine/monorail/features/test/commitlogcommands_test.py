# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.features.commitlogcommands."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest

from features import commitlogcommands
from features import send_notifications
from framework import monorailcontext
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class InboundEmailTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        config=fake.ConfigService())

    self.member = self.services.user.TestAddUser('member@example.com', 111)
    self.outsider = self.services.user.TestAddUser('outsider@example.com', 222)
    self.project = self.services.project.TestAddProject(
        'proj', project_id=987, process_inbound_email=True,
        committer_ids=[self.member.user_id])
    self.issue = tracker_pb2.Issue()
    self.issue.issue_id = 98701
    self.issue.project_id = 987
    self.issue.local_id = 1
    self.issue.owner_id = 0
    self.issue.summary = 'summary'
    self.issue.status = 'Assigned'
    self.services.issue.TestAddIssue(self.issue)

    self.uia = commitlogcommands.UpdateIssueAction(self.issue.local_id)

  def testParse_NoCommandLines(self):
    commands_found = self.uia.Parse(self.cnxn, self.project.project_name, 111,
                   ['line 1'], self.services,
                   hostport='testing-app.appspot.com', strip_quoted_lines=True)
    self.assertEquals(False, commands_found)
    self.assertEquals('line 1', self.uia.description)
    self.assertEquals('line 1', self.uia.inbound_message)

  def testParse_StripQuotedLines(self):
    commands_found = self.uia.Parse(self.cnxn, self.project.project_name, 111,
                   ['summary:something', '> line 1', 'line 2'], self.services,
                   hostport='testing-app.appspot.com', strip_quoted_lines=True)
    self.assertEquals(True, commands_found)
    self.assertEquals('line 2', self.uia.description)
    self.assertEquals('summary:something\n> line 1\nline 2',
                      self.uia.inbound_message)

  def testParse_NoStripQuotedLines(self):
    commands_found = self.uia.Parse(self.cnxn, self.project.project_name, 111,
                   ['summary:something', '> line 1', 'line 2'], self.services,
                   hostport='testing-app.appspot.com')
    self.assertEquals(True, commands_found)
    self.assertEquals('> line 1\nline 2', self.uia.description)
    self.assertIsNone(self.uia.inbound_message)

  def setupAndCallRun(self, mc, commenter_id, mock_pasicn):
    self.uia.Parse(self.cnxn, self.project.project_name, 111,
                   ['summary:something', 'status:New', '> line 1', '> line 2'],
                   self.services, hostport='testing-app.appspot.com')
    self.uia.Run(mc, self.services)

    mock_pasicn.assert_called_once_with(
        self.issue.issue_id, 'testing-app.appspot.com', commenter_id,
        old_owner_id=self.issue.owner_id, comment_id=1, send_email=True)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testRun_AllowEdit(self, mock_pasicn):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='member@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    self.setupAndCallRun(mc, 111, mock_pasicn)

    self.assertEquals('> line 1\n> line 2', self.uia.description)
    # Assert that ammendments were made to the issue.
    self.assertEquals('something', self.issue.summary)
    self.assertEquals('New', self.issue.status)

  @mock.patch(
      'features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testRun_NoAllowEdit(self, mock_pasicn):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='outsider@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    self.setupAndCallRun(mc, 222, mock_pasicn)

    self.assertEquals('> line 1\n> line 2', self.uia.description)
    # Assert that ammendments were *not* made to the issue.
    self.assertEquals('summary', self.issue.summary)
    self.assertEquals('Assigned', self.issue.status)
