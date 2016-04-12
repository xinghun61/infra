# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for notify.py."""

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
        project_id=789,
        local_id=1,
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
        project_id=789,
        hostport='testbed-test.appspotmail.com',
        local_id=1,
        delta_blocker_iids=[],
        commenter_id=1,
        send_email=True)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_BLOCKING_CHANGE_TASK + '.do')
    self.assertEqual(0, len(tasks))

    notify.PrepareAndSendIssueBlockingNotification(
        project_id=789,
        hostport='testbed-test.appspotmail.com',
        local_id=1,
        delta_blocker_iids=[2],
        commenter_id=1,
        send_email=True)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_BLOCKING_CHANGE_TASK + '.do')
    self.assertEqual(1, len(tasks))

  def testSendIssueBulkChangeNotification_CommentOnly(self):
    notify.SendIssueBulkChangeNotification(
        hostport='testbed-test.appspotmail.com',
        project_id=789,
        local_ids=[1],
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
        hostport='testbed-test.appspotmail.com',
        project_id=789,
        local_ids=[1],
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

  def testAddAllEmailTasks(self):
    notify.AddAllEmailTasks(
      tasks=[{'to': 'user'}, {'to': 'user2'}])

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.OUTBOUND_EMAIL_TASK + '.do')
    self.assertEqual(2, len(tasks))


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
    self.services.project.TestAddProject(
        'test-project', owner_ids=[1],
        project_id=12345)
    issue1 = MakeTestIssue(
        project_id=12345, local_id=1, owner_id=2, reporter_id=1)
    self.services.issue.TestAddIssue(issue1)

  def VerifyParams(self, result, params):
    self.assertEqual(
        bool(params['send_email']), result['params']['send_email'])
    if 'id' in params:
      self.assertEqual(params['id'], result['params']['local_id'])
    if 'ids' in params:
      self.assertEqual([int(p) for p in params['ids'].split(',')],
                       result['params']['local_ids'])
    self.assertEqual(params['project_id'], result['params']['project_id'])

  def testNotifyIssueChangeTask(self):
    task = notify.NotifyIssueChangeTask(
        request=None, response=None, services=self.services)
    params = {'send_email': 1, 'project_id': 12345, 'id': 1, 'seq': 0,
              'commenter_id': 2}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.VerifyParams(result, params)

  def testNotifyIssueChangeTask_spam(self):
    issue = MakeTestIssue(
        project_id=12345, local_id=1, owner_id=1, reporter_id=1,
        is_spam=True)
    self.services.issue.TestAddIssue(issue)
    task = notify.NotifyIssueChangeTask(
        request=None, response=None, services=self.services)
    params = {'send_email': 0, 'project_id': 12345, 'id': 1, 'seq': 0,
              'commenter_id': 2}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.assertEquals(0, len(result['notified']))

  def testNotifyBlockingChangeTask(self):
    issue2 = MakeTestIssue(
        project_id=12345, local_id=2, owner_id=2, reporter_id=1)
    self.services.issue.TestAddIssue(issue2)
    task = notify.NotifyBlockingChangeTask(
        request=None, response=None, services=self.services)
    params = {'send_email': 1, 'project_id': 12345, 'id': 1, 'seq': 0,
              'delta_blocker_iids': 2, 'commenter_id': 1}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.VerifyParams(result, params)

  def testNotifyBlockingChangeTask_spam(self):
    issue2 = MakeTestIssue(
        project_id=12345, local_id=2, owner_id=2, reporter_id=1,
        is_spam=True)
    self.services.issue.TestAddIssue(issue2)
    task = notify.NotifyBlockingChangeTask(
        request=None, response=None, services=self.services)
    params = {'send_email': 1, 'project_id': 12345, 'id': 1, 'seq': 0,
              'delta_blocker_iids': 2, 'commenter_id': 1}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.assertEquals(0, len(result['notified']))

  def testNotifyBulkChangeTask(self):
    issue2 = MakeTestIssue(
        project_id=12345, local_id=2, owner_id=2, reporter_id=1)
    self.services.issue.TestAddIssue(issue2)
    task = notify.NotifyBulkChangeTask(
        request=None, response=None, services=self.services)
    params = {'send_email': 1, 'project_id': 12345, 'ids': '1,2', 'seq': 0,
              'old_owner_ids': '1,1', 'commenter_id': 1}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.VerifyParams(result, params)

  def testNotifyBulkChangeTask_spam(self):
    issue2 = MakeTestIssue(
        project_id=12345, local_id=2, owner_id=2, reporter_id=1,
        is_spam=True)
    self.services.issue.TestAddIssue(issue2)
    task = notify.NotifyBulkChangeTask(
        request=None, response=None, services=self.services)
    params = {'send_email': 1, 'project_id': 12345, 'ids': '1,2', 'seq': 0,
              'old_owner_ids': '1,1', 'commenter_id': 1}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.assertEquals(1, len(result['notified']))

  def testOutboundEmailTask(self):
    task = notify.OutboundEmailTask(
        request=None, response=None, services=self.services)
    params = {
        'from_addr': 'requester@example.com',
        'reply_to': 'user@example.com',
        'to': 'user@example.com',
        'subject': 'Test subject'}
    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1},
        params=params,
        method='POST',
        services=self.services)
    result = task.HandleRequest(mr)
    self.assertEqual(params['from_addr'], result['sender'])
    self.assertEqual(params['subject'], result['subject'])
