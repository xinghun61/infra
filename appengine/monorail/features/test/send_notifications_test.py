# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for prepareandsend.py"""

import os
import unittest
import urllib

from google.appengine.ext import testbed

from features import send_notifications
from framework import urls
from tracker import tracker_bizobj


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
    send_notifications.PrepareAndSendIssueChangeNotification(
        issue_id=78901,
        hostport='testbed-test.appspotmail.com',
        commenter_id=1,
        old_owner_id=2,
        send_email=True)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_ISSUE_CHANGE_TASK + '.do')
    self.assertEqual(1, len(tasks))

  def testPrepareAndSendIssueBlockingNotification(self):
    send_notifications.PrepareAndSendIssueBlockingNotification(
        issue_id=78901,
        hostport='testbed-test.appspotmail.com',
        delta_blocker_iids=[],
        commenter_id=1,
        send_email=True)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_BLOCKING_CHANGE_TASK + '.do')
    self.assertEqual(0, len(tasks))

    send_notifications.PrepareAndSendIssueBlockingNotification(
        issue_id=78901,
        hostport='testbed-test.appspotmail.com',
        delta_blocker_iids=[2],
        commenter_id=1,
        send_email=True)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_BLOCKING_CHANGE_TASK + '.do')
    self.assertEqual(1, len(tasks))

  def testPrepareAndSendApprovalChangeNotification(self):
    send_notifications.PrepareAndSendApprovalChangeNotification(
        78901, 3, 'testbed-test.appspotmail.com', 55)

    tasks = self.taskqueue_stub.get_filtered_tasks(
        url=urls.NOTIFY_APPROVAL_CHANGE_TASK + '.do')
    self.assertEqual(1, len(tasks))

  def testSendIssueBulkChangeNotification_CommentOnly(self):
    send_notifications.SendIssueBulkChangeNotification(
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
    send_notifications.SendIssueBulkChangeNotification(
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
