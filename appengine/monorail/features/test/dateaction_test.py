# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the dateaction module."""

import time
import unittest

import mox

from google.appengine.api import taskqueue

from features import dateaction
from framework import framework_constants
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

  def testEnqueueDateAction(self):
    self.SetUpEnqueueDateAction(78901)
    self.mox.ReplayAll()

    self.servlet.EnqueueDateAction(78901)


class IssueDateActionTaskTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        issue=fake.IssueService(),
        config=fake.ConfigService())
    self.servlet = dateaction.IssueDateActionTask(
        'req', 'res', services=self.services)
    self.mox = mox.Mox()

    self.config = self.services.config.GetProjectConfig('cnxn', 789)
    self.config.field_defs = [
        tracker_bizobj.MakeFieldDef(
            123, 789, 'NextAction', tracker_pb2.FieldTypes.DATE_TYPE,
            '', '', False, False, False, None, None, None, False, '',
            None, None, tracker_pb2.DateAction.PING_OWNER_ONLY, 'doc', False),
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

    self.servlet.HandleRequest(mr)
    self.assertEqual(1, len(self.services.issue.GetCommentsForIssue(
        mr.cnxn, 78901)))

  def testHandleRequest_IssueHasOneArriveDate(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path=urls.ISSUE_DATE_ACTION_TASK + '.do?issue_id=78901')

    now = int(time.time())
    date_str = timestr.TimestampToDateWidgetStr(now)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'New', 111L, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    issue.field_values = [
        tracker_bizobj.MakeFieldValue(123, None, None, None, now, False)]
    self.assertEqual(1, len(self.services.issue.GetCommentsForIssue(
        mr.cnxn, 78901)))

    self.servlet.HandleRequest(mr)
    comments = self.services.issue.GetCommentsForIssue(mr.cnxn, 78901)
    self.assertEqual(2, len(comments))
    self.assertEqual(
      'The NextAction date has arrived: %s' % date_str,
      comments[1].content)

  def testHandleRequest_IssueHasTwoArriveDates(self):
    _request, mr = testing_helpers.GetRequestObjects(
        path=urls.ISSUE_DATE_ACTION_TASK + '.do?issue_id=78901')

    now = int(time.time())
    date_str = timestr.TimestampToDateWidgetStr(now)
    issue = fake.MakeTestIssue(789, 1, 'summary', 'New', 111L, issue_id=78901)
    self.services.issue.TestAddIssue(issue)
    issue.field_values = [
        tracker_bizobj.MakeFieldValue(123, None, None, None, now, False),
        tracker_bizobj.MakeFieldValue(124, None, None, None, now, False),
        tracker_bizobj.MakeFieldValue(125, None, None, None, now, False),
        ]
    self.assertEqual(1, len(self.services.issue.GetCommentsForIssue(
        mr.cnxn, 78901)))

    self.servlet.HandleRequest(mr)
    comments = self.services.issue.GetCommentsForIssue(mr.cnxn, 78901)
    self.assertEqual(2, len(comments))
    self.assertEqual(
      'The EoL date has arrived: %s\n'
      'The NextAction date has arrived: %s' % (date_str, date_str),
      comments[1].content)
