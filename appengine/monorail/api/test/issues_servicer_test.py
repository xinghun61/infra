# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the issues servicer."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import sys
import time
import unittest
from mock import ANY, Mock, patch

from google.protobuf import empty_pb2

from components.prpc import codes
from components.prpc import context
from components.prpc import server

from api import issues_servicer
from api import converters
from api.api_proto import common_pb2
from api.api_proto import issues_pb2
from api.api_proto import issue_objects_pb2
from api.api_proto import common_pb2
from businesslogic import work_env
from features import filterrules_helpers
from features import send_notifications
from framework import authdata
from framework import exceptions
from framework import framework_views
from framework import monorailcontext
from framework import permissions
from search import frontendsearchpipeline
from proto import tracker_pb2
from proto import project_pb2
from testing import fake
from tracker import tracker_bizobj
from services import service_manager
from proto import tracker_pb2


class IssuesServicerTest(unittest.TestCase):

  NOW = 1234567890

  def setUp(self):
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        features=fake.FeaturesService(),
        issue=fake.IssueService(),
        issue_star=fake.IssueStarService(),
        project=fake.ProjectService(),
        spam=fake.SpamService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789, owner_ids=[111], contrib_ids=[222, 333])
    self.user_1 = self.services.user.TestAddUser('owner@example.com', 111)
    self.user_2 = self.services.user.TestAddUser('approver2@example.com', 222)
    self.user_3 = self.services.user.TestAddUser('approver3@example.com', 333)
    self.user_4 = self.services.user.TestAddUser('nonmember@example.com', 444)
    self.issue_1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj',
        opened_timestamp=self.NOW, issue_id=1001)
    self.issue_2 = fake.MakeTestIssue(
        789, 2, 'sum', 'New', 111, project_name='proj', issue_id=1002)
    self.issue_1.blocked_on_iids.append(self.issue_2.issue_id)
    self.issue_1.blocked_on_ranks.append(sys.maxint)
    self.services.issue.TestAddIssue(self.issue_1)
    self.services.issue.TestAddIssue(self.issue_2)
    self.issues_svcr = issues_servicer.IssuesServicer(
        self.services, make_rate_limiter=False)
    self.prpc_context = context.ServicerContext()
    self.prpc_context.set_code(server.StatusCode.OK)
    self.auth = authdata.AuthData(user_id=333, email='approver3@example.com')

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
        field_name='DogApproval', field_id=5,
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE,
        applicable_type='')

  def CallWrapped(self, wrapped_handler, *args, **kwargs):
    return wrapped_handler.wrapped(self.issues_svcr, *args, **kwargs)

  def testGetProjectIssueIDsAndConfig_OnlyOneProjectName(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    issue_refs = [
        common_pb2.IssueRef(project_name='proj', local_id=1),
        common_pb2.IssueRef(local_id=2),
        common_pb2.IssueRef(project_name='proj', local_id=3),
    ]
    project, issue_ids, config = self.issues_svcr._GetProjectIssueIDsAndConfig(
        mc, issue_refs)
    self.assertEqual(project, self.project)
    self.assertEqual(issue_ids, [self.issue_1.issue_id, self.issue_2.issue_id])
    self.assertEqual(
        config,
        self.services.config.GetProjectConfig(
            self.cnxn, self.project.project_id))

  def testGetProjectIssueIDsAndConfig_NoProjectName(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    issue_refs = [
        common_pb2.IssueRef(local_id=2),
        common_pb2.IssueRef(local_id=3),
    ]
    with self.assertRaises(exceptions.InputException):
      self.issues_svcr._GetProjectIssueIDsAndConfig(mc, issue_refs)

  def testGetProjectIssueIDsAndConfig_MultipleProjectNames(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    issue_refs = [
        common_pb2.IssueRef(project_name='proj', local_id=2),
        common_pb2.IssueRef(project_name='proj2', local_id=3),
    ]
    with self.assertRaises(exceptions.InputException):
      self.issues_svcr._GetProjectIssueIDsAndConfig(mc, issue_refs)

  def testGetProjectIssueIDsAndConfig_MissingLocalId(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    issue_refs = [
        common_pb2.IssueRef(project_name='proj'),
        common_pb2.IssueRef(project_name='proj', local_id=3),
    ]
    with self.assertRaises(exceptions.InputException):
      self.issues_svcr._GetProjectIssueIDsAndConfig(mc, issue_refs)

  def testCreateIssue_Normal(self):
    """We can create an issue."""
    request = issues_pb2.CreateIssueRequest(
        project_name='proj',
        issue=issue_objects_pb2.Issue(
            project_name='proj', local_id=1, summary='sum'))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    response = self.CallWrapped(self.issues_svcr.CreateIssue, mc, request)

    self.assertEqual('proj', response.project_name)

  def testGetIssue_Normal(self):
    """We can get an issue."""
    request = issues_pb2.GetIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    response = self.CallWrapped(self.issues_svcr.GetIssue, mc, request)

    actual = response.issue
    self.assertEqual('proj', actual.project_name)
    self.assertEqual(1, actual.local_id)
    self.assertEqual(1, len(actual.blocked_on_issue_refs))
    self.assertEqual('proj', actual.blocked_on_issue_refs[0].project_name)
    self.assertEqual(2, actual.blocked_on_issue_refs[0].local_id)

  def testGetIssue_Moved(self):
    """We can get a moved issue."""
    self.services.project.TestAddProject(
        'other', project_id=987, owner_ids=[111], contrib_ids=[111])
    issue = fake.MakeTestIssue(987, 200, 'sum', 'New', 111, issue_id=1010)
    self.services.issue.TestAddIssue(issue)
    self.services.issue.TestAddMovedIssueRef(789, 404, 987, 200)

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    request = issues_pb2.GetIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 404

    response = self.CallWrapped(self.issues_svcr.GetIssue, mc, request)

    ref = response.moved_to_ref
    self.assertEqual(200, ref.local_id)
    self.assertEqual('other', ref.project_name)

  @patch('search.frontendsearchpipeline.FrontendSearchPipeline')
  def testListIssues(self, mock_pipeline):
    """We can get a list of issues from a search."""
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com',
        auth=self.auth)
    users_by_id = framework_views.MakeAllUserViews(
        mc.cnxn, self.services.user, [111])
    config = self.services.config.GetProjectConfig(self.cnxn, 789)

    instance = Mock(
        spec=True, visible_results=[self.issue_1, self.issue_2],
        users_by_id=users_by_id, harmonized_config=config,
        pagination=Mock(total_count=2))
    mock_pipeline.return_value = instance
    instance.SearchForIIDs = Mock()
    instance.MergeAndSortIssues = Mock()
    instance.Paginate = Mock()

    request = issues_pb2.ListIssuesRequest(query='',project_names=['proj'])
    response = self.CallWrapped(self.issues_svcr.ListIssues, mc, request)

    actual_issue_1 = response.issues[0]
    self.assertEqual(actual_issue_1.owner_ref.user_id, 111)
    self.assertEqual('owner@example.com', actual_issue_1.owner_ref.display_name)
    self.assertEqual(actual_issue_1.local_id, 1)

    actual_issue_2 = response.issues[1]
    self.assertEqual(actual_issue_2.owner_ref.user_id, 111)
    self.assertEqual('owner@example.com', actual_issue_2.owner_ref.display_name)
    self.assertEqual(actual_issue_2.local_id, 2)
    self.assertEqual(2, response.total_results)

  def testListReferencedIssues(self):
    """We can get the referenced issues that exist."""
    self.services.project.TestAddProject(
        'other-proj', project_id=788, owner_ids=[111])
    other_issue = fake.MakeTestIssue(
        788, 1, 'sum', 'Fixed', 111, project_name='other-proj', issue_id=78801)
    self.services.issue.TestAddIssue(other_issue)
    # We ignore project_names or local_ids that don't exist in our DB.
    request = issues_pb2.ListReferencedIssuesRequest(
        issue_refs=[
            common_pb2.IssueRef(project_name='proj', local_id=1),
            common_pb2.IssueRef(project_name='other-proj', local_id=1),
            common_pb2.IssueRef(project_name='other-proj', local_id=2),
            common_pb2.IssueRef(project_name='ghost-proj', local_id=1)
            ]
        )
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    response = self.CallWrapped(
        self.issues_svcr.ListReferencedIssues, mc, request)
    self.assertEqual(len(response.closed_refs), 1)
    self.assertEqual(len(response.open_refs), 1)
    self.assertEqual(
        issue_objects_pb2.Issue(
            local_id=1,
            project_name='other-proj',
            summary='sum',
            status_ref=common_pb2.StatusRef(
                status='Fixed'),
            owner_ref=common_pb2.UserRef(
                user_id=111,
                display_name='owner@example.com'),
            reporter_ref=common_pb2.UserRef(
                user_id=111,
                display_name='owner@example.com')),
        response.closed_refs[0])
    self.assertEqual(
        issue_objects_pb2.Issue(
            local_id=1,
            project_name='proj',
            summary='sum',
            status_ref=common_pb2.StatusRef(
                status='New',
                means_open=True),
            owner_ref=common_pb2.UserRef(
                user_id=111,
                display_name='owner@example.com'),
            blocked_on_issue_refs=[common_pb2.IssueRef(
                project_name='proj',
                local_id=2)],
            reporter_ref=common_pb2.UserRef(
                user_id=111,
                display_name='owner@example.com'),
            opened_timestamp=1234567890),
        response.open_refs[0])

  def testListReferencedIssues_MissingInput(self):
    request = issues_pb2.ListReferencedIssuesRequest(
        issue_refs=[common_pb2.IssueRef(local_id=1)])
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.ListReferencedIssues, mc, request)

  def testListApplicableFieldDefs_EmptyIssueRefs(self):
    request = issues_pb2.ListApplicableFieldDefsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.issues_svcr.ListApplicableFieldDefs, mc, request)
    self.assertEqual(response, issues_pb2.ListApplicableFieldDefsResponse())

  def testListApplicableFieldDefs_CrossProjectRequest(self):
    issue_refs = [common_pb2.IssueRef(project_name='proj', local_id=1),
                  common_pb2.IssueRef(project_name='proj2', local_id=2)]
    request = issues_pb2.ListApplicableFieldDefsRequest(issue_refs=issue_refs)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.ListApplicableFieldDefs, mc, request)

  def testListApplicableFieldDefs_MissingProjectName(self):
    issue_refs = [common_pb2.IssueRef(local_id=1),
                  common_pb2.IssueRef(local_id=2)]
    request = issues_pb2.ListApplicableFieldDefsRequest(issue_refs=issue_refs)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.ListApplicableFieldDefs, mc, request)

  def testListApplicableFieldDefs_Normal(self):
    self.issue_1.labels = ['Type-Feedback']
    self.issue_2.approval_values = [
        tracker_pb2.ApprovalValue(approval_id=self.fd_3.field_id)]
    self.fd_1.applicable_type = 'Defect'  # not applicable
    self.fd_2.applicable_type = 'feedback'  # applicable
    self.fd_3.applicable_type = 'ignored'  # is APPROVAL_TYPE, applicable
    self.fd_4.applicable_type = ''  # applicable
    self.fd_5.applicable_type = ''  # is APPROVAl_TYPE, not applicable
    config = tracker_pb2.ProjectIssueConfig(
        project_id=789,
        field_defs=[self.fd_1, self.fd_2, self.fd_3, self.fd_4, self.fd_5])
    self.services.config.StoreConfig(self.cnxn, config)
    issue_refs = [common_pb2.IssueRef(project_name='proj', local_id=1),
                  common_pb2.IssueRef(project_name='proj', local_id=2)]
    request = issues_pb2.ListApplicableFieldDefsRequest(issue_refs=issue_refs)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.issues_svcr.ListApplicableFieldDefs, mc, request)
    converted_field_defs = [converters.ConvertFieldDef(fd, [], {}, config, True)
                            for fd in [self.fd_2, self.fd_3, self.fd_4]]
    self.assertEqual(response, issues_pb2.ListApplicableFieldDefsResponse(
        field_defs=converted_field_defs))

  def testUpdateIssue_Denied_Edit(self):
    """We reject requests to update an issue when the user lacks perms."""
    request = issues_pb2.UpdateIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    request.delta.summary.value = 'new summary'

    # Anon user can never update.
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

    # Signed in user cannot view this issue.
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    self.issue_1.labels = ['Restrict-View-CoreTeam']
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

    # Signed in user cannot edit this issue.
    self.issue_1.labels = ['Restrict-EditIssue-CoreTeam']
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

  @patch('features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_JustAComment(self, _fake_pasicn):
    """We check AddIssueComment when the user is only commenting."""
    request = issues_pb2.UpdateIssueRequest()
    request.comment_content = 'Foo'
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    # Note: no delta.

    # Anon user can never update.
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

    # Signed in user cannot view this issue.
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    self.issue_1.labels = ['Restrict-View-CoreTeam']
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

    # Signed in user cannot edit this issue, but they can still comment.
    self.issue_1.labels = ['Restrict-EditIssue-CoreTeam']
    self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

    # Signed in user cannot post even a text comment.
    self.issue_1.labels = ['Restrict-AddIssueComment-CoreTeam']
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

  @patch('features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_Normal(self, fake_pasicn):
    """We can update an issue."""
    request = issues_pb2.UpdateIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    request.delta.summary.value = 'New summary'
    request.delta.label_refs_add.extend([
        common_pb2.LabelRef(label='Hot')])
    request.comment_content = 'test comment'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    response = self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

    actual = response.issue
    # Intended stuff was changed.
    self.assertEqual(1, len(actual.label_refs))
    self.assertEqual('Hot', actual.label_refs[0].label)
    self.assertEqual('New summary', actual.summary)

    # Other stuff didn't change.
    self.assertEqual('proj', actual.project_name)
    self.assertEqual(1, actual.local_id)
    self.assertEqual(1, len(actual.blocked_on_issue_refs))
    self.assertEqual('proj', actual.blocked_on_issue_refs[0].project_name)
    self.assertEqual(2, actual.blocked_on_issue_refs[0].local_id)

    # A comment was added.
    fake_pasicn.assert_called_once()
    comments = self.services.issue.GetCommentsForIssue(
        self.cnxn, self.issue_1.issue_id)
    self.assertEqual(2, len(comments))
    self.assertEqual('test comment', comments[1].content)

  @patch('features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_CommentOnly(self, fake_pasicn):
    """We can update an issue with a comment w/o making any other changes."""
    request = issues_pb2.UpdateIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    request.comment_content = 'test comment'
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

    # A comment was added.
    fake_pasicn.assert_called_once()
    comments = self.services.issue.GetCommentsForIssue(
        self.cnxn, self.issue_1.issue_id)
    self.assertEqual(2, len(comments))
    self.assertEqual('test comment', comments[1].content)
    self.assertFalse(comments[1].is_description)

  @patch('features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_CommentWithAttachments(self, fake_pasicn):
    """We can update an issue with a comment and attachments."""
    request = issues_pb2.UpdateIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    request.comment_content = 'test comment'
    request.uploads.extend([
          issue_objects_pb2.AttachmentUpload(
              filename='a.txt',
              content='aaaaa')])
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

    # A comment with an attachment was added.
    fake_pasicn.assert_called_once()
    comments = self.services.issue.GetCommentsForIssue(
        self.cnxn, self.issue_1.issue_id)
    self.assertEqual(2, len(comments))
    self.assertEqual('test comment', comments[1].content)
    self.assertFalse(comments[1].is_description)
    self.assertEqual(1, len(comments[1].attachments))
    self.assertEqual('a.txt', comments[1].attachments[0].filename)
    self.assertEqual(5, self.project.attachment_bytes_used)

  @patch('features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_Description(self, fake_pasicn):
    """We can update an issue's description."""
    request = issues_pb2.UpdateIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    request.comment_content = 'new description'
    request.is_description = True
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

    # A comment was added.
    fake_pasicn.assert_called_once()
    comments = self.services.issue.GetCommentsForIssue(
        self.cnxn, self.issue_1.issue_id)
    self.assertEqual(2, len(comments))
    self.assertEqual('new description', comments[1].content)
    self.assertTrue(comments[1].is_description)

  @patch('features.send_notifications.PrepareAndSendIssueChangeNotification')
  def testUpdateIssue_NoOp(self, fake_pasicn):
    """We gracefully ignore requests that have no delta or comment."""
    request = issues_pb2.UpdateIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    response = self.CallWrapped(self.issues_svcr.UpdateIssue, mc, request)

    actual = response.issue
    # Other stuff didn't change.
    self.assertEqual('proj', actual.project_name)
    self.assertEqual(1, actual.local_id)
    self.assertEqual('sum', actual.summary)
    self.assertEqual('New', actual.status_ref.status)

    # No comment was added.
    fake_pasicn.assert_not_called()
    comments = self.services.issue.GetCommentsForIssue(
        self.cnxn, self.issue_1.issue_id)
    self.assertEqual(1, len(comments))

  def testStarIssue_Denied(self):
    """We reject requests to star an issue if the user lacks perms."""
    request = issues_pb2.StarIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    request.starred = True

    # Anon user cannot star an issue.
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.StarIssue, mc, request)

    # User star an issue that they cannot view.
    self.issue_1.labels = ['Restrict-View-CoreTeam']
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.StarIssue, mc, request)

    # The issue was not actually starred.
    self.assertEqual(0, self.issue_1.star_count)

  def testStarIssue_Normal(self):
    """Users can star and unstar issues."""
    request = issues_pb2.StarIssueRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    request.starred = True
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    # First, star it.
    response = self.CallWrapped(self.issues_svcr.StarIssue, mc, request)
    self.assertEqual(1, response.star_count)

    # Then, unstar it.
    request.starred = False
    response = self.CallWrapped(self.issues_svcr.StarIssue, mc, request)
    self.assertEqual(0, response.star_count)

  def testIsIssueStared_Anon(self):
    """Anon users can't star issues, so they always get back False."""
    request = issues_pb2.IsIssueStarredRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    mc.LookupLoggedInUserPerms(self.project)

    response = self.CallWrapped(self.issues_svcr.IsIssueStarred, mc, request)
    self.assertFalse(response.is_starred)

  def testIsIssueStared_Denied(self):
    """Users can't ask about an issue that they cannot currently view."""
    request = issues_pb2.IsIssueStarredRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    self.issue_1.labels = ['Restrict-View-CoreTeam']

    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.IsIssueStarred, mc, request)

  def testIsIssueStared_Normal(self):
    """Users can star and unstar issues."""
    request = issues_pb2.IsIssueStarredRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    # It is not initially starred by this user.
    response = self.CallWrapped(self.issues_svcr.IsIssueStarred, mc, request)
    self.assertFalse(response.is_starred)

    # If we star it, we get response True.
    self.services.issue_star.SetStar(
        self.cnxn, self.services, 'fake config', self.issue_1.issue_id,
        333, True)
    response = self.CallWrapped(self.issues_svcr.IsIssueStarred, mc, request)
    self.assertTrue(response.is_starred)

  def testListStarredIssues_Anon(self):
    """Users can't see their starred issues until they sign in."""
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    mc.LookupLoggedInUserPerms(self.project)

    response = self.CallWrapped(self.issues_svcr.ListStarredIssues, mc, {})
    # Assert that response has an empty list
    self.assertEqual(0, len(response.starred_issue_refs))

  def testListStarredIssues_Normal(self):
    """User can access which issues they've starred."""
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    # First, star some issues
    self.services.issue_star.SetStar(
        self.cnxn, self.services, 'fake config', self.issue_1.issue_id,
        333, True)
    self.services.issue_star.SetStar(
        self.cnxn, self.services, 'fake config', self.issue_2.issue_id,
        333, True)

    # Now test that user can retrieve their star in a list
    response = self.CallWrapped(self.issues_svcr.ListStarredIssues, mc, {})
    self.assertEqual(2, len(response.starred_issue_refs))

  def testListComments_Normal(self):
    """We can get comments on an issue."""
    comment = tracker_pb2.IssueComment(
        user_id=111, timestamp=self.NOW, content='second',
        project_id=789, issue_id=self.issue_1.issue_id, sequence=1)
    self.services.issue.TestAddComment(comment, self.issue_1.local_id)
    request = issues_pb2.ListCommentsRequest()
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    response = self.CallWrapped(self.issues_svcr.ListComments, mc, request)

    actual_0 = response.comments[0]
    actual_1 = response.comments[1]
    expected_0 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=0, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='owner@example.com'),
        timestamp=self.NOW, content='sum', is_spam=False,
        description_num=1, can_delete=True, can_flag=True)
    expected_1 = issue_objects_pb2.Comment(
        project_name='proj', local_id=1, sequence_num=1, is_deleted=False,
        commenter=common_pb2.UserRef(
            user_id=111, display_name='owner@example.com'),
        timestamp=self.NOW, content='second', can_delete=True, can_flag=True)
    self.assertEqual(expected_0, actual_0)
    self.assertEqual(expected_1, actual_1)

  def testListActivities_Normal(self):
    """We can get issue activity."""
    self.services.user.TestAddUser('user@example.com', 444)

    config = tracker_pb2.ProjectIssueConfig(
        project_id=789,
        field_defs=[self.fd_1])
    self.services.config.StoreConfig(self.cnxn, config)

    comment = tracker_pb2.IssueComment(
        user_id=444, timestamp=self.NOW, content='c1',
        project_id=789, issue_id=self.issue_1.issue_id, sequence=1)
    self.services.issue.TestAddComment(comment, self.issue_1.local_id)

    self.services.project.TestAddProject(
        'proj2', project_id=790, owner_ids=[111], contrib_ids=[222, 333])
    issue_2 = fake.MakeTestIssue(
        790, 1, 'sum', 'New', 444, project_name='proj2',
        opened_timestamp=self.NOW, issue_id=2001)
    comment_2 = tracker_pb2.IssueComment(
        user_id=444, timestamp=self.NOW, content='c2',
        project_id=790, issue_id=issue_2.issue_id, sequence=1)
    self.services.issue.TestAddComment(comment_2, issue_2.local_id)
    self.services.issue.TestAddIssue(issue_2)

    issue_3 = fake.MakeTestIssue(
        790, 2, 'sum', 'New', 111, project_name='proj2',
        opened_timestamp=self.NOW, issue_id=2002, labels=['Restrict-View-Foo'])
    comment_3 = tracker_pb2.IssueComment(
        user_id=444, timestamp=self.NOW, content='c3',
        project_id=790, issue_id=issue_3.issue_id, sequence=1)
    self.services.issue.TestAddComment(comment_3, issue_3.local_id)
    self.services.issue.TestAddIssue(issue_3)

    request = issues_pb2.ListActivitiesRequest()
    request.user_ref.user_id = 444
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.ListActivities, mc, request)

    self.maxDiff = None
    self.assertEqual([
        issue_objects_pb2.Comment(
            project_name='proj',
            local_id=1,
            commenter=common_pb2.UserRef(
                user_id=444, display_name='user@example.com'),
            timestamp=self.NOW,
            content='c1',
            sequence_num=1,
            can_delete=True,
            can_flag=True),
        issue_objects_pb2.Comment(
            project_name='proj2',
            local_id=1,
            commenter=common_pb2.UserRef(
                user_id=444, display_name='user@example.com'),
            timestamp=self.NOW,
            content='sum',
            description_num=1,
            can_delete=True,
            can_flag=True),
        issue_objects_pb2.Comment(
            project_name='proj2',
            local_id=1,
            commenter=common_pb2.UserRef(
                user_id=444, display_name='user@example.com'),
            timestamp=self.NOW,
            content='c2',
            sequence_num=1,
            can_delete=True,
            can_flag=True)],
        sorted(
            response.comments,
            key=lambda c: (c.project_name, c.local_id, c.sequence_num)))
    self.assertEqual([
        issue_objects_pb2.IssueSummary(
            project_name='proj',
            local_id=1,
            summary='sum'),
        issue_objects_pb2.IssueSummary(
            project_name='proj2',
            local_id=1,
            summary='sum')],
        sorted(
            response.issue_summaries,
            key=lambda issue: (issue.project_name, issue.local_id)))

  def testListActivities_Amendment(self):
    self.services.user.TestAddUser('user@example.com', 444)

    comment = tracker_pb2.IssueComment(
        user_id=444,
        timestamp=self.NOW,
        amendments=[tracker_bizobj.MakeOwnerAmendment(111, 222)],
        project_id=789,
        issue_id=self.issue_1.issue_id,
        content='',
        sequence=1)
    self.services.issue.TestAddComment(comment, self.issue_1.local_id)

    request = issues_pb2.ListActivitiesRequest()
    request.user_ref.user_id = 444
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.ListActivities, mc, request)

    self.assertEqual([
        issue_objects_pb2.Comment(
            project_name='proj',
            local_id=1,
            commenter=common_pb2.UserRef(
                user_id=444, display_name='user@example.com'),
            timestamp=self.NOW,
            content='',
            sequence_num=1,
            amendments=[issue_objects_pb2.Amendment(
                field_name="Owner",
                new_or_delta_value="ow...@example.com")],
            can_delete=True,
            can_flag=True)],
        sorted(
            response.comments,
            key=lambda c: (c.project_name, c.local_id, c.sequence_num)))
    self.assertEqual([
        issue_objects_pb2.IssueSummary(
            project_name='proj',
            local_id=1,
            summary='sum')],
        sorted(
            response.issue_summaries,
            key=lambda issue: (issue.project_name, issue.local_id)))

  @patch('testing.fake.IssueService.SoftDeleteComment')
  def testDeleteComment_Invalid(self, fake_softdeletecomment):
    """We reject requests to delete a non-existent comment."""
    # Note: no comments added to self.issue_1 after the description.
    request = issues_pb2.DeleteCommentRequest(
        issue_ref=common_pb2.IssueRef(project_name='proj', local_id=1),
        sequence_num=2, delete=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    with self.assertRaises(exceptions.NoSuchCommentException):
      self.CallWrapped(self.issues_svcr.DeleteComment, mc, request)

    fake_softdeletecomment.assert_not_called()

  def testDeleteComment_Normal(self):
    """An authorized user can delete and undelete a comment."""
    comment_1 = tracker_pb2.IssueComment(
        project_id=789, issue_id=self.issue_1.issue_id, content='one')
    self.services.issue.TestAddComment(comment_1, 1)
    comment_2 = tracker_pb2.IssueComment(
        project_id=789, issue_id=self.issue_1.issue_id, content='two',
        user_id=222)
    self.services.issue.TestAddComment(comment_2, 1)

    # Delete a comment.
    request = issues_pb2.DeleteCommentRequest(
        issue_ref=common_pb2.IssueRef(project_name='proj', local_id=1),
        sequence_num=2, delete=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    response = self.CallWrapped(self.issues_svcr.DeleteComment, mc, request)

    self.assertTrue(isinstance(response, empty_pb2.Empty))
    self.assertEqual(111, comment_2.deleted_by)

    # Undelete a comment.
    request.delete=False

    response = self.CallWrapped(self.issues_svcr.DeleteComment, mc, request)

    self.assertTrue(isinstance(response, empty_pb2.Empty))
    self.assertEqual(None, comment_2.deleted_by)

  @patch('testing.fake.IssueService.SoftDeleteComment')
  def testDeleteComment_Denied(self, fake_softdeletecomment):
    """An unauthorized user cannot delete a comment."""
    comment_1 = tracker_pb2.IssueComment(
        project_id=789, issue_id=self.issue_1.issue_id, content='one',
        user_id=222)
    self.services.issue.TestAddComment(comment_1, 1)

    request = issues_pb2.DeleteCommentRequest(
        issue_ref=common_pb2.IssueRef(project_name='proj', local_id=1),
        sequence_num=1, delete=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com')

    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.DeleteComment, mc, request)

    fake_softdeletecomment.assert_not_called()
    self.assertIsNone(comment_1.deleted_by)

  def testUpdateApproval_MissingFieldDef(self):
    """Missing Approval Field Def throwns exception."""
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    field_ref = common_pb2.FieldRef(field_name='LegalApproval')
    approval_delta = issue_objects_pb2.ApprovalDelta(
        status=issue_objects_pb2.REVIEW_REQUESTED)
    request = issues_pb2.UpdateApprovalRequest(
        issue_ref=issue_ref, field_ref=field_ref, approval_delta=approval_delta)

    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com',
        auth=self.auth)

    with self.assertRaises(exceptions.NoSuchFieldDefException):
      self.CallWrapped(self.issues_svcr.UpdateApproval, mc, request)

  def testBulkUpdateApprovals_EmptyIssueRefs(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    request = issues_pb2.BulkUpdateApprovalsRequest(
        field_ref=common_pb2.FieldRef(field_name='LegalApproval'),
        approval_delta=issue_objects_pb2.ApprovalDelta())
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.BulkUpdateApprovals, mc, request)

  def testBulkUpdateApprovals_NoProjectName(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    issue_refs = [common_pb2.IssueRef(local_id=1),
                  common_pb2.IssueRef(local_id=2)]
    request = issues_pb2.BulkUpdateApprovalsRequest(
        issue_refs=issue_refs,
        field_ref=common_pb2.FieldRef(field_name='LegalApproval'),
        approval_delta=issue_objects_pb2.ApprovalDelta())
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.BulkUpdateApprovals, mc, request)

  def testBulkUpdateApprovals_CrossProjectRequest(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    issue_refs = [common_pb2.IssueRef(project_name='p1', local_id=1),
                  common_pb2.IssueRef(project_name='p2', local_id=2)]
    request = issues_pb2.BulkUpdateApprovalsRequest(
        issue_refs=issue_refs,
        field_ref=common_pb2.FieldRef(field_name='LegalApproval'),
        approval_delta=issue_objects_pb2.ApprovalDelta())
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.BulkUpdateApprovals, mc, request)

  def testBulkUpdateApprovals_NoSuchFieldDef(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    issue_refs = [common_pb2.IssueRef(project_name='proj', local_id=1),
                  common_pb2.IssueRef(project_name='proj', local_id=2)]
    request = issues_pb2.BulkUpdateApprovalsRequest(
        issue_refs=issue_refs,
        field_ref=common_pb2.FieldRef(field_name='LegalApproval'),
        approval_delta=issue_objects_pb2.ApprovalDelta())
    with self.assertRaises(exceptions.NoSuchFieldDefException):
      self.CallWrapped(self.issues_svcr.BulkUpdateApprovals, mc, request)

  def testBulkUpdateApprovals_AnonDenied(self):
    """Anon user cannot make any updates"""
    config = tracker_pb2.ProjectIssueConfig(
        project_id=789,
        field_defs=[self.fd_3])
    self.services.config.StoreConfig(self.cnxn, config)
    field_ref = common_pb2.FieldRef(field_name='LegalApproval')
    approval_delta = issue_objects_pb2.ApprovalDelta()
    issue_refs = [common_pb2.IssueRef(project_name='proj', local_id=1),
                  common_pb2.IssueRef(project_name='proj', local_id=2)]
    request = issues_pb2.BulkUpdateApprovalsRequest(
        issue_refs=issue_refs, field_ref=field_ref,
        approval_delta=approval_delta)

    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.BulkUpdateApprovals, mc, request)

  def testBulkUpdateApprovals_UserLacksViewPerms(self):
    """User who cannot view issue cannot update issue."""
    config = tracker_pb2.ProjectIssueConfig(
        project_id=789,
        field_defs=[self.fd_3])
    self.services.config.StoreConfig(self.cnxn, config)
    field_ref = common_pb2.FieldRef(field_name='LegalApproval')
    approval_delta = issue_objects_pb2.ApprovalDelta()
    issue_refs = [common_pb2.IssueRef(project_name='proj', local_id=1),
                  common_pb2.IssueRef(project_name='proj', local_id=2)]
    request = issues_pb2.BulkUpdateApprovalsRequest(
        issue_refs=issue_refs, field_ref=field_ref,
        approval_delta=approval_delta)

    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='nonmember@example.com')
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.BulkUpdateApprovals, mc, request)

  @patch('time.time')
  @patch('businesslogic.work_env.WorkEnv.BulkUpdateIssueApprovals')
  @patch('businesslogic.work_env.WorkEnv.GetIssueRefs')
  def testBulkUpdateApprovals_Normal(
      self, mockGetIssueRefs, mockBulkUpdateIssueApprovals, mockTime):
    """Issue approvals that can be updated are updated and returned."""
    mockTime.return_value = 12345
    mockGetIssueRefs.return_value = {1001: ('proj', 1), 1002: ('proj', 2)}
    config = tracker_pb2.ProjectIssueConfig(
        project_id=789,
        field_defs=[self.fd_3])
    self.services.config.StoreConfig(self.cnxn, config)
    field_ref = common_pb2.FieldRef(field_name='LegalApproval')
    issue_refs = [common_pb2.IssueRef(project_name='proj', local_id=1),
                  common_pb2.IssueRef(project_name='proj', local_id=2)]
    request = issues_pb2.BulkUpdateApprovalsRequest(
        issue_refs=issue_refs, field_ref=field_ref,
        approval_delta=issue_objects_pb2.ApprovalDelta(
            status=issue_objects_pb2.APPROVED),
        comment_content='new bulk comment')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='nonmember@example.com')
    response = self.CallWrapped(
        self.issues_svcr.BulkUpdateApprovals, mc, request)
    self.assertEqual(
        response,
        issues_pb2.BulkUpdateApprovalsResponse(
            issue_refs=[common_pb2.IssueRef(project_name='proj', local_id=1),
                        common_pb2.IssueRef(project_name='proj', local_id=2)]))

    approval_delta = tracker_pb2.ApprovalDelta(
        status=tracker_pb2.ApprovalStatus.APPROVED,
        setter_id=444, set_on=12345)
    mockBulkUpdateIssueApprovals.assert_called_once_with(
        [1001, 1002], 3, self.project, approval_delta,
        'new bulk comment', send_email=False)

  @patch('businesslogic.work_env.WorkEnv.BulkUpdateIssueApprovals')
  @patch('businesslogic.work_env.WorkEnv.GetIssueRefs')
  def testBulkUpdateApprovals_EmptyDelta(
      self, mockGetIssueRefs, mockBulkUpdateIssueApprovals):
    """Bulk update approval requests don't fail with an empty approval delta."""
    mockGetIssueRefs.return_value = {1001: ('proj', 1)}
    config = tracker_pb2.ProjectIssueConfig(
        project_id=789,
        field_defs=[self.fd_3])
    self.services.config.StoreConfig(self.cnxn, config)
    field_ref = common_pb2.FieldRef(field_name='LegalApproval')
    issue_refs = [common_pb2.IssueRef(project_name='proj', local_id=1)]
    request = issues_pb2.BulkUpdateApprovalsRequest(
        issue_refs=issue_refs, field_ref=field_ref,
        comment_content='new bulk comment',
        send_email=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='nonmember@example.com')
    self.CallWrapped(
        self.issues_svcr.BulkUpdateApprovals, mc, request)

    approval_delta = tracker_pb2.ApprovalDelta()
    mockBulkUpdateIssueApprovals.assert_called_once_with(
        [1001], 3, self.project, approval_delta,
        'new bulk comment', send_email=True)


  @patch('businesslogic.work_env.WorkEnv.UpdateIssueApproval')
  @patch('features.send_notifications.PrepareAndSendApprovalChangeNotification')
  def testUpdateApproval(self, _mockPrepareAndSend, mockUpdateIssueApproval):
    """We can update an approval."""

    av_3 = tracker_pb2.ApprovalValue(
            approval_id=3,
            status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW,
            approver_ids=[333]
    )
    self.issue_1.approval_values = [av_3]

    config = self.services.config.GetProjectConfig(
        self.cnxn, 789)
    config.field_defs = [self.fd_1, self.fd_3]

    self.services.config.StoreConfig(self.cnxn, config)

    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    field_ref = common_pb2.FieldRef(field_name='LegalApproval')
    approval_delta = issue_objects_pb2.ApprovalDelta(
        status=issue_objects_pb2.REVIEW_REQUESTED,
        approver_refs_add=[
          common_pb2.UserRef(user_id=222, display_name='approver2@example.com')
          ],
        field_vals_add=[
          issue_objects_pb2.FieldValue(
              field_ref=common_pb2.FieldRef(field_name='FirstField'),
              value='string')
          ]
    )

    request = issues_pb2.UpdateApprovalRequest(
        issue_ref=issue_ref, field_ref=field_ref, approval_delta=approval_delta,
        comment_content='Well, actually'
    )
    request.issue_ref.project_name = 'proj'
    request.issue_ref.local_id = 1
    request.uploads.extend([
          issue_objects_pb2.AttachmentUpload(
              filename='a.txt',
              content='aaaaa')])
    request.kept_attachments.extend([1, 2, 3])
    request.send_email = True

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com',
        auth=self.auth)

    mockUpdateIssueApproval.return_value = [
        tracker_pb2.ApprovalValue(
            approval_id=3,
            status=tracker_pb2.ApprovalStatus.REVIEW_REQUESTED,
            setter_id=333,
            approver_ids=[333, 222]),
        'comment_pb']

    actual = self.CallWrapped(self.issues_svcr.UpdateApproval, mc, request)

    expected = issues_pb2.UpdateApprovalResponse()
    expected.approval.CopyFrom(
      issue_objects_pb2.Approval(
          field_ref=common_pb2.FieldRef(
              field_id=3,
              field_name='LegalApproval',
              type=common_pb2.APPROVAL_TYPE),
          approver_refs=[
              common_pb2.UserRef(
                  user_id=333, display_name='approver3@example.com'),
              common_pb2.UserRef(
                  user_id=222, display_name='approver2@example.com')
              ],
          status=issue_objects_pb2.REVIEW_REQUESTED,
          setter_ref=common_pb2.UserRef(
                  user_id=333, display_name='approver3@example.com'),
          phase_ref=issue_objects_pb2.PhaseRef()
      )
      )

    work_env.WorkEnv(mc, self.services).UpdateIssueApproval.\
    assert_called_once_with(
        self.issue_1.issue_id, 3, ANY, u'Well, actually', False,
        attachments=[(u'a.txt', 'aaaaa', 'text/plain')], send_email=True,
        kept_attachments=[1, 2, 3])
    self.assertEqual(expected, actual)

  @patch('businesslogic.work_env.WorkEnv.UpdateIssueApproval')
  @patch('features.send_notifications.PrepareAndSendApprovalChangeNotification')
  def testUpdateApproval_IsDescription(
      self, _mockPrepareAndSend, mockUpdateIssueApproval):
    """We can update an approval survey."""

    av_3 = tracker_pb2.ApprovalValue(approval_id=3)
    self.issue_1.approval_values = [av_3]

    config = self.services.config.GetProjectConfig(self.cnxn, 789)
    config.field_defs = [self.fd_3]
    self.services.config.StoreConfig(self.cnxn, config)

    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    field_ref = common_pb2.FieldRef(field_name='LegalApproval')
    approval_delta = issue_objects_pb2.ApprovalDelta()

    request = issues_pb2.UpdateApprovalRequest(
        issue_ref=issue_ref, field_ref=field_ref, approval_delta=approval_delta,
        comment_content='Better response.', is_description=True)

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com',
        auth=self.auth)

    mockUpdateIssueApproval.return_value = [
        tracker_pb2.ApprovalValue(approval_id=3),
        'comment_pb']

    actual = self.CallWrapped(self.issues_svcr.UpdateApproval, mc, request)

    expected = issues_pb2.UpdateApprovalResponse()
    expected.approval.CopyFrom(
        issue_objects_pb2.Approval(
            field_ref=common_pb2.FieldRef(
                field_id=3,
                field_name='LegalApproval',
                type=common_pb2.APPROVAL_TYPE),
            setter_ref=common_pb2.UserRef(display_name='----'),
            phase_ref=issue_objects_pb2.PhaseRef()
        )
    )

    work_env.WorkEnv(mc, self.services
    ).UpdateIssueApproval.assert_called_once_with(
        self.issue_1.issue_id, 3,
        tracker_pb2.ApprovalDelta(),
        u'Better response.', True, attachments=[], send_email=False,
        kept_attachments=[])
    self.assertEqual(expected, actual)

  @patch('businesslogic.work_env.WorkEnv.UpdateIssueApproval')
  @patch('features.send_notifications.PrepareAndSendApprovalChangeNotification')
  def testUpdateApproval_EmptyDelta(
      self, _mockPrepareAndSend, mockUpdateIssueApproval):
    self.issue_1.approval_values = [tracker_pb2.ApprovalValue(approval_id=3)]

    config = self.services.config.GetProjectConfig(self.cnxn, 789)
    config.field_defs = [self.fd_3]
    self.services.config.StoreConfig(self.cnxn, config)

    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    field_ref = common_pb2.FieldRef(field_name='LegalApproval')

    request = issues_pb2.UpdateApprovalRequest(
        issue_ref=issue_ref, field_ref=field_ref,
        comment_content='Better response.', is_description=True)

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com',
        auth=self.auth)

    mockUpdateIssueApproval.return_value = [
        tracker_pb2.ApprovalValue(approval_id=3), 'comment_pb']

    actual = self.CallWrapped(self.issues_svcr.UpdateApproval, mc, request)

    approval_value = issue_objects_pb2.Approval(
        field_ref=common_pb2.FieldRef(
            field_id=3,
            field_name='LegalApproval',
            type=common_pb2.APPROVAL_TYPE),
        setter_ref=common_pb2.UserRef(display_name='----'),
        phase_ref=issue_objects_pb2.PhaseRef()
    )
    expected = issues_pb2.UpdateApprovalResponse(approval=approval_value)
    self.assertEqual(expected, actual)

    mockUpdateIssueApproval.assert_called_once_with(
        self.issue_1.issue_id, 3,
        tracker_pb2.ApprovalDelta(),
        u'Better response.', True, attachments=[], send_email=False,
        kept_attachments=[])

  @patch('businesslogic.work_env.WorkEnv.ConvertIssueApprovalsTemplate')
  def testConvertIssueApprovalsTemplate(self, mockWorkEnvConvertApprovals):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com',
        auth=self.auth)
    request = issues_pb2.ConvertIssueApprovalsTemplateRequest(
        issue_ref=common_pb2.IssueRef(project_name='proj', local_id=1),
        template_name='template_name', comment_content='CHICKEN',
        send_email=True)
    response = self.CallWrapped(
        self.issues_svcr.ConvertIssueApprovalsTemplate, mc, request)
    config = self.services.config.GetProjectConfig(self.cnxn, 789)
    mockWorkEnvConvertApprovals.assert_called_once_with(
        config, self.issue_1, 'template_name', request.comment_content,
        send_email=request.send_email)
    self.assertEqual(
        response.issue,
        issue_objects_pb2.Issue(
            project_name='proj',
            local_id=1,
            summary='sum',
            owner_ref=common_pb2.UserRef(
                user_id=111, display_name='owner@example.com'),
            status_ref=common_pb2.StatusRef(status='New', means_open=True),
            blocked_on_issue_refs=[
                common_pb2.IssueRef(project_name='proj', local_id=2)],
            reporter_ref=common_pb2.UserRef(
                user_id=111, display_name='owner@example.com'),
            opened_timestamp=1234567890,
            ))

  def testConvertIssueApprovalsTemplate_MissingRequiredFields(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver3@example.com',
        auth=self.auth)
    request = issues_pb2.ConvertIssueApprovalsTemplateRequest(
        issue_ref=common_pb2.IssueRef(project_name='proj', local_id=1))
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(
          self.issues_svcr.ConvertIssueApprovalsTemplate, mc, request)

    request = issues_pb2.ConvertIssueApprovalsTemplateRequest(
        template_name='name')
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(
          self.issues_svcr.ConvertIssueApprovalsTemplate, mc, request)

  @patch('businesslogic.work_env.WorkEnv.SnapshotCountsQuery')
  def testSnapshotCounts_RequiredFields(self, mockSnapshotCountsQuery):
    """Test that timestamp is required at all times.
    And that label_prefix is required when group_by is 'label'.
    """
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    # Test timestamp is required.
    request = issues_pb2.IssueSnapshotRequest(project_name='proj')
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.IssueSnapshot, mc, request)

    # Test project_name is required.
    request = issues_pb2.IssueSnapshotRequest(timestamp=1531334109)
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.IssueSnapshot, mc, request)

    # Test label_prefix is required when group_by is 'label'.
    request = issues_pb2.IssueSnapshotRequest(timestamp=1531334109,
        project_name='proj', group_by='label')
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.IssueSnapshot, mc, request)

    mockSnapshotCountsQuery.assert_not_called()

  @patch('businesslogic.work_env.WorkEnv.SnapshotCountsQuery')
  def testSnapshotCounts_Basic(self, mockSnapshotCountsQuery):
    """Tests the happy path case."""
    request = issues_pb2.IssueSnapshotRequest(
        timestamp=1531334109, project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mockSnapshotCountsQuery.return_value = ({'total': 123}, [], True)

    response = self.CallWrapped(self.issues_svcr.IssueSnapshot, mc, request)

    self.assertEqual(123, response.snapshot_count[0].count)
    self.assertEqual(0, len(response.unsupported_field))
    self.assertTrue(response.search_limit_reached)
    mockSnapshotCountsQuery.assert_called_once_with(self.project, 1531334109,
      '', query=None, canned_query=None, label_prefix='')

  @patch('businesslogic.work_env.WorkEnv.SnapshotCountsQuery')
  @patch('search.searchpipeline.ReplaceKeywordsWithUserIDs')
  @patch('features.savedqueries_helpers.SavedQueryIDToCond')
  def testSnapshotCounts_ReplacesKeywords(self, mockSavedQueryIDToCond,
                                          mockReplaceKeywordsWithUserIDs,
                                          mockSnapshotCountsQuery):
    """Tests that canned query is unpacked and keywords in query and canned
    query are replaced with user IDs."""
    request = issues_pb2.IssueSnapshotRequest(timestamp=1531334109,
        project_name='proj', query='owner:me', canned_query=3)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mockSavedQueryIDToCond.return_value = 'cc:me'
    mockReplaceKeywordsWithUserIDs.side_effect = [
        ('cc:2345', []), ('owner:1234', [])]
    mockSnapshotCountsQuery.return_value = ({'total': 789}, [], False)

    response = self.CallWrapped(self.issues_svcr.IssueSnapshot, mc, request)

    self.assertEqual(789, response.snapshot_count[0].count)
    self.assertEqual(0, len(response.unsupported_field))
    self.assertFalse(response.search_limit_reached)
    mockSnapshotCountsQuery.assert_called_once_with(self.project, 1531334109,
      '', query='owner:1234', canned_query='cc:2345', label_prefix='')

  @patch('businesslogic.work_env.WorkEnv.SnapshotCountsQuery')
  def testSnapshotCounts_GroupByLabel(self, mockSnapshotCountsQuery):
    """Tests grouping by label with label_prefix and a query.
    But no canned_query.
    """
    request = issues_pb2.IssueSnapshotRequest(timestamp=1531334109,
        project_name='proj', group_by='label', label_prefix='Type',
        query='rutabaga:rutabaga')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mockSnapshotCountsQuery.return_value = (
        {'label1': 123, 'label2': 987},
        ['rutabaga'],
        True)

    response = self.CallWrapped(self.issues_svcr.IssueSnapshot, mc, request)

    self.assertEqual(2, len(response.snapshot_count))
    self.assertEqual('label1', response.snapshot_count[0].dimension)
    self.assertEqual(123, response.snapshot_count[0].count)
    self.assertEqual('label2', response.snapshot_count[1].dimension)
    self.assertEqual(987, response.snapshot_count[1].count)
    self.assertEqual(1, len(response.unsupported_field))
    self.assertEqual('rutabaga', response.unsupported_field[0])
    self.assertTrue(response.search_limit_reached)
    mockSnapshotCountsQuery.assert_called_once_with(self.project, 1531334109,
        'label', label_prefix='Type', query='rutabaga:rutabaga',
        canned_query=None)

  @patch('businesslogic.work_env.WorkEnv.SnapshotCountsQuery')
  def testSnapshotCounts_GroupByComponent(self, mockSnapshotCountsQuery):
    """Tests grouping by component with a query and a canned_query."""
    request = issues_pb2.IssueSnapshotRequest(timestamp=1531334109,
        project_name='proj', group_by='component',
        query='rutabaga:rutabaga', canned_query=2)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mockSnapshotCountsQuery.return_value = (
        {'component1': 123, 'component2': 987},
        ['rutabaga'],
        True)

    response = self.CallWrapped(self.issues_svcr.IssueSnapshot, mc, request)

    self.assertEqual(2, len(response.snapshot_count))
    self.assertEqual('component1', response.snapshot_count[0].dimension)
    self.assertEqual(123, response.snapshot_count[0].count)
    self.assertEqual('component2', response.snapshot_count[1].dimension)
    self.assertEqual(987, response.snapshot_count[1].count)
    self.assertEqual(1, len(response.unsupported_field))
    self.assertEqual('rutabaga', response.unsupported_field[0])
    self.assertTrue(response.search_limit_reached)
    mockSnapshotCountsQuery.assert_called_once_with(self.project, 1531334109,
        'component', label_prefix='', query='rutabaga:rutabaga',
        canned_query='is:open')

  @patch('businesslogic.work_env.WorkEnv.SnapshotCountsQuery')
  def testSnapshotCounts_GroupByOpen(self, mockSnapshotCountsQuery):
    """Tests grouping by open with a query."""
    request = issues_pb2.IssueSnapshotRequest(
        timestamp=1531334109, project_name='proj', group_by='open')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mockSnapshotCountsQuery.return_value = (
        {'Opened': 100, 'Closed': 23}, [], True)

    response = self.CallWrapped(self.issues_svcr.IssueSnapshot, mc, request)

    self.assertEqual(2, len(response.snapshot_count))
    self.assertEqual('Opened', response.snapshot_count[0].dimension)
    self.assertEqual(100, response.snapshot_count[0].count)
    self.assertEqual('Closed', response.snapshot_count[1].dimension)
    self.assertEqual(23, response.snapshot_count[1].count)
    mockSnapshotCountsQuery.assert_called_once_with(self.project, 1531334109,
        'open', label_prefix='', query=None, canned_query=None)

  @patch('businesslogic.work_env.WorkEnv.SnapshotCountsQuery')
  def testSnapshotCounts_GroupByStatus(self, mockSnapshotCountsQuery):
    """Tests grouping by status with a query."""
    request = issues_pb2.IssueSnapshotRequest(
        timestamp=1531334109, project_name='proj', group_by='status')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mockSnapshotCountsQuery.return_value = (
        {'Accepted': 100, 'Fixed': 23}, [], True)

    response = self.CallWrapped(self.issues_svcr.IssueSnapshot, mc, request)

    self.assertEqual(2, len(response.snapshot_count))
    self.assertEqual('Fixed', response.snapshot_count[0].dimension)
    self.assertEqual(23, response.snapshot_count[0].count)
    self.assertEqual('Accepted', response.snapshot_count[1].dimension)
    self.assertEqual(100, response.snapshot_count[1].count)
    mockSnapshotCountsQuery.assert_called_once_with(self.project, 1531334109,
        'status', label_prefix='', query=None, canned_query=None)

  @patch('businesslogic.work_env.WorkEnv.SnapshotCountsQuery')
  def testSnapshotCounts_GroupByOwner(self, mockSnapshotCountsQuery):
    """Tests grouping by status with a query."""
    request = issues_pb2.IssueSnapshotRequest(
        timestamp=1531334109, project_name='proj', group_by='owner')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mockSnapshotCountsQuery.return_value = ({111: 100}, [], True)

    response = self.CallWrapped(self.issues_svcr.IssueSnapshot, mc, request)

    self.assertEqual(1, len(response.snapshot_count))
    self.assertEqual('owner@example.com', response.snapshot_count[0].dimension)
    self.assertEqual(100, response.snapshot_count[0].count)
    mockSnapshotCountsQuery.assert_called_once_with(self.project, 1531334109,
        'owner', label_prefix='', query=None, canned_query=None)

  def AddField(self, name, field_type_str):
    kwargs = {
        'cnxn': self.cnxn,
        'project_id': self.project.project_id,
        'field_name': name,
        'field_type_str': field_type_str}
    kwargs.update({
        arg: None
        for arg in ('applic_type', 'applic_pred', 'is_required', 'is_niche',
                    'is_multivalued', 'min_value', 'max_value', 'regex',
                    'needs_member', 'needs_perm', 'grants_perm', 'notify_on',
                    'date_action_str', 'docstring', 'admin_ids')})
    return self.services.config.CreateFieldDef(**kwargs)

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_NoDerivedFields(self, mockGetFilterRules):
    """When no rules match, we respond with just owner availability."""
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(user_id=111),
        label_refs_add=[common_pb2.LabelRef(label='foo')])

    mockGetFilterRules.return_value = [
        filterrules_helpers.MakeRule('label:bar', add_labels=['baz'])]

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        issues_pb2.PresubmitIssueResponse(
            owner_availability="User never visited",
            owner_availability_state="never"),
        response)

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_IncompleteOwnerEmail(self, mockGetFilterRules):
    """User is in the process of typing in the proposed owner."""
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(display_name='owner@examp'))

    mockGetFilterRules.return_value = []
    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    actual = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        issues_pb2.PresubmitIssueResponse(),
        actual)

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_NewIssue(self, mockGetFilterRules):
    """Proposed owner has a vacation message set."""
    self.user_1.vacation_message = 'In Galapagos Islands'
    issue_ref = common_pb2.IssueRef(project_name='proj')
    issue_delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(user_id=111),
        label_refs_add=[common_pb2.LabelRef(label='foo')])

    mockGetFilterRules.return_value = []

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        issues_pb2.PresubmitIssueResponse(
            owner_availability='In Galapagos Islands',
            owner_availability_state='none'),
        response)

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_OwnerVacation(self, mockGetFilterRules):
    """Proposed owner has a vacation message set."""
    self.user_1.vacation_message = 'In Galapagos Islands'
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(user_id=111),
        label_refs_add=[common_pb2.LabelRef(label='foo')])

    mockGetFilterRules.return_value = []

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        issues_pb2.PresubmitIssueResponse(
            owner_availability='In Galapagos Islands',
            owner_availability_state='none'),
        response)

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_OwnerIsAvailable(self, mockGetFilterRules):
    """Proposed owner not on vacation and has visited recently."""
    self.user_1.last_visit_timestamp = int(time.time())
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(user_id=111),
        label_refs_add=[common_pb2.LabelRef(label='foo')])

    mockGetFilterRules.return_value = []

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        issues_pb2.PresubmitIssueResponse(
            owner_availability='',
            owner_availability_state=''),
        response)

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_DerivedLabels(self, mockGetFilterRules):
    """Test that we can match label rules and return derived labels."""
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(user_id=111),
        label_refs_add=[common_pb2.LabelRef(label='foo')])

    mockGetFilterRules.return_value = [
        filterrules_helpers.MakeRule('label:foo', add_labels=['bar', 'baz'])]

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        [common_pb2.ValueAndWhy(
            value='bar',
            why='Added by rule: IF label:foo THEN ADD LABEL'),
         common_pb2.ValueAndWhy(
            value='baz',
            why='Added by rule: IF label:foo THEN ADD LABEL')],
        [vnw for vnw in response.derived_labels])

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_DerivedOwner(self, mockGetFilterRules):
    """Test that we can match component rules and return derived owners."""
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Foo', 'Foo Docstring', False,
        [], [], 0, 111, [])
    self.issue_1.owner_id = 0
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta(
        comp_refs_add=[common_pb2.ComponentRef(path='Foo')])

    mockGetFilterRules.return_value = [
        filterrules_helpers.MakeRule('component:Foo', default_owner_id=222)]

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        [common_pb2.ValueAndWhy(
            value='approver2@example.com',
            why='Added by rule: IF component:Foo THEN SET DEFAULT OWNER')],
        [vnw for vnw in response.derived_owners])

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_DerivedCCs(self, mockGetFilterRules):
    """Test that we can match field rules and return derived cc emails."""
    field_id = self.AddField('Foo', 'ENUM_TYPE')
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(user_id=111),
        field_vals_add=[issue_objects_pb2.FieldValue(
            value='Bar', field_ref=common_pb2.FieldRef(field_id=field_id))])

    mockGetFilterRules.return_value = [
        filterrules_helpers.MakeRule('Foo=Bar', add_cc_ids=[222, 333])]

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        [common_pb2.ValueAndWhy(
            value='approver2@example.com',
            why='Added by rule: IF Foo=Bar THEN ADD CC'),
         common_pb2.ValueAndWhy(
            value='approver3@example.com',
            why='Added by rule: IF Foo=Bar THEN ADD CC')],
        [vnw for vnw in response.derived_ccs])

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_DerivedCCsNonMember(self, mockGetFilterRules):
    """Test that we can return obscured cc emails to non-members."""
    field_id = self.AddField('Foo', 'ENUM_TYPE')
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(user_id=111),
        field_vals_add=[issue_objects_pb2.FieldValue(
            value='Bar', field_ref=common_pb2.FieldRef(field_id=field_id))])

    mockGetFilterRules.return_value = [
        filterrules_helpers.MakeRule('Foo=Bar', add_cc_ids=[222, 333])]

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='nonmember@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        [common_pb2.ValueAndWhy(
            value='approv...@example.com',
            why='Added by rule: IF Foo=Bar THEN ADD CC'),
         common_pb2.ValueAndWhy(
            value='approv...@example.com',
            why='Added by rule: IF Foo=Bar THEN ADD CC')],
        [vnw for vnw in response.derived_ccs])

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_Warnings(self, mockGetFilterRules):
    """Test that we can match owner rules and return warnings."""
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(user_id=111))

    mockGetFilterRules.return_value = [
        filterrules_helpers.MakeRule(
            'owner:owner@example.com', warning='Owner is too busy')]

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        [common_pb2.ValueAndWhy(
            value='Owner is too busy',
            why='Added by rule: IF owner:owner@example.com THEN ADD WARNING')],
        [vnw for vnw in response.warnings])

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_Errors(self, mockGetFilterRules):
    """Test that we can match owner rules and return errors."""
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta(
        owner_ref=common_pb2.UserRef(user_id=222),
        cc_refs_add=[
            common_pb2.UserRef(user_id=111),
            common_pb2.UserRef(user_id=333)])

    mockGetFilterRules.return_value = [
        filterrules_helpers.MakeRule(
            'cc:owner@example.com', error='Owner is not to be disturbed')]

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        [common_pb2.ValueAndWhy(
            value='Owner is not to be disturbed',
            why='Added by rule: IF cc:owner@example.com THEN ADD ERROR')],
        [vnw for vnw in response.errors])

  @patch('testing.fake.FeaturesService.GetFilterRules')
  def testPresubmitIssue_Errors_ExistingOwner(self, mockGetFilterRules):
    """Test that we apply the rules to the issue + delta, not only delta."""
    issue_ref = common_pb2.IssueRef(project_name='proj', local_id=1)
    issue_delta = issue_objects_pb2.IssueDelta()

    mockGetFilterRules.return_value = [
        filterrules_helpers.MakeRule(
            'owner:owner@example.com', error='Owner is not to be disturbed')]

    request = issues_pb2.PresubmitIssueRequest(
        issue_ref=issue_ref, issue_delta=issue_delta)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.issues_svcr.PresubmitIssue, mc, request)

    self.assertEqual(
        [common_pb2.ValueAndWhy(
            value='Owner is not to be disturbed',
            why='Added by rule: IF owner:owner@example.com THEN ADD ERROR')],
        [vnw for vnw in response.errors])

  def testRerankBlockedOnIssues_SplitBelow(self):
    issues = []
    for idx in range(3, 6):
      issues.append(fake.MakeTestIssue(
          789, idx, 'sum', 'New', 111, project_name='proj', issue_id=1000+idx))
      self.services.issue.TestAddIssue(issues[-1])
      self.issue_1.blocked_on_iids.append(issues[-1].issue_id)
      self.issue_1.blocked_on_ranks.append(self.issue_1.blocked_on_ranks[-1]-1)

    request = issues_pb2.RerankBlockedOnIssuesRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        moved_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=2),
        target_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=4),
        split_above=False)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.issues_svcr.RerankBlockedOnIssues, mc, request)

    self.assertEqual(
        [3, 4, 2, 5],
        [blocked_on_ref.local_id
         for blocked_on_ref in response.blocked_on_issue_refs])

  def testRerankBlockedOnIssues_SplitAbove(self):
    self.project.committer_ids.append(222)
    issues = []
    for idx in range(3, 6):
      issues.append(fake.MakeTestIssue(
          789, idx, 'sum', 'New', 111, project_name='proj', issue_id=1000+idx))
      self.services.issue.TestAddIssue(issues[-1])
      self.issue_1.blocked_on_iids.append(issues[-1].issue_id)
      self.issue_1.blocked_on_ranks.append(self.issue_1.blocked_on_ranks[-1]-1)

    request = issues_pb2.RerankBlockedOnIssuesRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        moved_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=2),
        target_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=4),
        split_above=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver2@example.com')
    response = self.CallWrapped(
        self.issues_svcr.RerankBlockedOnIssues, mc, request)

    self.assertEqual(
        [3, 2, 4, 5],
        [blocked_on_ref.local_id
         for blocked_on_ref in response.blocked_on_issue_refs])

  def testRerankBlockedOnIssues_CantEditIssue(self):
    self.project.committer_ids.append(222)
    issues = []
    for idx in range(3, 6):
      issues.append(fake.MakeTestIssue(
          789, idx, 'sum', 'New', 111, project_name='proj', issue_id=1000+idx))
      self.services.issue.TestAddIssue(issues[-1])
      self.issue_1.blocked_on_iids.append(issues[-1].issue_id)
      self.issue_1.blocked_on_ranks.append(self.issue_1.blocked_on_ranks[-1]-1)

    self.issue_1.labels = ['Restrict-EditIssue-Foo']

    request = issues_pb2.RerankBlockedOnIssuesRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        moved_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=2),
        target_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=4),
        split_above=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver2@example.com')
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.RerankBlockedOnIssues, mc, request)

  def testRerankBlockedOnIssues_ComplexPermissions(self):
    """We can rerank blocked on issues, regardless of perms on other issues.

    If Issue 1 is blocked on Issue 3 and Issue 4, we should be able to reorder
    them as long as we have permission to edit Issue 1, even if we don't have
    permission to view or edit Issues 3 or 4.
    """
    # Issue 3 is in proj2, which we don't have access to.
    project_2 = self.services.project.TestAddProject(
        'proj2', project_id=790, owner_ids=[222], contrib_ids=[333])
    project_2.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    issue_3 = fake.MakeTestIssue(
        790, 3, 'sum', 'New', 111, project_name='proj2', issue_id=1003)

    # Issue 4 requires a permission we don't have in order to edit it.
    issue_4 = fake.MakeTestIssue(
        789, 4, 'sum', 'New', 111, project_name='proj', issue_id=1004)
    issue_4.labels = ['Restrict-EditIssue-Foo']

    self.services.issue.TestAddIssue(issue_3)
    self.services.issue.TestAddIssue(issue_4)

    self.issue_1.blocked_on_iids = [1003, 1004]
    self.issue_1.blocked_on_ranks = [2, 1]

    request = issues_pb2.RerankBlockedOnIssuesRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        moved_ref=common_pb2.IssueRef(
            project_name='proj2',
            local_id=3),
        target_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=4),
        split_above=False)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.issues_svcr.RerankBlockedOnIssues, mc, request)

    self.assertEqual(
        [4, 3],
        [blocked_on_ref.local_id
         for blocked_on_ref in response.blocked_on_issue_refs])

  def testDeleteIssue_Delete(self):
    """We can delete an issue."""
    issue = self.services.issue.GetIssue(self.cnxn, self.issue_1.issue_id)
    self.assertFalse(issue.deleted)

    request = issues_pb2.DeleteIssueRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        delete=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.issues_svcr.DeleteIssue, mc, request)

    issue = self.services.issue.GetIssue(self.cnxn, self.issue_1.issue_id)
    self.assertTrue(issue.deleted)

  def testDeleteIssue_Undelete(self):
    """We can undelete an issue."""
    self.services.issue.SoftDeleteIssue(
        self.cnxn, self.project.project_id, 1, True, self.services.user)
    issue = self.services.issue.GetIssue(self.cnxn, self.issue_1.issue_id)
    self.assertTrue(issue.deleted)

    request = issues_pb2.DeleteIssueRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        delete=False)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.issues_svcr.DeleteIssue, mc, request)

    issue = self.services.issue.GetIssue(self.cnxn, self.issue_1.issue_id)
    self.assertFalse(issue.deleted)

  def testDeleteIssueComment_Delete(self):
    """We can delete an issue comment."""
    comment = tracker_pb2.IssueComment(
        project_id=self.project.project_id,
        issue_id=self.issue_1.issue_id,
        user_id=111,
        content='Foo',
        timestamp=12345)
    self.services.issue.TestAddComment(comment, self.issue_1.local_id)

    request = issues_pb2.DeleteIssueCommentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        delete=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.issues_svcr.DeleteIssueComment, mc, request)

    comment = self.services.issue.GetComment(self.cnxn, comment.id)
    self.assertEqual(111, comment.deleted_by)

  def testDeleteIssueComment_Undelete(self):
    """We can undelete an issue comment."""
    comment = tracker_pb2.IssueComment(
        project_id=self.project.project_id,
        issue_id=self.issue_1.issue_id,
        user_id=111,
        content='Foo',
        timestamp=12345,
        deleted_by=111)
    self.services.issue.TestAddComment(comment, self.issue_1.local_id)

    request = issues_pb2.DeleteIssueCommentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        delete=False)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.issues_svcr.DeleteIssueComment, mc, request)

    comment = self.services.issue.GetComment(self.cnxn, comment.id)
    self.assertIsNone(comment.deleted_by)

  def testDeleteIssueComment_InvalidSequenceNum(self):
    """We can handle invalid sequence numbers."""
    request = issues_pb2.DeleteIssueCommentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        delete=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.DeleteIssueComment, mc, request)

  def testDeleteAttachment_Delete(self):
    """We can delete an issue comment attachment."""
    comment = tracker_pb2.IssueComment(
        project_id=self.project.project_id,
        issue_id=self.issue_1.issue_id,
        user_id=111,
        content='Foo',
        timestamp=12345)
    self.services.issue.TestAddComment(comment, self.issue_1.local_id)
    attachment = tracker_pb2.Attachment()
    self.services.issue.TestAddAttachment(attachment, comment.id, 1)

    request = issues_pb2.DeleteAttachmentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        attachment_id=attachment.attachment_id,
        delete=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(
        self.issues_svcr.DeleteAttachment, mc, request)

    self.assertTrue(attachment.deleted)

  def testDeleteAttachment_Undelete(self):
    """We can undelete an issue comment attachment."""
    comment = tracker_pb2.IssueComment(
        project_id=self.project.project_id,
        issue_id=self.issue_1.issue_id,
        user_id=111,
        content='Foo',
        timestamp=12345,
        deleted_by=111)
    self.services.issue.TestAddComment(comment, self.issue_1.local_id)
    attachment = tracker_pb2.Attachment(deleted=True)
    self.services.issue.TestAddAttachment(attachment, comment.id, 1)

    request = issues_pb2.DeleteAttachmentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        attachment_id=attachment.attachment_id,
        delete=False)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(
        self.issues_svcr.DeleteAttachment, mc, request)

    self.assertFalse(attachment.deleted)

  def testDeleteAttachment_InvalidSequenceNum(self):
    """We can handle invalid sequence numbers."""
    request = issues_pb2.DeleteAttachmentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        attachment_id=1234,
        delete=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(
          self.issues_svcr.DeleteAttachment, mc, request)

  def testFlagIssues_Normal(self):
    """Test that an user can flag an issue as spam."""
    self.services.user.TestAddUser('user@example.com', 999)

    request = issues_pb2.FlagIssuesRequest(
        issue_refs=[
            common_pb2.IssueRef(
                project_name='proj',
                local_id=1),
            common_pb2.IssueRef(
                project_name='proj',
                local_id=2)],
        flag=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')
    self.CallWrapped(self.issues_svcr.FlagIssues, mc, request)

    issue_id = self.issue_1.issue_id
    self.assertEqual(
        [999], self.services.spam.reports_by_issue_id[issue_id])
    self.assertNotIn(
        999, self.services.spam.manual_verdicts_by_issue_id[issue_id])

    issue_id2 = self.issue_2.issue_id
    self.assertEqual(
        [999], self.services.spam.reports_by_issue_id[issue_id2])
    self.assertNotIn(
        999, self.services.spam.manual_verdicts_by_issue_id[issue_id2])

  def testFlagIssues_Unflag(self):
    """Test that we can un-flag an issue as spam."""
    self.services.spam.FlagIssues(
        self.cnxn, self.services.issue, [self.issue_1], 111, True)
    self.services.spam.RecordManualIssueVerdicts(
        self.cnxn, self.services.issue, [self.issue_1], 111, True)

    request = issues_pb2.FlagIssuesRequest(
        issue_refs=[
            common_pb2.IssueRef(
                project_name='proj',
                local_id=1)],
        flag=False)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.issues_svcr.FlagIssues, mc, request)

    issue_id = self.issue_1.issue_id
    self.assertEqual([], self.services.spam.reports_by_issue_id[issue_id])
    self.assertFalse(
        self.services.spam.manual_verdicts_by_issue_id[issue_id][111])

  def testFlagIssues_OwnerAutoVerdict(self):
    """Test that an owner can flag an issue as spam and it is a verdict."""
    request = issues_pb2.FlagIssuesRequest(
        issue_refs=[
            common_pb2.IssueRef(
                project_name='proj',
                local_id=1)],
        flag=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.issues_svcr.FlagIssues, mc, request)

    issue_id = self.issue_1.issue_id
    self.assertEqual(
        [111], self.services.spam.reports_by_issue_id[issue_id])
    self.assertTrue(
        self.services.spam.manual_verdicts_by_issue_id[issue_id][111])

  def testFlagIssues_CommitterAutoVerdict(self):
    """Test that an owner can flag an issue as spam and it is a verdict."""
    self.services.user.TestAddUser('committer@example.com', 999)
    self.services.project.TestAddProjectMembers(
        [999], self.project, fake.COMMITTER_ROLE)

    request = issues_pb2.FlagIssuesRequest(
        issue_refs=[
            common_pb2.IssueRef(
                project_name='proj',
                local_id=1)],
        flag=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='committer@example.com')
    self.CallWrapped(self.issues_svcr.FlagIssues, mc, request)

    issue_id = self.issue_1.issue_id
    self.assertEqual(
        [999], self.services.spam.reports_by_issue_id[issue_id])
    self.assertTrue(
        self.services.spam.manual_verdicts_by_issue_id[issue_id][999])

  def testFlagIssues_ContributorAutoVerdict(self):
    """Test that an owner can flag an issue as spam and it is a verdict."""
    request = issues_pb2.FlagIssuesRequest(
        issue_refs=[
            common_pb2.IssueRef(
                project_name='proj',
                local_id=1)],
        flag=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver2@example.com')
    self.CallWrapped(self.issues_svcr.FlagIssues, mc, request)

    issue_id = self.issue_1.issue_id
    self.assertEqual(
        [222], self.services.spam.reports_by_issue_id[issue_id])
    self.assertTrue(
        self.services.spam.manual_verdicts_by_issue_id[issue_id][222])

  def testFlagIssues_NotAllowed(self):
    """Test that anon users cannot flag issues as spam."""
    request = issues_pb2.FlagIssuesRequest(
        issue_refs=[
            common_pb2.IssueRef(
                project_name='proj',
                local_id=1)],
        flag=True)
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.FlagIssues, mc, request)

    self.assertEqual(
        [], self.services.spam.reports_by_issue_id[self.issue_1.issue_id])
    self.assertEqual({}, self.services.spam.manual_verdicts_by_issue_id)

  def testFlagIssues_CrossProjectNotAllowed(self):
    """Test that cross-project requests are rejected."""
    request = issues_pb2.FlagIssuesRequest(
        issue_refs=[
            common_pb2.IssueRef(
                project_name='proj',
                local_id=1),
            common_pb2.IssueRef(
                project_name='proj2',
                local_id=2)],
        flag=True)
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.FlagIssues, mc, request)

    self.assertEqual(
        [], self.services.spam.reports_by_issue_id[self.issue_1.issue_id])
    self.assertEqual({}, self.services.spam.manual_verdicts_by_issue_id)

  def testFlagIssues_MissingIssueRefs(self):
    request = issues_pb2.FlagIssuesRequest(flag=True)
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.FlagIssues, mc, request)

  def testFlagComment_InvalidSequenceNumber(self):
    """Test that we reject requests with invalid sequence numbers."""
    request = issues_pb2.FlagCommentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        flag=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.issues_svcr.FlagComment, mc, request)

  def testFlagComment_Normal(self):
    """Test that an user can flag a comment as spam."""
    self.services.user.TestAddUser('user@example.com', 999)
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=111,
        issue_id=self.issue_1.issue_id)
    self.services.issue.TestAddComment(comment, 1)

    request = issues_pb2.FlagCommentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        flag=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')
    self.CallWrapped(self.issues_svcr.FlagComment, mc, request)

    comment_reports = self.services.spam.comment_reports_by_issue_id
    manual_verdicts = self.services.spam.manual_verdicts_by_comment_id
    self.assertEqual([999], comment_reports[self.issue_1.issue_id][comment.id])
    self.assertNotIn(999, manual_verdicts[comment.id])

  def testFlagComment_Unflag(self):
    """Test that we can un-flag a comment as spam."""
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=999,
        issue_id=self.issue_1.issue_id)
    self.services.issue.TestAddComment(comment, 1)

    self.services.spam.FlagComment(
        self.cnxn, self.issue_1.issue_id, comment.id, 999, 111, True)
    self.services.spam.RecordManualCommentVerdict(
        self.cnxn, self.services.issue, self.services.user, comment.id, 111,
        True)

    request = issues_pb2.FlagCommentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        flag=False)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.issues_svcr.FlagComment, mc, request)

    comment_reports = self.services.spam.comment_reports_by_issue_id
    manual_verdicts = self.services.spam.manual_verdicts_by_comment_id
    self.assertEqual([], comment_reports[self.issue_1.issue_id][comment.id])
    self.assertFalse(manual_verdicts[comment.id][111])

  def testFlagComment_OwnerAutoVerdict(self):
    """Test that an owner can flag a comment as spam and it is a verdict."""
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=999,
        issue_id=self.issue_1.issue_id)
    self.services.issue.TestAddComment(comment, 1)

    request = issues_pb2.FlagCommentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        flag=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    self.CallWrapped(self.issues_svcr.FlagComment, mc, request)

    comment_reports = self.services.spam.comment_reports_by_issue_id
    manual_verdicts = self.services.spam.manual_verdicts_by_comment_id
    self.assertEqual([111], comment_reports[self.issue_1.issue_id][comment.id])
    self.assertTrue(manual_verdicts[comment.id][111])

  def testFlagComment_CommitterAutoVerdict(self):
    """Test that an owner can flag an issue as spam and it is a verdict."""
    self.services.user.TestAddUser('committer@example.com', 999)
    self.services.project.TestAddProjectMembers(
        [999], self.project, fake.COMMITTER_ROLE)

    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=999,
        issue_id=self.issue_1.issue_id)
    self.services.issue.TestAddComment(comment, 1)

    request = issues_pb2.FlagCommentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        flag=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='committer@example.com')
    self.CallWrapped(self.issues_svcr.FlagComment, mc, request)

    comment_reports = self.services.spam.comment_reports_by_issue_id
    manual_verdicts = self.services.spam.manual_verdicts_by_comment_id
    self.assertEqual([999], comment_reports[self.issue_1.issue_id][comment.id])
    self.assertTrue(manual_verdicts[comment.id][999])

  def testFlagComment_ContributorAutoVerdict(self):
    """Test that an owner can flag an issue as spam and it is a verdict."""
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=999,
        issue_id=self.issue_1.issue_id)
    self.services.issue.TestAddComment(comment, 1)

    request = issues_pb2.FlagCommentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        flag=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver2@example.com')
    self.CallWrapped(self.issues_svcr.FlagComment, mc, request)

    comment_reports = self.services.spam.comment_reports_by_issue_id
    manual_verdicts = self.services.spam.manual_verdicts_by_comment_id
    self.assertEqual([222], comment_reports[self.issue_1.issue_id][comment.id])
    self.assertTrue(manual_verdicts[comment.id][222])

  def testFlagComment_NotAllowed(self):
    """Test that anon users cannot flag issues as spam."""
    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=999,
        issue_id=self.issue_1.issue_id)
    self.services.issue.TestAddComment(comment, 1)

    request = issues_pb2.FlagCommentRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        sequence_num=1,
        flag=True)
    mc = monorailcontext.MonorailContext(self.services, cnxn=self.cnxn)

    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.issues_svcr.FlagComment, mc, request)

    comment_reports = self.services.spam.comment_reports_by_issue_id
    manual_verdicts = self.services.spam.manual_verdicts_by_comment_id
    self.assertNotIn(comment.id, comment_reports[self.issue_1.issue_id])
    self.assertEqual({}, manual_verdicts[comment.id])

  def testListIssuePermissions_Normal(self):
    issue_1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj', issue_id=1001)
    self.services.issue.TestAddIssue(issue_1)

    request = issues_pb2.ListIssuePermissionsRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')

    response = self.CallWrapped(
        self.issues_svcr.ListIssuePermissions, mc, request)
    self.assertEqual(
        issues_pb2.ListIssuePermissionsResponse(
            permissions=[
               'addissuecomment',
               'createissue',
               'deleteown',
               'flagspam',
               'setstar',
               'view']),
        response)

  def testListIssuePermissions_DeletedIssue(self):
    issue_1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj', issue_id=1001)
    issue_1.deleted = True
    self.services.issue.TestAddIssue(issue_1)

    request = issues_pb2.ListIssuePermissionsRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver2@example.com')

    response = self.CallWrapped(
        self.issues_svcr.ListIssuePermissions, mc, request)
    self.assertEqual(
        issues_pb2.ListIssuePermissionsResponse(permissions=['view']),
        response)

  def testListIssuePermissions_CanViewDeletedIssue(self):
    issue_1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj', issue_id=1001)
    issue_1.deleted = True
    self.services.issue.TestAddIssue(issue_1)

    request = issues_pb2.ListIssuePermissionsRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    response = self.CallWrapped(
        self.issues_svcr.ListIssuePermissions, mc, request)
    self.assertEqual(
        issues_pb2.ListIssuePermissionsResponse(permissions=[
            'deleteissue',
            'view']),
        response)

  def testListIssuePermissions_IssueRestrictions(self):
    issue_1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj', issue_id=1001)
    issue_1.labels = ['Restrict-SetStar-CustomPerm']
    self.services.issue.TestAddIssue(issue_1)

    request = issues_pb2.ListIssuePermissionsRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver2@example.com')

    response = self.CallWrapped(
        self.issues_svcr.ListIssuePermissions, mc, request)
    self.assertEqual(
        issues_pb2.ListIssuePermissionsResponse(
            permissions=[
               'addissuecomment',
               'createissue',
               'deleteown',
               'flagspam',
               'verdictspam',
               'view']),
        response)

  def testListIssuePermissions_IssueGrantedPerms(self):
    self.services.config.CreateFieldDef(
        self.cnxn, 789, 'Field Name', 'USER_TYPE', None, None, None, None,
        None, None, None, None, None, None, 'CustomPerm', None, None,
        'Docstring', [])

    issue_1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, project_name='proj', issue_id=1001)
    issue_1.labels = ['Restrict-SetStar-CustomPerm']
    issue_1.field_values = [tracker_pb2.FieldValue(user_id=222, field_id=123)]
    self.services.issue.TestAddIssue(issue_1)

    request = issues_pb2.ListIssuePermissionsRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1))
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='approver2@example.com')

    response = self.CallWrapped(
        self.issues_svcr.ListIssuePermissions, mc, request)
    self.assertEqual(
        issues_pb2.ListIssuePermissionsResponse(
            permissions=[
               'addissuecomment',
               'createissue',
               'customperm',
               'deleteown',
               'flagspam',
               'setstar',
               'verdictspam',
               'view']),
        response)

  @patch('services.tracker_fulltext.IndexIssues')
  @patch('services.tracker_fulltext.UnindexIssues')
  def testMoveIssue_Normal(self, _mock_index, _mock_unindex):
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    self.project.owner_ids = [111]
    target_project = self.services.project.TestAddProject(
      'dest', project_id=988, committer_ids=[111])

    request = issues_pb2.MoveIssueRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        target_project_name='dest')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.issues_svcr.MoveIssue, mc, request)

    self.assertEqual(
        issues_pb2.MoveIssueResponse(
            new_issue_ref=common_pb2.IssueRef(
                project_name='dest',
                local_id=1)),
        response)

    moved_issue = self.services.issue.GetIssueByLocalID(self.cnxn,
        target_project.project_id, 1)
    self.assertEqual(target_project.project_id, moved_issue.project_id)
    self.assertEqual(issue.summary, moved_issue.summary)
    self.assertEqual(moved_issue.reporter_id, 111)

  @patch('services.tracker_fulltext.IndexIssues')
  def testCopyIssue_Normal(self, _mock_index):
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    self.project.owner_ids = [111]

    request = issues_pb2.CopyIssueRequest(
        issue_ref=common_pb2.IssueRef(
            project_name='proj',
            local_id=1),
        target_project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.issues_svcr.CopyIssue, mc, request)

    self.assertEqual(
        issues_pb2.CopyIssueResponse(
            new_issue_ref=common_pb2.IssueRef(
                project_name='proj',
                local_id=3)),
        response)

    copied_issue = self.services.issue.GetIssueByLocalID(self.cnxn,
        self.project.project_id, 3)
    self.assertEqual(self.project.project_id, copied_issue.project_id)
    self.assertEqual(issue.summary, copied_issue.summary)
    self.assertEqual(copied_issue.reporter_id, 111)
