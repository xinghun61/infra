# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the spam service."""

import unittest

import mox

from google.appengine.ext import testbed

import settings
from framework import sql
from proto import user_pb2
from proto import tracker_pb2
from services import spam_svc
from testing import fake


def assert_unreached():
  raise Exception('This code should not have been called.')


class SpamServiceTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()

    self.mox = mox.Mox()
    self.mock_report_tbl = self.mox.CreateMock(sql.SQLTableManager)
    self.mock_verdict_tbl = self.mox.CreateMock(sql.SQLTableManager)
    self.mock_issue_tbl = self.mox.CreateMock(sql.SQLTableManager)
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.issue_service = fake.IssueService()
    self.spam_service = spam_svc.SpamService()
    self.spam_service.report_tbl = self.mock_report_tbl
    self.spam_service.verdict_tbl = self.mock_verdict_tbl
    self.spam_service.issue_tbl = self.mock_issue_tbl

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testLookupFlaggers(self):
    self.mock_report_tbl.Select(
        self.cnxn, cols=['user_id', 'comment_id'],
        issue_id=234).AndReturn([[111L, None], [222L, 1]])
    self.mox.ReplayAll()

    issue_reporters, comment_reporters = (
        self.spam_service.LookupIssueFlaggers(self.cnxn, 234))
    self.mox.VerifyAll()
    self.assertItemsEqual([111L], issue_reporters)
    self.assertEqual({1: [222L]}, comment_reporters)

  def testFlagIssues_overThresh(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, reporter_id=111L, owner_id=456,
        summary='sum', status='Live', issue_id=78901)
    issue.assume_stale = False  # We will store this issue.

    self.mock_report_tbl.InsertRows(self.cnxn,
        ['issue_id', 'reported_user_id', 'user_id'],
        [(78901, 111L, 111L)], ignore=True)

    self.mock_report_tbl.Select(self.cnxn,
        cols=['issue_id', 'COUNT(*)'], group_by=['issue_id'],
        issue_id=[78901]).AndReturn([(78901, settings.spam_flag_thresh)])
    self.mock_verdict_tbl.Select(
        self.cnxn, cols=['issue_id', 'reason', 'MAX(created)'],
        group_by=['issue_id'], issue_id=[78901]).AndReturn([])
    self.mock_verdict_tbl.InsertRows(
        self.cnxn, ['issue_id', 'is_spam', 'reason', 'project_id'],
        [(78901, True, 'threshold', 789)], ignore=True)

    self.mox.ReplayAll()
    self.spam_service.FlagIssues(
        self.cnxn, self.issue_service, [issue], 111L, True)
    self.mox.VerifyAll()
    self.assertIn(issue, self.issue_service.updated_issues)

  def testFlagIssues_underThresh(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, reporter_id=111L, owner_id=456,
        summary='sum', status='Live', issue_id=78901)

    self.mock_report_tbl.InsertRows(self.cnxn,
        ['issue_id', 'reported_user_id', 'user_id'],
        [(78901, 111L, 111L)], ignore=True)

    self.mock_report_tbl.Select(self.cnxn,
        cols=['issue_id', 'COUNT(*)'], group_by=['issue_id'],
        issue_id=[78901]).AndReturn([(78901, settings.spam_flag_thresh - 1)])

    self.mock_verdict_tbl.Select(
        self.cnxn, cols=['issue_id', 'reason', 'MAX(created)'],
        group_by=['issue_id'], issue_id=[78901]).AndReturn([])

    self.mox.ReplayAll()
    self.spam_service.FlagIssues(
        self.cnxn, self.issue_service, [issue], 111L, True)
    self.mox.VerifyAll()

    self.assertNotIn(issue, self.issue_service.updated_issues)

  def testUnflagIssue_overThresh(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, reporter_id=111L, owner_id=456,
        summary='sum', status='Live', issue_id=78901, is_spam=True)
    self.mock_report_tbl.Delete(self.cnxn, issue_id=[issue.issue_id],
        comment_id=None, user_id=111L)
    self.mock_report_tbl.Select(self.cnxn,
        cols=['issue_id', 'COUNT(*)'], group_by=['issue_id'],
        issue_id=[78901]).AndReturn([(78901, settings.spam_flag_thresh)])

    self.mock_verdict_tbl.Select(
        self.cnxn, cols=['issue_id', 'reason', 'MAX(created)'],
        group_by=['issue_id'], issue_id=[78901]).AndReturn([])

    self.mox.ReplayAll()
    self.spam_service.FlagIssues(
        self.cnxn, self.issue_service, [issue], 111L, False)
    self.mox.VerifyAll()

    self.assertNotIn(issue, self.issue_service.updated_issues)
    self.assertEqual(True, issue.is_spam)

  def testUnflagIssue_underThresh(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, reporter_id=111L, owner_id=456,
        summary='sum', status='Live', issue_id=78901, is_spam=True)
    issue.assume_stale = False  # We will store this issue.
    self.mock_report_tbl.Delete(self.cnxn, issue_id=[issue.issue_id],
        comment_id=None, user_id=111L)
    self.mock_report_tbl.Select(self.cnxn,
        cols=['issue_id', 'COUNT(*)'], group_by=['issue_id'],
        issue_id=[78901]).AndReturn([(78901, settings.spam_flag_thresh - 1)])

    self.mock_verdict_tbl.Select(
        self.cnxn, cols=['issue_id', 'reason', 'MAX(created)'],
        group_by=['issue_id'], issue_id=[78901]).AndReturn([])
    self.mock_verdict_tbl.InsertRows(
        self.cnxn, ['issue_id', 'is_spam', 'reason', 'project_id'],
        [(78901, False, 'threshold', 789)], ignore=True)

    self.mox.ReplayAll()
    self.spam_service.FlagIssues(
        self.cnxn, self.issue_service, [issue], 111L, False)
    self.mox.VerifyAll()

    self.assertIn(issue, self.issue_service.updated_issues)
    self.assertEqual(False, issue.is_spam)

  def testUnflagIssue_underThreshNoManualOerride(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, reporter_id=111L, owner_id=456,
        summary='sum', status='Live', issue_id=78901, is_spam=True)
    self.mock_report_tbl.Delete(self.cnxn, issue_id=[issue.issue_id],
        comment_id=None, user_id=111L)
    self.mock_report_tbl.Select(self.cnxn,
        cols=['issue_id', 'COUNT(*)'], group_by=['issue_id'],
        issue_id=[78901]).AndReturn([(78901, settings.spam_flag_thresh - 1)])

    self.mock_verdict_tbl.Select(
        self.cnxn, cols=['issue_id', 'reason', 'MAX(created)'],
        group_by=['issue_id'],
        issue_id=[78901]).AndReturn([(78901, 'manual', '')])

    self.mox.ReplayAll()
    self.spam_service.FlagIssues(
        self.cnxn, self.issue_service, [issue], 111L, False)
    self.mox.VerifyAll()

    self.assertNotIn(issue, self.issue_service.updated_issues)
    self.assertEqual(True, issue.is_spam)

  def testGetIssueClassifierQueue_noVerdicts(self):
    self.mock_verdict_tbl.Select(self.cnxn,
        cols=['issue_id', 'is_spam', 'reason', 'classifier_confidence',
              'created'],
        where=[
             ('project_id = %s', [789]),
             ('classifier_confidence <= %s',
                 [settings.classifier_moderation_thresh]),
             ('overruled = %s', [False]),
             ('issue_id IS NOT NULL', []),
        ],
        order_by=[
             ('classifier_confidence ASC', []),
             ('created ASC', [])
        ],
        group_by=['issue_id'],
        offset=0,
        limit=10,
    ).AndReturn([])

    self.mock_verdict_tbl.SelectValue(self.cnxn,
        col='COUNT(*)',
        where=[
            ('project_id = %s', [789]),
            ('classifier_confidence <= %s',
                [settings.classifier_moderation_thresh]),
            ('overruled = %s', [False]),
            ('issue_id IS NOT NULL', []),
        ]).AndReturn(0)

    self.mox.ReplayAll()
    res, count = self.spam_service.GetIssueClassifierQueue(
        self.cnxn, self.issue_service, 789)
    self.mox.VerifyAll()

    self.assertEqual([], res)
    self.assertEqual(0, count)

  def testGetIssueClassifierQueue_someVerdicts(self):
    self.mock_verdict_tbl.Select(self.cnxn,
        cols=['issue_id', 'is_spam', 'reason', 'classifier_confidence',
              'created'],
        where=[
             ('project_id = %s', [789]),
             ('classifier_confidence <= %s',
                 [settings.classifier_moderation_thresh]),
             ('overruled = %s', [False]),
             ('issue_id IS NOT NULL', []),
        ],
        order_by=[
             ('classifier_confidence ASC', []),
             ('created ASC', [])
        ],
        group_by=['issue_id'],
        offset=0,
        limit=10,
    ).AndReturn([[78901, 0, "classifier", 0.9, "2015-12-10 11:06:24"]])

    self.mock_verdict_tbl.SelectValue(self.cnxn,
        col='COUNT(*)',
        where=[
            ('project_id = %s', [789]),
            ('classifier_confidence <= %s',
                [settings.classifier_moderation_thresh]),
            ('overruled = %s', [False]),
            ('issue_id IS NOT NULL', []),
        ]).AndReturn(10)

    self.mox.ReplayAll()
    res, count  = self.spam_service.GetIssueClassifierQueue(
        self.cnxn, self.issue_service, 789)
    self.mox.VerifyAll()
    self.assertEqual(1, len(res))
    self.assertEqual(10, count)
    self.assertEqual(78901, res[0].issue_id)
    self.assertEqual(False, res[0].is_spam)
    self.assertEqual("classifier", res[0].reason)
    self.assertEqual(0.9, res[0].classifier_confidence)
    self.assertEqual("2015-12-10 11:06:24", res[0].verdict_time)

  def testIsExempt_RegularUser(self):
    author = user_pb2.MakeUser(111L, email='test@example.com')
    self.assertFalse(self.spam_service._IsExempt(author, False))
    author = user_pb2.MakeUser(111L, email='test@chromium.org.example.com')
    self.assertFalse(self.spam_service._IsExempt(author, False))

  def testIsExempt_ProjectMember(self):
    author = user_pb2.MakeUser(111L, email='test@example.com')
    self.assertTrue(self.spam_service._IsExempt(author, True))

  def testIsExempt_WhitelistedDomain(self):
    author = user_pb2.MakeUser(111L, email='test@google.com')
    self.assertTrue(self.spam_service._IsExempt(author, False))

  def testIsExempt_TrustedNotToSpam(self):
    author = user_pb2.MakeUser(111L, email='test@example.com')
    author.ignore_action_limits = True
    self.assertTrue(self.spam_service._IsExempt(author, False))

  def testClassifyIssue_spam(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, reporter_id=111L, owner_id=456,
        summary='sum', status='Live', issue_id=78901, is_spam=True)
    self.spam_service._predict = lambda body: 1.0

    # Prevent missing service inits to fail the test.
    self.spam_service.ml_engine = True

    comment_pb = tracker_pb2.IssueComment()
    comment_pb.content = "this is spam"
    reporter = user_pb2.MakeUser(111L, email='test@test.com')
    res = self.spam_service.ClassifyIssue(issue, comment_pb, reporter, False)
    self.assertEqual(1.0, res['confidence_is_spam'])

    reporter.email = 'test@chromium.org.spam.com'
    res = self.spam_service.ClassifyIssue(issue, comment_pb, reporter, False)
    self.assertEqual(1.0, res['confidence_is_spam'])

    reporter.email = 'test.google.com@test.com'
    res = self.spam_service.ClassifyIssue(issue, comment_pb, reporter, False)
    self.assertEqual(1.0, res['confidence_is_spam'])

  def testClassifyIssue_Whitelisted(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, reporter_id=111L, owner_id=456,
        summary='sum', status='Live', issue_id=78901, is_spam=True)
    self.spam_service._predict = assert_unreached

    # Prevent missing service inits to fail the test.
    self.spam_service.ml_engine = True

    comment_pb = tracker_pb2.IssueComment()
    comment_pb.content = "this is spam"
    reporter = user_pb2.MakeUser(111L, email='test@google.com')
    res = self.spam_service.ClassifyIssue(issue, comment_pb, reporter, False)
    self.assertEqual(0.0, res['confidence_is_spam'])
    reporter.email = 'test@chromium.org'
    res = self.spam_service.ClassifyIssue(issue, comment_pb, reporter, False)
    self.assertEqual(0.0, res['confidence_is_spam'])

  def testClassifyIssue_IgnoreActionLimitsAndSpam(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, reporter_id=111L, owner_id=456,
        summary='sum', status='Live', issue_id=78901, is_spam=True)
    self.spam_service._predict = assert_unreached

    # Prevent missing service inits to fail the test.
    self.spam_service.ml_engine = True

    comment_pb = tracker_pb2.IssueComment()
    comment_pb.content = "this is spam"
    reporter = user_pb2.MakeUser(111L, email='test@example.com')
    reporter.ignore_action_limits = True
    res = self.spam_service.ClassifyIssue(issue, comment_pb, reporter, False)
    self.assertEqual(0.0, res['confidence_is_spam'])

  def testClassifyComment_spam(self):
    self.spam_service._predict = lambda body: 1.0

    # Prevent missing service inits to fail the test.
    self.spam_service.ml_engine = True

    commenter = user_pb2.MakeUser(111L, email='test@test.com')
    res = self.spam_service.ClassifyComment('this is spam', commenter, False)
    self.assertEqual(1.0, res['confidence_is_spam'])

    commenter.email = 'test@chromium.org.spam.com'
    res = self.spam_service.ClassifyComment('this is spam', commenter, False)
    self.assertEqual(1.0, res['confidence_is_spam'])

    commenter.email = 'test.google.com@test.com'
    res = self.spam_service.ClassifyComment('this is spam', commenter, False)
    self.assertEqual(1.0, res['confidence_is_spam'])

  def testClassifyComment_Whitelisted(self):
    self.spam_service._predict = assert_unreached

    # Prevent missing service inits to fail the test.
    self.spam_service.ml_engine = True

    commenter = user_pb2.MakeUser(111L, email='test@google.com')
    res = self.spam_service.ClassifyComment('this is spam', commenter, False)
    self.assertEqual(0.0, res['confidence_is_spam'])

    commenter.email = 'test@chromium.org'
    res = self.spam_service.ClassifyComment('this is spam', commenter, False)
    self.assertEqual(0.0, res['confidence_is_spam'])

  def testClassifyComment_IgnoreActionLimitsAndSpam(self):
    self.spam_service._predict = assert_unreached

    # Prevent missing service inits to fail the test.
    self.spam_service.ml_engine = True

    commenter = user_pb2.MakeUser(111L, email='test@example.com')
    commenter.ignore_action_limits = True
    res = self.spam_service.ClassifyComment('this is spam', commenter, False)
    self.assertEqual(0.0, res['confidence_is_spam'])
