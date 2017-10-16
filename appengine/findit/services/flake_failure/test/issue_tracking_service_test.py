# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import datetime
from monorail_api import Issue
from waterfall.test import wf_testcase
from libs import time_util

from model.flake.master_flake_analysis import MasterFlakeAnalysis
from services.flake_failure import issue_tracking_service
from waterfall.flake import flake_constants


class IssueTrackingServiceTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      '_HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=False)
  def testShouldFileBugForAnalysis(self, label_exists_fn, id_exists_fn,
                                   sufficient_confidence_fn,
                                   previous_attempt_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    self.assertTrue(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(label_exists_fn.called)
    self.assertTrue(id_exists_fn.called)
    self.assertTrue(sufficient_confidence_fn.called)
    self.assertTrue(previous_attempt_fn.called)

  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      '_HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=True)
  def testShouldFileBugForAnalysisWhenBugIdExists(self, id_exists_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.bug_id = 1
    analysis.Save()

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(id_exists_fn.called)

  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      '_HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=True)
  def testShouldFileBugForAnalysisWhenLabelExists(self, label_exists_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(label_exists_fn.called)

  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      '_HasSufficientConfidenceInCulprit',
      return_value=False)
  def testShouldFileBugForAnalysisWithoutSufficientConfidence(
      self, confidence_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.confidence_in_culprit = 0.5
    analysis.Save()

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(confidence_fn.called)

  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForId', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'BugAlreadyExistsForLabel', return_value=False)
  @mock.patch.object(
      issue_tracking_service,
      '_HasSufficientConfidenceInCulprit',
      return_value=True)
  @mock.patch.object(
      issue_tracking_service, '_HasPreviousAttempt', return_value=True)
  def testShouldFileBugForAnalysisWithPreviousAttempt(self, attempt_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.confidence_in_culprit = 0.5
    analysis.Save()

    self.assertFalse(issue_tracking_service.ShouldFileBugForAnalysis(analysis))
    self.assertTrue(attempt_fn.called)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2017, 1, 3))
  @mock.patch('services.flake_failure.issue_tracking_service.IssueTrackerAPI')
  def testBugAlreadyExistsForId(self, mock_api, _):
    mock_api.return_value.getIssue.return_value = None
    self.assertFalse(issue_tracking_service.BugAlreadyExistsForId(None))
    self.assertFalse(mock_api.return_value.getIssue.called)
    mock_api.reset_mock()

    mock_api.return_value.getIssue.return_value = None
    self.assertFalse(issue_tracking_service.BugAlreadyExistsForId(1234))
    self.assertTrue(mock_api.return_value.getIssue.called)
    args, _ = mock_api.return_value.getIssue.call_args
    self.assertEqual((1234,), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = True
    mock_issue.updated = datetime.datetime(2017, 1, 1)
    mock_issue.merged_into = None
    mock_api.return_value.getIssue.return_value = mock_issue
    self.assertTrue(issue_tracking_service.BugAlreadyExistsForId(1234))
    self.assertTrue(mock_api.return_value.getIssue.called)
    args, _ = mock_api.return_value.getIssue.call_args
    self.assertEqual((1234,), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = False
    mock_issue.updated = datetime.datetime(2017, 1, 2)
    mock_issue.merged_into = None
    mock_api.return_value.getIssue.return_value = mock_issue
    self.assertFalse(issue_tracking_service.BugAlreadyExistsForId(1234))
    self.assertTrue(mock_api.return_value.getIssue.called)
    args, _ = mock_api.return_value.getIssue.call_args
    self.assertEqual((1234,), args)
    mock_api.reset_mock()

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2017, 1, 3))
  @mock.patch('services.flake_failure.issue_tracking_service.IssueTrackerAPI')
  def testBugAlreadyExistsForLabel(self, mock_api, _):
    with self.assertRaises(AssertionError):
      issue_tracking_service.BugAlreadyExistsForLabel(None)

    mock_api.return_value.getIssues.return_value = None
    self.assertFalse(issue_tracking_service.BugAlreadyExistsForLabel('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('label:test',), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = True
    mock_issue.updated = datetime.datetime(2017, 1, 1)
    mock_api.return_value.getIssues.return_value = [mock_issue]
    self.assertTrue(issue_tracking_service.BugAlreadyExistsForLabel('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('label:test',), args)
    mock_api.reset_mock()

    mock_issue_1 = mock.MagicMock()
    mock_issue_1.open = True
    mock_issue_1.updated = datetime.datetime(2017, 1, 1)
    mock_issue_2 = mock.MagicMock()
    mock_issue_2.open = False
    mock_issue_2.updated = datetime.datetime(2017, 1, 1)
    mock_api.return_value.getIssues.return_value = [mock_issue_1, mock_issue_2]
    self.assertTrue(issue_tracking_service.BugAlreadyExistsForLabel('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('label:test',), args)
    mock_api.reset_mock()

    mock_issue_1 = mock.MagicMock()
    mock_issue_1.open = False
    mock_issue_1.updated = datetime.datetime(2017, 1, 2)
    mock_issue_2 = mock.MagicMock()
    mock_issue_2.open = False
    mock_issue_2.updated = datetime.datetime(2017, 1, 1)
    mock_api.return_value.getIssues.return_value = [mock_issue_1, mock_issue_2]
    self.assertFalse(issue_tracking_service.BugAlreadyExistsForLabel('test'))
    self.assertTrue(mock_api.return_value.getIssues.called)
    args, _ = mock_api.return_value.getIssues.call_args
    self.assertEqual(('label:test',), args)
    mock_api.reset_mock()

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2017, 1, 3))
  @mock.patch('services.flake_failure.issue_tracking_service.IssueTrackerAPI')
  def testCreateBugForTest(self, mock_api, _):
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForTest(None, None, None)
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForTest('test', None, None)
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForTest(None, 'subject', None)
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForTest(None, None, 'body')

    def set_id(issue):
      issue.id = 1

    mock_api.return_value.create.side_effect = set_id
    bug_id = issue_tracking_service.CreateBugForTest('test', 'subject', 'body')
    self.assertTrue(mock_api.return_value.create.called)
    self.assertEqual(1, bug_id)
    mock_api.reset_mock()

  def testTraverseMergedIssuesWithoutMergeInto(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({'id': 123})
    issue_tracker.getIssue.return_value = expected_issue

    issue = issue_tracking_service.TraverseMergedIssues(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls([mock.call.getIssue(123)])

  def testTraverseMergedIssuesWithMergeInto(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({'id': 345})
    issue_tracker.getIssue.side_effect = [
        Issue({
            'id': 123,
            'mergedInto': {
                'issueId': 234
            }
        }),
        Issue({
            'id': 234,
            'mergedInto': {
                'issueId': 345
            }
        }),
        expected_issue,
    ]

    issue = issue_tracking_service.TraverseMergedIssues(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls([
        mock.call.getIssue(123),
        mock.call.getIssue(234),
        mock.call.getIssue(345)
    ])

  def testTraverseMergedIssuesWithMergeInACircle(self):
    issue_tracker = mock.Mock()
    expected_issue = Issue({'id': 123})
    issue_tracker.getIssue.side_effect = [
        Issue({
            'id': 123,
            'mergedInto': {
                'issueId': 234
            }
        }),
        Issue({
            'id': 234,
            'mergedInto': {
                'issueId': 123
            }
        }),
        expected_issue,
    ]

    issue = issue_tracking_service.TraverseMergedIssues(123, issue_tracker)
    self.assertEqual(expected_issue, issue)
    issue_tracker.assert_has_calls([
        mock.call.getIssue(123),
        mock.call.getIssue(234),
        mock.call.getIssue(123)
    ])

  def testHasPreviousAttempt(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.has_attempted_filing = True
    analysis.Save()
    self.assertTrue(issue_tracking_service._HasPreviousAttempt(analysis))

    analysis.has_attempted_filing = False
    analysis.put()
    self.assertFalse(issue_tracking_service._HasPreviousAttempt(analysis))

  def testHasSufficientConfidenceInCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)

    analysis.confidence_in_culprit = None
    analysis.Save()
    self.assertFalse(
        issue_tracking_service._HasSufficientConfidenceInCulprit(analysis))

    analysis.confidence_in_culprit = 1.0
    analysis.Save()
    self.assertTrue(
        issue_tracking_service._HasSufficientConfidenceInCulprit(analysis))

    analysis.confidence_in_culprit = .9
    analysis.put()
    self.assertFalse(
        issue_tracking_service._HasSufficientConfidenceInCulprit(analysis))
