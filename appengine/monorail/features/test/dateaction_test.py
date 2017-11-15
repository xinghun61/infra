# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the dateaction module."""

import logging
import time
import unittest

import mox

from google.appengine.api import taskqueue

from features import dateaction
from framework import framework_constants
from framework import framework_views
from framework import timestr
from framework import urls
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


class DateActionCronTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        issue=fake.IssueService())
    self.servlet = dateaction.DateActionCron(
        'req', 'res', services=self.services)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def SetUpHandleRequest(self, mr, expected_iids, expected_capped):
    NOW = 1492120863
    self.mox.StubOutWithMock(time, 'time')
    time.time().MultipleTimes().AndReturn(NOW)
    TIMESTAMP_MIN = (NOW / framework_constants.SECS_PER_DAY *
                     framework_constants.SECS_PER_DAY)
    TIMESTAMP_MAX = TIMESTAMP_MIN + framework_constants.SECS_PER_DAY

    left_joins = [
        ('Issue2FieldValue ON Issue.id = Issue2FieldValue.issue_id', []),
        ('FieldDef ON Issue2FieldValue.field_id = FieldDef.id', []),
        ]
    where = [
        ('FieldDef.field_type = %s', ['date_type']),
        ('FieldDef.date_action IN (%s,%s)',
         ['ping_owner_only', 'ping_participants']),
        ('Issue2FieldValue.date_value >= %s', [TIMESTAMP_MIN]),
        ('Issue2FieldValue.date_value < %s', [TIMESTAMP_MAX]),
        ]
    order_by = [
        ('Issue.id', []),
        ]
    self.mox.StubOutWithMock(self.services.issue, 'RunIssueQuery')
    self.services.issue.RunIssueQuery(
        mr.cnxn, left_joins, where + [('Issue.id > %s', [0])],
        order_by).AndReturn((expected_iids, expected_capped))

  def testHandleRequest_NoMatches(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path=urls.DATE_ACTION_CRON)
    self.SetUpHandleRequest(mr, [], False)
    self.mox.ReplayAll()

    self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()

  def SetUpEnqueueDateAction(self, issue_id):
    self.mox.StubOutWithMock(taskqueue, 'add')
    taskqueue.add(
        url=urls.ISSUE_DATE_ACTION_TASK + '.do',
        params={'issue_id': issue_id})

  def testHandleRequest_OneMatche(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path=urls.DATE_ACTION_CRON)
    self.SetUpHandleRequest(mr, [78901], False)
    self.SetUpEnqueueDateAction(78901)
    self.mox.ReplayAll()

    self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()

  def testEnqueueDateAction(self):
    self.SetUpEnqueueDateAction(78901)
    self.mox.ReplayAll()

    self.servlet.EnqueueDateAction(78901)
    self.mox.VerifyAll()


class IssueDateActionTaskTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        features=fake.FeaturesService(),
        issue=fake.IssueService(),
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue_star=fake.IssueStarService())
    self.servlet = dateaction.IssueDateActionTask(
        'req', 'res', services=self.services)
    self.mox = mox.Mox()

    self.config = self.services.config.GetProjectConfig('cnxn', 789)
    self.config.field_defs = [
        tracker_bizobj.MakeFieldDef(
            123, 789, 'NextAction', tracker_pb2.FieldTypes.DATE_TYPE,
            '', '', False, False, False, None, None, None, False, '',
            None, None, tracker_pb2.DateAction.PING_OWNER_ONLY, 
            'Date of next expected progress update', False),
        tracker_bizobj.MakeFieldDef(
            124, 789, 'EoL', tracker_pb2.FieldTypes.DATE_TYPE,
            '', '', False, False, False, None, None, None, False, '',
            None, None, tracker_pb2.DateAction.PING_OWNER_ONLY, 'doc', False),
        tracker_bizobj.MakeFieldDef(
            125, 789, 'TLsBirthday', tracker_pb2.FieldTypes.DATE_TYPE,
            '', '', False, False, False, None, None, None, False, '',
            None, None, tracker_pb2.DateAction.NO_ACTION, 'doc', False),
        ]
    self.services.config.StoreConfig('cnxn', self.config)
    self.project = self.services.project.TestAddProject('proj', project_id=789)
    self.owner = self.services.user.TestAddUser('owner@example.com', 111L)
    self.date_action_user = self.services.user.TestAddUser(
        'date-action-user@example.com', 555L)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testHandleRequest_IssueHasNoArrivedDates(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path=urls.ISSUE_DATE_ACTION_TASK + '.do?issue_id=78901')
    self.services.issue.TestAddIssue(fake.MakeTestIssue(
        789, 1, 'summary', 'New', 111L, issue_id=78901))
    self.assertEqual(1, len(self.services.issue.GetCommentsForIssue(
        mr.cnxn, 78901)))
    self.mox.ReplayAll()

    self.servlet.HandleRequest(mr)
    self.assertEqual(1, len(self.services.issue.GetCommentsForIssue(
        mr.cnxn, 78901)))
    self.mox.VerifyAll()

  def SetUpEnqueueOutboundEmailTask(self, num_emails):
    self.mox.StubOutWithMock(taskqueue, 'add')
    for _ in range(num_emails):
      taskqueue.add(
        queue_name='outboundemail',
        url=urls.OUTBOUND_EMAIL_TASK + '.do',
        payload=mox.IgnoreArg())

  def testHandleRequest_IssueHasOneArriveDate(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path=urls.ISSUE_DATE_ACTION_TASK + '.do?issue_id=78901')

    now = int(time.time())
    date_str = timestr.TimestampToDateWidgetStr(now)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'New', 111L, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    issue.field_values = [
        tracker_bizobj.MakeFieldValue(123, None, None, None, now, None, False)]
    self.assertEqual(1, len(self.services.issue.GetCommentsForIssue(
        mr.cnxn, 78901)))
    self.SetUpEnqueueOutboundEmailTask(1)
    self.mox.ReplayAll()

    self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    comments = self.services.issue.GetCommentsForIssue(mr.cnxn, 78901)
    self.assertEqual(2, len(comments))
    self.assertEqual(
      'The NextAction date has arrived: %s' % date_str,
      comments[1].content)

  def SetUpFieldValues(self, issue, now):
    issue.field_values = [
        tracker_bizobj.MakeFieldValue(123, None, None, None, now, None, False),
        tracker_bizobj.MakeFieldValue(124, None, None, None, now, None, False),
        tracker_bizobj.MakeFieldValue(125, None, None, None, now, None, False),
        ]

  def testHandleRequest_IssueHasTwoArriveDates(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path=urls.ISSUE_DATE_ACTION_TASK + '.do?issue_id=78901')

    now = int(time.time())
    date_str = timestr.TimestampToDateWidgetStr(now)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'New', 111L, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    self.SetUpFieldValues(issue, now)
    self.assertEqual(1, len(self.services.issue.GetCommentsForIssue(
        mr.cnxn, 78901)))
    self.SetUpEnqueueOutboundEmailTask(1)
    self.mox.ReplayAll()

    self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    comments = self.services.issue.GetCommentsForIssue(mr.cnxn, 78901)
    self.assertEqual(2, len(comments))
    self.assertEqual(
      'The EoL date has arrived: %s\n'
      'The NextAction date has arrived: %s' % (date_str, date_str),
      comments[1].content)

  def MakePingComment(self):
    comment = tracker_pb2.IssueComment()
    comment.project_id = self.project.project_id
    comment.user_id = self.date_action_user.user_id
    comment.content = 'Some date(s) arrived...'
    return comment

  def testMakeEmailTasks_Owner(self):
    """The issue owner gets pinged and the email has expected content."""
    issue = fake.MakeTestIssue(
        789, 1, 'summary', 'New', self.owner.user_id, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    now = int(time.time())
    self.SetUpFieldValues(issue, now)
    issue.project_name = 'proj'
    comment = self.MakePingComment()
    next_action_field_def = self.config.field_defs[0]
    pings = [(next_action_field_def, now)]
    users_by_id = framework_views.MakeAllUserViews(
        'fake cnxn', self.services.user,
        [self.owner.user_id, self.date_action_user.user_id])

    tasks = self.servlet._MakeEmailTasks(
        'fake cnxn', issue, self.project, self.config, comment,
        [], 'example-app.appspot.com', users_by_id, pings)
    self.assertEqual(1, len(tasks))
    notify_owner_task = tasks[0]
    self.assertEqual('owner@example.com', notify_owner_task['to'])
    self.assertEqual(
        'Follow up on issue 1 in proj: summary',
        notify_owner_task['subject'])
    body = notify_owner_task['body']
    self.assertIn(comment.content, body)
    self.assertIn(next_action_field_def.docstring, body)

  def testMakeEmailTasks_Starrer(self):
    """Users who starred the issue are notified iff they opt in."""
    issue = fake.MakeTestIssue(
        789, 1, 'summary', 'New', 0L, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    now = int(time.time())
    self.SetUpFieldValues(issue, now)
    issue.project_name = 'proj'
    comment = self.MakePingComment()
    next_action_field_def = self.config.field_defs[0]
    pings = [(next_action_field_def, now)]

    starrer_333 = self.services.user.TestAddUser('starrer333@example.com', 333L)
    starrer_333.notify_starred_ping = True
    self.services.user.TestAddUser('starrer444@example.com', 444L)
    starrer_ids = [333L, 444L]
    users_by_id = framework_views.MakeAllUserViews(
        'fake cnxn', self.services.user,
        [self.owner.user_id, self.date_action_user.user_id],
        starrer_ids)

    tasks = self.servlet._MakeEmailTasks(
        'fake cnxn', issue, self.project, self.config, comment,
        starrer_ids, 'example-app.appspot.com', users_by_id, pings)
    self.assertEqual(1, len(tasks))
    notify_owner_task = tasks[0]
    self.assertEqual('starrer333@example.com', notify_owner_task['to'])
