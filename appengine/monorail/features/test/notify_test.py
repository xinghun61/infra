# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for notify.py."""

import json
import os
import unittest
import urllib
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


class SendNotificationTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_taskqueue_stub()
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    self.taskqueue_stub._root_path = os.path.dirname(
        os.path.dirname(os.path.dirname( __file__ )))

  def tearDown(self):
    self.testbed.deactivate()

  def testPrepareAndSendIssueChangeNotification(self):
    notify.PrepareAndSendIssueChangeNotification(
        issue_id=78901,
        hostport='testbed-test.appspotmail.com',
        commenter_id=1,
        seq_num=0,
        old_owner_id=2,
        send_email=True)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_ISSUE_CHANGE_TASK + '.do')
    self.assertEqual(1, len(tasks))

  def testPrepareAndSendIssueBlockingNotification(self):
    notify.PrepareAndSendIssueBlockingNotification(
        issue_id=78901,
        hostport='testbed-test.appspotmail.com',
        delta_blocker_iids=[],
        commenter_id=1,
        send_email=True)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_BLOCKING_CHANGE_TASK + '.do')
    self.assertEqual(0, len(tasks))

    notify.PrepareAndSendIssueBlockingNotification(
        issue_id=78901,
        hostport='testbed-test.appspotmail.com',
        delta_blocker_iids=[2],
        commenter_id=1,
        send_email=True)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_BLOCKING_CHANGE_TASK + '.do')
    self.assertEqual(1, len(tasks))

  def testSendIssueBulkChangeNotification_CommentOnly(self):
    notify.SendIssueBulkChangeNotification(
        issue_ids=[78901],
        hostport='testbed-test.appspotmail.com',
        old_owner_ids=[2],
        comment_text='comment',
        commenter_id=1,
        amendments=[],
        send_email=True,
        users_by_id=2)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_BULK_CHANGE_TASK + '.do')
    self.assertEqual(1, len(tasks))
    params = dict(urllib.unquote_plus(item).split('=')
                  for item in tasks[0].payload.split('&'))
    self.assertEqual('comment', params['comment_text'])
    self.assertEqual('', params['amendments'])

  def testSendIssueBulkChangeNotification_Normal(self):
    notify.SendIssueBulkChangeNotification(
        issue_ids=[78901],
        hostport='testbed-test.appspotmail.com',
        old_owner_ids=[2],
        comment_text='comment',
        commenter_id=1,
        amendments=[
            tracker_bizobj.MakeStatusAmendment('New', 'Old'),
            tracker_bizobj.MakeLabelsAmendment(['Added'], ['Removed']),
            tracker_bizobj.MakeStatusAmendment('New', 'Old'),
            ],
        send_email=True,
        users_by_id=2)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_BULK_CHANGE_TASK + '.do')
    self.assertEqual(1, len(tasks))
    params = dict(urllib.unquote_plus(item).split('=')
                  for item in tasks[0].payload.split('&'))
    self.assertEqual('comment', params['comment_text'])
    self.assertEqual(
        ['    Status: New',
         '    Labels: -Removed Added'],
        params['amendments'].split('\n'))


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
