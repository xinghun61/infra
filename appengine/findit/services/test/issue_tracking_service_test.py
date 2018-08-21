# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import mock
import textwrap

from libs import time_util
from monorail_api import Issue
from services import issue_tracking_service
from waterfall.test import wf_testcase


class IssueTrackingServiceTest(wf_testcase.WaterfallTestCase):

  def testAddFinditLabelToIssue(self):
    issue = mock.MagicMock()
    issue.labels = []
    issue_tracking_service.AddFinditLabelToIssue(issue)
    self.assertEqual(['Test-Findit-Analyzed'], issue.labels)
    issue_tracking_service.AddFinditLabelToIssue(issue)
    self.assertEqual(['Test-Findit-Analyzed'], issue.labels)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2017, 1, 3))
  @mock.patch('services.issue_tracking_service.IssueTrackerAPI')
  def testOpenBugAlreadyExistsForId(self, mock_api, _):
    mock_api.return_value.getIssue.return_value = None
    self.assertFalse(issue_tracking_service.OpenBugAlreadyExistsForId(None))
    self.assertFalse(mock_api.return_value.getIssue.called)
    mock_api.reset_mock()

    mock_api.return_value.getIssue.return_value = None
    self.assertFalse(issue_tracking_service.OpenBugAlreadyExistsForId(1234))
    self.assertTrue(mock_api.return_value.getIssue.called)
    args, _ = mock_api.return_value.getIssue.call_args
    self.assertEqual((1234,), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = True
    mock_issue.updated = datetime.datetime(2017, 1, 1)
    mock_issue.merged_into = None
    mock_api.return_value.getIssue.return_value = mock_issue
    self.assertTrue(issue_tracking_service.OpenBugAlreadyExistsForId(1234))
    self.assertTrue(mock_api.return_value.getIssue.called)
    args, _ = mock_api.return_value.getIssue.call_args
    self.assertEqual((1234,), args)
    mock_api.reset_mock()

    mock_issue = mock.MagicMock()
    mock_issue.open = False
    mock_issue.updated = datetime.datetime(2017, 1, 2)
    mock_issue.merged_into = None
    mock_api.return_value.getIssue.return_value = mock_issue
    self.assertFalse(issue_tracking_service.OpenBugAlreadyExistsForId(1234))
    self.assertTrue(mock_api.return_value.getIssue.called)
    args, _ = mock_api.return_value.getIssue.call_args
    self.assertEqual((1234,), args)
    mock_api.reset_mock()

  @mock.patch('services.issue_tracking_service.IssueTrackerAPI')
  def testCreateBug(self, mock_api):
    summary = 'test summary'
    description = 'test description'
    project_id = 'proj'
    issue = Issue({
        'status': 'Available',
        'summary': summary,
        'description': description,
        'projectId': 'chromium',
        'state': 'open',
    })

    issue_tracking_service.CreateBug(issue, project_id=project_id)
    mock_api.assert_has_calls(mock.call(project_id, use_staging=False))
    mock_api.return_value.create.assert_has_calls(mock.call(issue))

  @mock.patch('services.issue_tracking_service.IssueTrackerAPI')
  def testUpdateBug(self, mock_api):
    summary = 'test summary'
    description = 'test description'
    project_id = 'proj'
    comment = 'test comment'
    issue = Issue({
        'status': 'Available',
        'summary': summary,
        'description': description,
        'projectId': 'chromium',
        'state': 'open',
    })

    issue_tracking_service.UpdateBug(issue, comment, project_id=project_id)
    mock_api.assert_has_calls(mock.call(project_id, use_staging=False))
    mock_api.return_value.update.assert_has_calls(
        mock.call(issue, comment, send_email=True))

  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testCreateBugForFlakeAnalyzer(self, mock_create_bug_fn):
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForFlakeAnalyzer(None, None, None)
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForFlakeAnalyzer('test', None, None)
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForFlakeAnalyzer(None, 'subject', None)
    with self.assertRaises(AssertionError):
      issue_tracking_service.CreateBugForFlakeAnalyzer(None, None, 'body')

    issue_tracking_service.CreateBugForFlakeAnalyzer('test', 'subject', 'body')
    self.assertTrue(mock_create_bug_fn.called)

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

  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testCreateBugForFlakeDetection(self, mock_create_bug_fn):

    def assign_issue_id(issue, _):
      issue.id = 12345
      return issue.id

    mock_create_bug_fn.side_effect = assign_issue_id

    normalized_step_name = 'target'
    normalized_test_name = 'suite.test'
    num_occurrences = 5
    monorail_project = 'chromium'
    flake_url = 'https://findit-for-me-staging.com/flake/detection/show-flake?key=1212'  # pylint: disable=line-too-long
    previous_tracking_bug_id = None

    issue_id = issue_tracking_service.CreateBugForFlakeDetection(
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        num_occurrences=num_occurrences,
        monorail_project=monorail_project,
        flake_url=flake_url,
        previous_tracking_bug_id=previous_tracking_bug_id)
    mock_create_bug_fn.assert_called_once()
    self.assertEqual(12345, issue_id)

    expected_status = 'Untriaged'
    expected_summary = 'suite.test is flaky'

    expected_description = textwrap.dedent("""
target: suite.test is flaky.

Findit detected 5 flake occurrences of this test within the past
24 hours. List of all flake occurrences can be found at:
https://findit-for-me-staging.com/flake/detection/show-flake?key=1212.

Flaky tests should be disabled within 30 minutes unless culprit CL is found and
reverted, please disable it first and then find an appropriate owner.

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N). If this
result was incorrect, please apply the label Test-Findit-Wrong and mark the bug
as untriaged.""")

    expected_labels = [
        'Test-Findit-Detected', 'Sheriff-Chromium', 'Pri-1', 'Type-Bug',
        'Test-Flaky'
    ]

    issue = mock_create_bug_fn.call_args_list[0][0][0]
    self.assertEqual(expected_status, issue.status)
    self.assertEqual(expected_summary, issue.summary)
    self.assertEqual(expected_description, issue.description)
    self.assertEqual(expected_labels, issue.labels)
    self.assertEqual(1, len(issue.field_values))
    self.assertEqual('Flaky-Test', issue.field_values[0].to_dict()['fieldName'])
    self.assertEqual('suite.test',
                     issue.field_values[0].to_dict()['fieldValue'])

  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testCreateBugForFlakeDetectionWithPreviousBugId(self, mock_create_bug_fn):
    normalized_step_name = 'target'
    normalized_test_name = 'suite.test'
    num_occurrences = 5
    monorail_project = 'chromium'
    previous_tracking_bug_id = 56789
    flake_url = 'https://findit-for-me-staging.com/flake/detection/show-flake?key=1212'  # pylint: disable=line-too-long

    issue_tracking_service.CreateBugForFlakeDetection(
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        num_occurrences=num_occurrences,
        monorail_project=monorail_project,
        flake_url=flake_url,
        previous_tracking_bug_id=previous_tracking_bug_id)

    expected_previous_bug_description = (
        '\n\nThis flaky test was previously tracked in bug 56789.\n\n')
    issue = mock_create_bug_fn.call_args_list[0][0][0]
    self.assertIn(expected_previous_bug_description, issue.description)

  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  def testUpdateBugForFlakeDetection(self, mock_update_bug_fn,
                                     mock_get_bug_for_id):
    normalized_test_name = 'suite.test'
    num_occurrences = 5
    monorail_project = 'chromium'
    flake_url = 'https://findit-for-me-staging.com/flake/detection/show-flake?key=1212'  # pylint: disable=line-too-long
    issue_id = 12345
    issue = Issue({
        'status': 'Available',
        'summary': 'summary',
        'description': 'description',
        'projectId': monorail_project,
        'labels': [],
        'fieldValues': [],
        'state': 'open',
    })

    mock_get_bug_for_id.return_value = issue
    issue_tracking_service.UpdateBugForFlakeDetection(
        bug_id=issue_id,
        normalized_test_name=normalized_test_name,
        num_occurrences=num_occurrences,
        monorail_project=monorail_project,
        flake_url=flake_url)

    expected_labels = ['Test-Findit-Detected', 'Sheriff-Chromium', 'Test-Flaky']
    issue = mock_update_bug_fn.call_args_list[0][0][0]
    self.assertEqual(expected_labels, issue.labels)
    self.assertEqual(1, len(issue.field_values))
    self.assertEqual('Flaky-Test', issue.field_values[0].to_dict()['fieldName'])
    self.assertEqual('suite.test',
                     issue.field_values[0].to_dict()['fieldValue'])

    expected_comment = textwrap.dedent("""
Findit detected 5 new flake occurrences of this test. To see the
list of flake occurrences, please visit:
https://findit-for-me-staging.com/flake/detection/show-flake?key=1212.

Since flakiness is ongoing, the issue was moved back into the Sheriff Bug Queue
(unless already there).

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N).
Feedback is welcome! Please use component Tools>Test>FindIt>Flakiness.""")

    comment = mock_update_bug_fn.call_args_list[0][0][1]
    self.assertEqual(expected_comment, comment)

  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  def testUpdateBugForFlakeDetectionWithPreviousBugId(self, mock_update_bug_fn,
                                                      mock_get_bug_for_id):
    normalized_test_name = 'suite.test'
    num_occurrences = 5
    monorail_project = 'chromium'
    flake_url = 'https://findit-for-me-staging.com/flake/detection/show-flake?key=1212'  # pylint: disable=line-too-long
    issue_id = 12345
    previous_tracking_bug_id = 56789
    issue = Issue({
        'status': 'Available',
        'summary': 'summary',
        'description': 'description',
        'projectId': monorail_project,
        'labels': [],
        'fieldValues': [],
        'state': 'open',
    })

    mock_get_bug_for_id.return_value = issue
    issue_tracking_service.UpdateBugForFlakeDetection(
        bug_id=issue_id,
        normalized_test_name=normalized_test_name,
        num_occurrences=num_occurrences,
        monorail_project=monorail_project,
        flake_url=flake_url,
        previous_tracking_bug_id=previous_tracking_bug_id)

    expected_previous_bug_description = (
        '\n\nThis flaky test was previously tracked in bug 56789.\n\n')
    comment = mock_update_bug_fn.call_args_list[0][0][1]
    self.assertIn(expected_previous_bug_description, comment)

  # This test tests that an open issue related to flaky tests will NOT be found
  # if it ONLY has the test name inside the summary.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(issue_tracking_service, '_GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryNotFound(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test'
    issue.labels = []
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        None,
        issue_tracking_service.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and the 'Test-Flaky' label.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(issue_tracking_service, '_GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithFlakeLabel(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test'
    issue.labels = ['Test-Flaky']
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, issue_tracking_service.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and the 'Tests>Flaky' component.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(issue_tracking_service, '_GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithFlakeComponent(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test'
    issue.labels = []
    issue.components = ['Tests>Flaky']
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, issue_tracking_service.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and any of the flake keywords.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(issue_tracking_service, '_GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithKeywordFlake(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test is a flake'
    issue.labels = []
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, issue_tracking_service.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and any of the flake keywords.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(issue_tracking_service, '_GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithKeywordFlaky(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test is flaky'
    issue.labels = []
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, issue_tracking_service.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and any of the flake keywords.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(issue_tracking_service, '_GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithKeywordFlakiness(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test is causing flakiness'
    issue.labels = []
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, issue_tracking_service.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the Flaky-Test customized field.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestBySummary',
      return_value=None)
  @mock.patch.object(issue_tracking_service, '_GetOpenIssues')
  def testSearchOpenIssueFlakyTestInCustomizedField(
      self, mock_get_open_issues, mock_get_issue_id_by_summary):
    issue = mock.Mock()
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, issue_tracking_service.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with(
        'Flaky-Test=suite.test is:open', 'chromium')
    mock_get_issue_id_by_summary.assert_called_once_with(
        'suite.test', 'chromium')

  # This test tests that the util first searches for open bugs by summary on
  # Monorail and if it is found, then skip searching for customized field.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestBySummary',
      return_value=12345)
  def testSearchAndFoundOpenIssueBySummary(
      self, mock_get_issue_id_by_summary,
      mock_get_issue_id_by_customized_field):
    self.assertEqual(
        12345,
        issue_tracking_service.SearchOpenIssueIdForFlakyTest(
            'suite.test', 'chromium'))
    mock_get_issue_id_by_summary.assert_called_once_with(
        'suite.test', 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that the util first searches for open bugs on Monorail and
  # if it is not found, then searches for customized field.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=12345)
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestBySummary',
      return_value=None)
  def testSearchAndFoundOpenIssueByCustomizedField(
      self, mock_get_issue_id_by_summary,
      mock_get_issue_id_by_customized_field):
    self.assertEqual(
        12345,
        issue_tracking_service.SearchOpenIssueIdForFlakyTest(
            'suite.test', 'chromium'))
    mock_get_issue_id_by_summary.assert_called_once_with(
        'suite.test', 'chromium')
    mock_get_issue_id_by_customized_field.assert_called_once_with(
        'suite.test', 'chromium')

  # This test tests that the util first searches for open bugs on Monorail and
  # if it is not found, then searches for customized field, and if still not
  # found, returns None.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestBySummary',
      return_value=None)
  def testSearchAndNotFoundOpenIssue(self, mock_get_issue_id_by_summary,
                                     mock_get_issue_id_by_customized_field):
    self.assertEqual(
        None,
        issue_tracking_service.SearchOpenIssueIdForFlakyTest(
            'suite.test', 'chromium'))
    mock_get_issue_id_by_summary.assert_called_once_with(
        'suite.test', 'chromium')
    mock_get_issue_id_by_customized_field.assert_called_once_with(
        'suite.test', 'chromium')

  # This test tests that when there are multiple issues related to the flaky
  # test, returns the id of the issue that was filed earliest.
  @mock.patch.object(issue_tracking_service, '_GetOpenIssues')
  def testGetExistingOpenBugIdForTestReturnsEarliestBug(self,
                                                        mock_get_open_issues):
    issue1 = mock.Mock()
    issue1.id = 456
    issue1.summary = 'suite.test is flaky'
    issue1.labels = []
    issue1.components = []

    issue2 = mock.Mock()
    issue2.id = 123
    issue2.summary = 'suite.test is flaky'
    issue2.labels = []
    issue2.components = []

    mock_get_open_issues.return_value = [issue1, issue2]
    self.assertEqual(
        123,
        issue_tracking_service.SearchOpenIssueIdForFlakyTest(
            'suite.test', 'chromium'))
