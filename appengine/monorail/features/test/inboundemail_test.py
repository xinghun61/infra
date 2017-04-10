# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.feature.inboundemail."""

import unittest

import mox

from features import commitlogcommands
from features import inboundemail
from framework import emailfmt
from framework import monorailrequest
from framework import permissions
from proto import project_pb2
from proto import tracker_pb2
from proto import user_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class InboundEmailTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=987, process_inbound_email=True)
    self.project_addr = 'proj@monorail.example.com'

    self.issue = tracker_pb2.Issue()
    self.issue.project_id = 987
    self.issue.local_id = 100
    self.services.issue.TestAddIssue(self.issue)

    self.msg = testing_helpers.MakeMessage(
        testing_helpers.HEADER_LINES, 'awesome!')

    request, _ = testing_helpers.GetRequestObjects()
    self.inbound = inboundemail.InboundEmail(request, None, self.services)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testTemplates(self):
    for name, template_path in self.inbound._templates.iteritems():
      assert(name in inboundemail.MSG_TEMPLATES)
      assert(
          template_path.GetTemplatePath().endswith(
              inboundemail.MSG_TEMPLATES[name]))

  def testProcessMail_MsgTooBig(self):
    self.mox.StubOutWithMock(emailfmt, 'IsBodyTooBigToParse')
    emailfmt.IsBodyTooBigToParse(mox.IgnoreArg()).AndReturn(True)
    self.mox.ReplayAll()

    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertEquals(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEquals('user@example.com', email_task['to'])
    self.assertEquals('Email body too long', email_task['subject'])

  def testProcessMail_NoProjectOnToLine(self):
    self.mox.StubOutWithMock(emailfmt, 'IsProjectAddressOnToLine')
    emailfmt.IsProjectAddressOnToLine(
        self.project_addr, [self.project_addr]).AndReturn(False)
    self.mox.ReplayAll()

    ret = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testProcessMail_IssueUnidentified(self):
    self.mox.StubOutWithMock(emailfmt, 'IdentifyProjectAndVerb')
    emailfmt.IdentifyProjectAndVerb(self.project_addr).AndReturn(('proj', None))

    self.mox.StubOutWithMock(emailfmt, 'IdentifyIssue')
    emailfmt.IdentifyIssue('proj', mox.IgnoreArg()).AndReturn((None))

    self.mox.ReplayAll()

    ret = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testProcessMail_ProjectNotLive(self):
    self.project.state = project_pb2.ProjectState.DELETABLE
    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    email_task = email_tasks[0]
    self.assertEquals('user@example.com', email_task['to'])
    self.assertEquals('Project not found', email_task['subject'])

  def testProcessMail_ProjectInboundEmailDisabled(self):
    self.project.process_inbound_email = False
    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    email_task = email_tasks[0]
    self.assertEquals('user@example.com', email_task['to'])
    self.assertEquals('Email replies are not enabled in project proj',
                      email_task['subject'])

  def testProcessMail_NoRefHeader(self):
    self.mox.StubOutWithMock(emailfmt, 'ValidateReferencesHeader')
    emailfmt.ValidateReferencesHeader(
        mox.IgnoreArg(), self.project, mox.IgnoreArg(),
        mox.IgnoreArg()).AndReturn(False)
    self.mox.ReplayAll()

    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertEquals(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEquals('user@example.com', email_task['to'])
    self.assertEquals('Your message is not a reply to a notification email',
                      email_task['subject'])

  def testProcessMail_NoAccount(self):
    self.mox.StubOutWithMock(emailfmt, 'ValidateReferencesHeader')
    emailfmt.ValidateReferencesHeader(
        mox.IgnoreArg(), self.project, mox.IgnoreArg(),
        mox.IgnoreArg()).AndReturn(True)
    self.mox.ReplayAll()

    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertEquals(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEquals('user@example.com', email_task['to'])
    self.assertEquals('Could not determine account of sender',
                      email_task['subject'])

  def testProcessMail_BannedAccount(self):
    self.services.user.TestAddUser('user@example.com', 111L)
    class MockAuthData:
      def __init__(self):
        self.user_pb = user_pb2.MakeUser(111L)
        self.effective_ids = set([1, 2, 3])
        self.user_id = 111L
    mock_auth_data = MockAuthData()
    mock_auth_data.user_pb.banned = 'banned'

    self.mox.StubOutWithMock(emailfmt, 'ValidateReferencesHeader')
    emailfmt.ValidateReferencesHeader(
        mox.IgnoreArg(), self.project, mox.IgnoreArg(),
        mox.IgnoreArg()).AndReturn(True)
    self.mox.StubOutWithMock(monorailrequest.AuthData, 'FromEmail')
    monorailrequest.AuthData.FromEmail(
        mox.IgnoreArg(), 'user@example.com', self.services,
        autocreate=False).AndReturn(mock_auth_data)
    self.mox.ReplayAll()

    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertEquals(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEquals('user@example.com', email_task['to'])
    self.assertEquals('You are banned from using this issue tracker',
                      email_task['subject'])

  def testProcessMail_Success(self):
    self.services.user.TestAddUser('user@example.com', 111L)
    class MockAuthData:
      def __init__(self):
        self.user_pb = user_pb2.MakeUser(111L)
        self.effective_ids = set([1, 2, 3])
        self.user_id = 111L
    mock_auth_data = MockAuthData()

    self.mox.StubOutWithMock(emailfmt, 'ValidateReferencesHeader')
    emailfmt.ValidateReferencesHeader(
        mox.IgnoreArg(), self.project, mox.IgnoreArg(),
        mox.IgnoreArg()).AndReturn(True)

    self.mox.StubOutWithMock(monorailrequest.AuthData, 'FromEmail')
    monorailrequest.AuthData.FromEmail(
        mox.IgnoreArg(), 'user@example.com', self.services,
        autocreate=False).AndReturn(mock_auth_data)

    self.mox.StubOutWithMock(permissions, 'GetPermissions')
    permissions.GetPermissions(
        mock_auth_data.user_pb, mock_auth_data.effective_ids,
        self.project).AndReturn('test permissions')

    self.mox.StubOutWithMock(self.inbound, 'ProcessIssueReply')
    self.inbound.ProcessIssueReply(
        mox.IgnoreArg(), self.project, 123, self.project_addr,
        'user@example.com', 111L, mock_auth_data.effective_ids,
        'test permissions', 'awesome!')

    self.mox.ReplayAll()

    ret = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testProcessAlert_NonWhitelistedSender(self):
    # TODO(zhangtiff): Check to make sure the error path was hit.
    ret = self.inbound.ProcessAlert(
        self.cnxn, self.project, self.project_addr, 'user@malicious.com',
        'user@example.com', 111L, 'issue title', 'issue body', 'incident')
    self.assertIsNone(ret)

  def testProcessAlert_Basic(self):
    self.mox.StubOutWithMock(self.services.config, 'LookupLabelID')
    self.services.config.LookupLabelID(
        self.cnxn, self.project.project_id, 'Incident-Id-incident-1'
    ).AndReturn(None)

    self.mox.StubOutWithMock(self.services.issue, 'CreateIssue')
    self.services.issue.CreateIssue(
        self.cnxn, self.services, self.project.project_id, 'issue title', 'new',
        None, [], ['Infra-Troopers', 'Restrict-View-Google',
        'Incident-Id-incident-1'], [], [], 111L,
        'Filed by user@example.com on behalf of user@google.com\n\nissue body'
        ).AndReturn(None)

    self.mox.ReplayAll()

    ret = self.inbound.ProcessAlert(
        self.cnxn, self.project, self.project_addr, 'user@google.com',
        'user@example.com', 111L, 'issue title', 'issue body', 'incident-1')

    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testProcessIssueReply_NoIssue(self):
    nonexistant_local_id = 200
    email_tasks = self.inbound.ProcessIssueReply(
        self.cnxn, self.project, nonexistant_local_id, self.project_addr,
        'user@example.com', 111L, [1, 2, 3], permissions.USER_PERMISSIONSET,
        'awesome!')
    self.assertEquals(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEquals('user@example.com', email_task['to'])
    self.assertEquals('Could not find issue %d in project %s' % (
                          nonexistant_local_id, self.project.project_name),
                      email_task['subject'])

  def testProcessIssueReply_DeletedIssue(self):
    self.issue.deleted = True
    email_tasks = self.inbound.ProcessIssueReply(
        self.cnxn, self.project, self.issue.local_id, self.project_addr,
        'user@example.com', 111L, [1, 2, 3], permissions.USER_PERMISSIONSET,
        'awesome!')
    self.assertEquals(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEquals('user@example.com', email_task['to'])
    self.assertEquals('Could not find issue %d in project %s' % (
                          self.issue.local_id, self.project.project_name),
                      email_task['subject'])

  def VerifyUserHasNoPerm(self, perms):
    email_tasks = self.inbound.ProcessIssueReply(
        self.cnxn, self.project, self.issue.local_id, self.project_addr,
        'user@example.com', 111L, [1, 2, 3], perms, 'awesome!')
    self.assertEquals(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEquals('user@example.com', email_task['to'])
    self.assertEquals('User does not have permission to add a comment',
                      email_task['subject'])

  def testProcessIssueReply_NoViewPerm(self):
    self.VerifyUserHasNoPerm(permissions.EMPTY_PERMISSIONSET)

  def testProcessIssueReply_CantViewRestrictedIssue(self):
    self.issue.labels.append('Restrict-View-CoreTeam')
    self.VerifyUserHasNoPerm(permissions.USER_PERMISSIONSET)

  def testProcessIssueReply_NoAddIssuePerm(self):
    self.VerifyUserHasNoPerm(permissions.READ_ONLY_PERMISSIONSET)

  def testProcessIssueReply_NoEditIssuePerm(self):
    perms = permissions.USER_PERMISSIONSET
    mock_uia = commitlogcommands.UpdateIssueAction(self.issue.local_id)

    self.mox.StubOutWithMock(commitlogcommands, 'UpdateIssueAction')
    commitlogcommands.UpdateIssueAction(self.issue.local_id).AndReturn(mock_uia)

    self.mox.StubOutWithMock(mock_uia, 'Parse')
    mock_uia.Parse(
        self.cnxn, self.project.project_name, 111L, ['awesome!'], self.services,
        strip_quoted_lines=True)
    self.mox.StubOutWithMock(mock_uia, 'Run')
    # Allow edit is false here because the permission set does not contain
    # EDIT_ISSUE.
    mock_uia.Run(self.cnxn, self.services, allow_edit=False)

    self.mox.ReplayAll()
    ret = self.inbound.ProcessIssueReply(
        self.cnxn, self.project, self.issue.local_id, self.project_addr,
        'from_addr', 111L, [1, 2, 3], perms, 'awesome!')
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testProcessIssueReply_Success(self):
    perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    mock_uia = commitlogcommands.UpdateIssueAction(self.issue.local_id)

    self.mox.StubOutWithMock(commitlogcommands, 'UpdateIssueAction')
    commitlogcommands.UpdateIssueAction(self.issue.local_id).AndReturn(mock_uia)

    self.mox.StubOutWithMock(mock_uia, 'Parse')
    mock_uia.Parse(
        self.cnxn, self.project.project_name, 111L, ['awesome!'], self.services,
        strip_quoted_lines=True)
    self.mox.StubOutWithMock(mock_uia, 'Run')
    mock_uia.Run(self.cnxn, self.services, allow_edit=True)

    self.mox.ReplayAll()
    ret = self.inbound.ProcessIssueReply(
        self.cnxn, self.project, self.issue.local_id, self.project_addr,
        'from_addr', 111L, [1, 2, 3], perms, 'awesome!')
    self.mox.VerifyAll()
    self.assertIsNone(ret)
