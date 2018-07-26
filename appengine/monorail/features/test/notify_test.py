# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for notify.py."""

import json
import logging
import os
import unittest
import webapp2
import webtest

from google.appengine.api import taskqueue
from google.appengine.ext import testbed

from features import notify
from framework import urls
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


def MakeTestIssue(project_id, local_id, owner_id, reporter_id, is_spam=False):
  issue = tracker_pb2.Issue()
  issue.project_id = project_id
  issue.local_id = local_id
  issue.issue_id = 1000 * project_id + local_id
  issue.owner_id = owner_id
  issue.reporter_id = reporter_id
  issue.is_spam = is_spam
  return issue


class NotifyTaskHandleRequestTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_taskqueue_stub()
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    self.taskqueue_stub._root_path = os.path.dirname(
        os.path.dirname(os.path.dirname( __file__ )))
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        issue_star=fake.IssueStarService(),
        features=fake.FeaturesService())
    self.services.user.TestAddUser('requester@example.com', 1)
    self.services.user.TestAddUser('user@example.com', 2)
    self.services.user.TestAddUser('member@example.com', 3)
    self.services.project.TestAddProject(
        'test-project', owner_ids=[1, 3],
        project_id=12345)
    self.issue1 = MakeTestIssue(
        project_id=12345, local_id=1, owner_id=2, reporter_id=1)
    self.services.issue.TestAddIssue(self.issue1)

  def tearDown(self):
    self.testbed.deactivate()

  def VerifyParams(self, result, params):
    self.assertEqual(
        bool(params['send_email']), result['params']['send_email'])
    if 'issue_id' in params:
      self.assertEqual(params['issue_id'], result['params']['issue_id'])
    if 'issue_ids' in params:
      self.assertEqual([int(p) for p in params['issue_ids'].split(',')],
                       result['params']['issue_ids'])

  def testNotifyIssueChangeTask_Normal(self):
    task = notify.NotifyIssueChangeTask(
        request=None, response=None, services=self.services)
    params = {'send_email': 1, 'issue_id': 12345001, 'seq': 0,
              'commenter_id': 2}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.VerifyParams(result, params)

  def testNotifyIssueChangeTask_Spam(self):
    issue = MakeTestIssue(
        project_id=12345, local_id=1, owner_id=1, reporter_id=1,
        is_spam=True)
    self.services.issue.TestAddIssue(issue)
    task = notify.NotifyIssueChangeTask(
        request=None, response=None, services=self.services)
    params = {'send_email': 0, 'issue_id': issue.issue_id, 'seq': 0,
              'commenter_id': 2}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.assertEquals(0, len(result['notified']))

  def testNotifyBlockingChangeTask_Normal(self):
    issue2 = MakeTestIssue(
        project_id=12345, local_id=2, owner_id=2, reporter_id=1)
    self.services.issue.TestAddIssue(issue2)
    task = notify.NotifyBlockingChangeTask(
        request=None, response=None, services=self.services)
    params = {
        'send_email': 1, 'issue_id': issue2.issue_id, 'seq': 0,
        'delta_blocker_iids': 2, 'commenter_id': 1}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.VerifyParams(result, params)

  def testNotifyBlockingChangeTask_Spam(self):
    issue2 = MakeTestIssue(
        project_id=12345, local_id=2, owner_id=2, reporter_id=1,
        is_spam=True)
    self.services.issue.TestAddIssue(issue2)
    task = notify.NotifyBlockingChangeTask(
        request=None, response=None, services=self.services)
    params = {
        'send_email': 1, 'issue_id': issue2.issue_id, 'seq': 0,
        'delta_blocker_iids': 2, 'commenter_id': 1}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.assertEquals(0, len(result['notified']))

  def testNotifyBulkChangeTask_Normal(self):
    """We generate email tasks for each user involved in the issues."""
    issue2 = MakeTestIssue(
        project_id=12345, local_id=2, owner_id=2, reporter_id=1)
    issue2.cc_ids = [3]
    self.services.issue.TestAddIssue(issue2)
    task = notify.NotifyBulkChangeTask(
        request=None, response=None, services=self.services)
    params = {
        'send_email': 1, 'seq': 0,
        'issue_ids': '%d,%d' % (self.issue1.issue_id, issue2.issue_id),
        'old_owner_ids': '1,1', 'commenter_id': 1}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.VerifyParams(result, params)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.OUTBOUND_EMAIL_TASK + '.do')
    self.assertEqual(2, len(tasks))
    for task in tasks:
      task_params = json.loads(task.payload)
      # obfuscated email for non-members
      if 'user' in task_params['to']:
        self.assertIn(u'\u2026', task_params['from_addr'])
      # Full email for members
      if 'member' in task_params['to']:
        self.assertNotIn(u'\u2026', task_params['from_addr'])

  def testNotifyBulkChangeTask_SubscriberGetsEmail(self):
    """If a user subscription matches the issue, notify that user."""
    task = notify.NotifyBulkChangeTask(
        request=None, response=None, services=self.services)
    params = {
        'send_email': 1,
        'issue_ids': '%d' % (self.issue1.issue_id),
        'seq': 0,
        'old_owner_ids': '1', 'commenter_id': 1}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    self.services.user.TestAddUser('subscriber@example.com', 4)
    sq = tracker_bizobj.MakeSavedQuery(
        1, 'all open issues', 2, '', subscription_mode='immediate',
        executes_in_project_ids=[self.issue1.project_id])
    self.services.features.UpdateUserSavedQueries('cnxn', 4, [sq])
    result = task.HandleRequest(mr)
    self.VerifyParams(result, params)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.OUTBOUND_EMAIL_TASK + '.do')
    self.assertEqual(2, len(tasks))

  def testNotifyBulkChangeTask_CCAndSubscriberListsIssueOnce(self):
    """If a user both CCs and subscribes, include issue only once."""
    task = notify.NotifyBulkChangeTask(
        request=None, response=None, services=self.services)
    params = {
        'send_email': 1,
        'issue_ids': '%d' % (self.issue1.issue_id),
        'seq': 0,
        'old_owner_ids': '1', 'commenter_id': 1}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    self.services.user.TestAddUser('subscriber@example.com', 4)
    self.issue1.cc_ids = [4]
    sq = tracker_bizobj.MakeSavedQuery(
        1, 'all open issues', 2, '', subscription_mode='immediate',
        executes_in_project_ids=[self.issue1.project_id])
    self.services.features.UpdateUserSavedQueries('cnxn', 4, [sq])
    result = task.HandleRequest(mr)
    self.VerifyParams(result, params)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.OUTBOUND_EMAIL_TASK + '.do')
    self.assertEqual(2, len(tasks))
    found = False
    for task in tasks:
      task_params = json.loads(task.payload)
      if task_params['to'] == 'subscriber@example.com':
        found = True
        body = task_params['body']
        self.assertEqual(1, body.count('issue %d' % self.issue1.local_id))
    self.assertTrue(found)

  def testNotifyBulkChangeTask_Spam(self):
    """A spam issue is excluded from notification emails."""
    issue2 = MakeTestIssue(
        project_id=12345, local_id=2, owner_id=2, reporter_id=1,
        is_spam=True)
    self.services.issue.TestAddIssue(issue2)
    task = notify.NotifyBulkChangeTask(
        request=None, response=None, services=self.services)
    params = {
        'send_email': 1,
        'issue_ids': '%d,%d' % (self.issue1.issue_id, issue2.issue_id),
        'seq': 0,
        'old_owner_ids': '1,1', 'commenter_id': 1}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.assertEquals(1, len(result['notified']))

  def testNotifyApprovalChangeTask_Normal(self):
    config = self.services.config.GetProjectConfig('cnxn', 12345)
    config.field_defs = [
        # issue's User field with any_comment is notified.
        tracker_bizobj.MakeFieldDef(
            121, 12345, 'TL', tracker_pb2.FieldTypes.USER_TYPE,
            '', '', False, False, False, None, None, None, False, '',
            None, tracker_pb2.NotifyTriggers.ANY_COMMENT, 'no_action',
            'TL, notified on everything', False),
        # issue's User field with never is not notified.
        tracker_bizobj.MakeFieldDef(
            122, 12345, 'silentTL', tracker_pb2.FieldTypes.USER_TYPE,
            '', '', False, False, False, None, None, None, False, '',
            None, tracker_pb2.NotifyTriggers.NEVER, 'no_action',
            'TL, notified on nothing', False),
        # approval's User field with any_comment is notified.
        tracker_bizobj.MakeFieldDef(
            123, 12345, 'otherapprovalTL', tracker_pb2.FieldTypes.USER_TYPE,
            '', '', False, False, False, None, None, None, False, '',
            None, tracker_pb2.NotifyTriggers.ANY_COMMENT, 'no_action',
            'TL on the approvers team', False, approval_id=3),
        # another approval's User field with any_comment is not notified.
        tracker_bizobj.MakeFieldDef(
            124, 12345, 'otherapprovalTL', tracker_pb2.FieldTypes.USER_TYPE,
            '', '', False, False, False, None, None, None, False, '',
            None, tracker_pb2.NotifyTriggers.ANY_COMMENT, 'no_action',
            'TL on another approvers team', False, approval_id=4),
    ]
    self.services.config.StoreConfig('cnxn', config)

    # Custom user_type field TLs
    self.services.user.TestAddUser('TL@example.com', 111L)
    self.services.user.TestAddUser('silentTL@example.com', 222L)
    self.services.user.TestAddUser('approvalTL@example.com', 333L)
    self.services.user.TestAddUser('otherapprovalTL@example.com', 444L)

    # Approvers
    self.services.user.TestAddUser('approver_old@example.com', 7)
    self.services.user.TestAddUser('approver_new@example.com', 8)
    self.services.user.TestAddUser('approver_still@example.com', 9)
    canary_phase = tracker_pb2.Phase(
        name='Canary', phase_id=1, rank=1)
    approval_values = [
        tracker_pb2.ApprovalValue(approval_id=3, approver_ids=[8, 9])]
    approval_issue = MakeTestIssue(
        project_id=12345, local_id=2, owner_id=2, reporter_id=1,
        is_spam=True)
    approval_issue.phases = [canary_phase]
    approval_issue.approval_values = approval_values
    approval_issue.field_values = [
        tracker_bizobj.MakeFieldValue(121, None, None, 111L, None, None, False),
        tracker_bizobj.MakeFieldValue(122, None, None, 222L, None, None, False),
        tracker_bizobj.MakeFieldValue(123, None, None, 333L, None, None, False),
        tracker_bizobj.MakeFieldValue(124, None, None, 444L, None, None, False),
    ]
    self.services.issue.TestAddIssue(approval_issue)

    amend = tracker_bizobj.MakeApprovalApproversAmendment([8], [7])

    comment = tracker_pb2.IssueComment(
        project_id=12345, user_id=9, issue_id=approval_issue.issue_id,
        amendments=[amend], timestamp=1234567890, content='just a comment.')
    self.services.issue.TestAddComment(comment, approval_issue.local_id)

    task = notify.NotifyApprovalChangeTask(
        request=None, response=None, services=self.services)
    params = {
        'send_email': 1,
        'issue_id': approval_issue.issue_id,
        'approval_id': 3,
        'comment_id': comment.id,
    }
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.assertTrue('just a comment' in result['tasks'][0]['body'])
    self.assertTrue('Approvers: -approver' in result['tasks'][0]['body'])
    self.assertItemsEqual(
        ['user@example.com', 'approver_old@example.com',
         'approver_new@example.com', 'TL@example.com',
         'approvalTL@example.com'],
        result['notified'])

  def testNotifyApprovalChangeTask_GetApprovalEmailRecipients(self):
    task = notify.NotifyApprovalChangeTask(
        request=None, response=None, services=self.services)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'New', 111L)
    approval_value = tracker_pb2.ApprovalValue(
        approver_ids=[222L, 333L],
        status=tracker_pb2.ApprovalStatus.APPROVED)
    comment = tracker_pb2.IssueComment(
        project_id=789, user_id=1, issue_id=78901)

    # Comment with not amendments notifies everyone.
    rids = task._GetApprovalEmailRecipients(
        approval_value, comment, issue, [777L, 888L])
    self.assertItemsEqual(rids, [111L, 222L, 333L, 777L, 888L])

    # New APPROVED status notifies owners and any_comment users.
    amendment = tracker_bizobj.MakeApprovalStatusAmendment(
        tracker_pb2.ApprovalStatus.APPROVED)
    comment.amendments = [amendment]
    rids = task._GetApprovalEmailRecipients(
        approval_value, comment, issue, [777L, 888L])
    self.assertItemsEqual(rids, [111L, 777L, 888L])

    # New REVIEW_REQUESTED status notifies approvers.
    approval_value.status = tracker_pb2.ApprovalStatus.REVIEW_REQUESTED
    amendment = tracker_bizobj.MakeApprovalStatusAmendment(
        tracker_pb2.ApprovalStatus.REVIEW_REQUESTED)
    comment.amendments = [amendment]
    rids = task._GetApprovalEmailRecipients(
        approval_value, comment, issue, [777L, 888L])
    self.assertItemsEqual(rids, [222L, 333L])

    # Approvers change notifies everyone.
    amendment = tracker_bizobj.MakeApprovalApproversAmendment(
        [222L], [555L])
    comment.amendments = [amendment]
    approval_value.approver_ids = [222L]
    rids = task._GetApprovalEmailRecipients(
        approval_value, comment, issue, [777L], omit_ids=[444L, 333L])
    self.assertItemsEqual(rids, [111L, 222L, 555L, 777L])

  def testOutboundEmailTask_Normal(self):
    """We can send an email."""
    params = {
        'from_addr': 'requester@example.com',
        'reply_to': 'user@example.com',
        'to': 'user@example.com',
        'subject': 'Test subject'}
    body = json.dumps(params)
    request = webapp2.Request.blank('/', body=body)
    task = notify.OutboundEmailTask(
        request=request, response=None, services=self.services)
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        payload=body,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.assertEqual(params['from_addr'], result['sender'])
    self.assertEqual(params['subject'], result['subject'])

  def testOutboundEmailTask_MissingTo(self):
    """We skip emails that don't specify the To-line."""
    params = {
        'from_addr': 'requester@example.com',
        'reply_to': 'user@example.com',
        'subject': 'Test subject'}
    body = json.dumps(params)
    request = webapp2.Request.blank('/', body=body)
    task = notify.OutboundEmailTask(
        request=request, response=None, services=self.services)
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        payload=body,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.assertEqual('Skipping because no "to" address found.', result['note'])
    self.assertNotIn('from_addr', result)

  def testOutboundEmailTask_BannedUser(self):
    """We don't send emails to banned users.."""
    params = {
        'from_addr': 'requester@example.com',
        'reply_to': 'user@example.com',
        'to': 'banned@example.com',
        'subject': 'Test subject'}
    body = json.dumps(params)
    request = webapp2.Request.blank('/', body=body)
    task = notify.OutboundEmailTask(
        request=request, response=None, services=self.services)
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        payload=body,
        method='POST',
        services=self.services)
    self.services.user.TestAddUser('banned@example.com', 404L, banned=True)
    result = task.HandleRequest(mr)
    self.assertEqual('Skipping because user is banned.', result['note'])
    self.assertNotIn('from_addr', result)
