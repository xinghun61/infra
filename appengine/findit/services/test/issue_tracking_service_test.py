# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import mock
import textwrap

from libs import time_util
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from monorail_api import Issue
from monorail_api import IssueTrackerAPI
from services import issue_tracking_service
from waterfall.test import wf_testcase


class TestIssueGenerator(issue_tracking_service.FlakyTestIssueGenerator):
  """A FlakyTestIssueGenerator used for testing."""

  def __init__(self, step_name='step', test_name='test'):
    super(TestIssueGenerator, self).__init__()
    self.step_name = step_name
    self.test_name = test_name
    #self._previous_tracking_bug_id = None

  def GetStepName(self):
    return self.step_name

  def GetTestName(self):
    return self.test_name

  def GetDescription(self):
    previous_tracking_bug_id = self.GetPreviousTrackingBugId()
    if previous_tracking_bug_id:
      return ('description with previous tracking bug id: %s.' %
              previous_tracking_bug_id)

    return 'description without previous tracking bug id.'

  def GetComment(self):
    previous_tracking_bug_id = self.GetPreviousTrackingBugId()
    if previous_tracking_bug_id:
      return ('comment with previous tracking bug id: %s.' %
              previous_tracking_bug_id)

    return 'comment without previous tracking bug id.'

  def ShouldRestoreChromiumSheriffLabel(self):
    # Sets to False as default value, if need to test this control flow, please
    # mock this method.
    return False

  def GetLabels(self):
    return ['label1', 'Sheriff-Chromium']


class IssueTrackingServiceTest(wf_testcase.WaterfallTestCase):

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

  @mock.patch.object(IssueTrackerAPI, 'getIssue')
  def testGetMergedDestinationIssueWithoutMergeInto(self, mock_get_issue):
    issue = Issue({'id': 12345})
    mock_get_issue.return_value = issue
    self.assertEqual(
        issue, issue_tracking_service.GetMergedDestinationIssueForId(12345))

  @mock.patch.object(IssueTrackerAPI, 'getIssue')
  def testGetMergedDestinationIssueWithMergeInto(self, mock_get_issue):
    issue = Issue({'id': 12345, 'mergedInto': {'issueId': 56789}})

    another_issue = Issue({'id': 56789})

    def _return_issue(issue_id):
      if issue_id == 12345:
        return issue

      if issue_id == 56789:
        return another_issue

      return None

    mock_get_issue.side_effect = _return_issue
    self.assertEqual(
        another_issue,
        issue_tracking_service.GetMergedDestinationIssueForId(12345))

  @mock.patch.object(IssueTrackerAPI, 'getIssue')
  def testGetMergedDestinationIssueWithMergeInCircle(self, mock_get_issue):
    issue = Issue({'id': 12345, 'mergedInto': {'issueId': 56789}})

    another_issue = Issue({'id': 56789, 'mergedInto': {'issueId': 12345}})

    def _return_issue(issue_id):
      if issue_id == 12345:
        return issue

      if issue_id == 56789:
        return another_issue

      return None

    mock_get_issue.side_effect = _return_issue
    self.assertEqual(
        issue, issue_tracking_service.GetMergedDestinationIssueForId(12345))

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

  # This test tests that an open issue related to flaky tests will not be found
  # if has the Test-FIndit-Wrong label.
  @mock.patch.object(
      issue_tracking_service,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(issue_tracking_service, '_GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithTestFinditWrongLabel(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test is causing flakiness'
    issue.labels = ['Test-Findit-Wrong']
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

  # This test tests that creating issue via issue generator without previous
  # tracking bug id works properly.
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'CreateBug', return_value=12345)
  def testCreateIssueWithIssueGenerator(self, mock_create_bug_fn,
                                        mock_update_bug_fn):
    test_issue_generator = TestIssueGenerator()
    issue_id = issue_tracking_service.CreateIssueWithIssueGenerator(
        issue_generator=test_issue_generator)

    self.assertTrue(mock_create_bug_fn.called)
    self.assertFalse(mock_update_bug_fn.called)
    self.assertEqual(12345, issue_id)
    issue = mock_create_bug_fn.call_args_list[0][0][0]
    self.assertEqual('Untriaged', issue.status)
    self.assertEqual('test is flaky', issue.summary)
    self.assertEqual('description without previous tracking bug id.',
                     issue.description)
    self.assertEqual(['label1', 'Sheriff-Chromium', 'Pri-1'], issue.labels)
    self.assertEqual(1, len(issue.field_values))
    self.assertEqual('Flaky-Test', issue.field_values[0].to_dict()['fieldName'])
    self.assertEqual('test', issue.field_values[0].to_dict()['fieldValue'])

  # This test tests that creating issue via issue generator with previous
  # tracking bug id works properly.
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'CreateBug', return_value=12345)
  def testCreateIssueWithIssueGeneratorWithPreviousTrackingBugId(
      self, mock_create_bug_fn, mock_update_bug_fn):
    test_issue_generator = TestIssueGenerator()
    test_issue_generator.SetPreviousTrackingBugId(56789)
    issue_id = issue_tracking_service.CreateIssueWithIssueGenerator(
        issue_generator=test_issue_generator)

    self.assertTrue(mock_create_bug_fn.called)
    self.assertFalse(mock_update_bug_fn.called)
    self.assertEqual(12345, issue_id)
    issue = mock_create_bug_fn.call_args_list[0][0][0]
    self.assertEqual('Untriaged', issue.status)
    self.assertEqual('test is flaky', issue.summary)
    self.assertEqual('description with previous tracking bug id: 56789.',
                     issue.description)
    self.assertEqual(['label1', 'Sheriff-Chromium', 'Pri-1'], issue.labels)
    self.assertEqual(1, len(issue.field_values))
    self.assertEqual('Flaky-Test', issue.field_values[0].to_dict()['fieldName'])
    self.assertEqual('test', issue.field_values[0].to_dict()['fieldValue'])

  # This test tests that updating issue via issue generator without previous
  # tracking bug id works properly.
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testUpdateIssueWithIssueGenerator(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_merged_issue):
    issue_id = 12345
    issue = Issue({
        'status': 'Available',
        'summary': 'summary',
        'description': 'description',
        'projectId': 'chromium',
        'labels': [],
        'fieldValues': [],
        'state': 'open',
    })
    mock_get_merged_issue.return_value = issue

    test_issue_generator = TestIssueGenerator()
    issue_tracking_service.UpdateIssueWithIssueGenerator(
        issue_id=issue_id, issue_generator=test_issue_generator)

    self.assertFalse(mock_create_bug_fn.called)
    mock_update_bug_fn.assert_called_once_with(
        issue, 'comment without previous tracking bug id.', 'chromium')
    issue = mock_update_bug_fn.call_args_list[0][0][0]
    self.assertEqual(['label1'], issue.labels)
    self.assertEqual(1, len(issue.field_values))
    self.assertEqual('Flaky-Test', issue.field_values[0].to_dict()['fieldName'])
    self.assertEqual('test', issue.field_values[0].to_dict()['fieldValue'])

  # This test tests that updating issue via issue generator works properly if
  # the switch to turn on to restore Chromium Sheriffs label when udpate bugs.
  @mock.patch.object(
      TestIssueGenerator,
      'ShouldRestoreChromiumSheriffLabel',
      return_value=True)
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testUpdateIssueWithIssueGeneratorAndRestoreSheriffLabel(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_merged_issue, _):
    issue_id = 12345
    issue = Issue({
        'status': 'Available',
        'summary': 'summary',
        'description': 'description',
        'projectId': 'chromium',
        'labels': [],
        'fieldValues': [],
        'state': 'open',
    })
    mock_get_merged_issue.return_value = issue

    test_issue_generator = TestIssueGenerator()
    issue_tracking_service.UpdateIssueWithIssueGenerator(
        issue_id=issue_id, issue_generator=test_issue_generator)

    self.assertFalse(mock_create_bug_fn.called)
    self.assertTrue(mock_update_bug_fn.called)
    self.assertEqual(['label1', 'Sheriff-Chromium'], issue.labels)

  # This test tests that updating issue via issue generator with previous
  # tracking id works properly.
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testUpdateIssueWithIssueGeneratorWithPreviousTrackingId(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_merged_issue):
    issue_id = 12345
    issue = Issue({
        'status': 'Available',
        'summary': 'summary',
        'description': 'description',
        'projectId': 'chromium',
        'labels': [],
        'fieldValues': [],
        'state': 'open',
    })
    mock_get_merged_issue.return_value = issue

    test_issue_generator = TestIssueGenerator()
    test_issue_generator.SetPreviousTrackingBugId(56789)
    issue_tracking_service.UpdateIssueWithIssueGenerator(
        issue_id=issue_id, issue_generator=test_issue_generator)

    self.assertFalse(mock_create_bug_fn.called)
    mock_update_bug_fn.assert_called_once_with(
        issue, 'comment with previous tracking bug id: 56789.', 'chromium')

  # This test tests that if a flake has a flake issue attached and the bug is
  # open (not merged) on Monorail, then should directly update that bug.
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(issue_tracking_service, 'CreateIssueWithIssueGenerator')
  def testHasFlakeAndFlakeIssueAndBugIsOpen(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, mock_get_merged_issue):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='test')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = True

    test_issue_generator = TestIssueGenerator()
    issue_tracking_service.CreateOrUpdateIssue(test_issue_generator)

    self.assertFalse(mock_create_with_issue_generator_fn.called)
    mock_update_with_issue_generator_fn.assert_called_once_with(
        issue_id=12345, issue_generator=test_issue_generator)
    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(12345, fetched_flake_issues[0].issue_id)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that if a flake has a flake issue attached and the bug is
  # closed (not merged) on Monorail, then should create a new one if an existing
  # open bug is not found on Monorail.
  @mock.patch.object(
      issue_tracking_service,
      'SearchOpenIssueIdForFlakyTest',
      return_value=None)
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(
      issue_tracking_service,
      'CreateIssueWithIssueGenerator',
      return_value=66666)
  def testHasFlakeAndFlakeIssueAndBugIsClosed(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, mock_get_merged_issue, _):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='test')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = False

    test_issue_generator = TestIssueGenerator()
    issue_tracking_service.CreateOrUpdateIssue(test_issue_generator)

    mock_create_with_issue_generator_fn.assert_called_once_with(
        issue_generator=test_issue_generator)
    self.assertFalse(mock_update_with_issue_generator_fn.called)
    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(66666, fetched_flake_issues[0].issue_id)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that if a flake has a flake issue attached and the bug was
  # merged to another bug on Monorail, and that destination bug is open, then
  # should update the destination bug.
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(issue_tracking_service, 'CreateIssueWithIssueGenerator')
  def testHasFlakeAndFlakeIssueAndBugWasMergedToAnOpenBug(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, mock_get_merged_issue):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='test')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_get_merged_issue.return_value.id = 45678
    mock_get_merged_issue.return_value.open = True

    test_issue_generator = TestIssueGenerator()
    issue_tracking_service.CreateOrUpdateIssue(test_issue_generator)

    self.assertFalse(mock_create_with_issue_generator_fn.called)
    mock_update_with_issue_generator_fn.assert_called_once_with(
        issue_id=45678, issue_generator=test_issue_generator)
    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(45678, fetched_flake_issues[0].issue_id)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that if a flake has a flake issue attached and the bug was
  # merged to another bug on Monorail, but that destination bug was closed, then
  # should create a new one if an existing open bug is not found on Monorail.
  @mock.patch.object(
      issue_tracking_service,
      'SearchOpenIssueIdForFlakyTest',
      return_value=None)
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(
      issue_tracking_service,
      'CreateIssueWithIssueGenerator',
      return_value=66666)
  def testHasFlakeAndFlakeIssueAndBugWasMergedToAClosedBug(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, mock_get_merged_issue, _):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='test')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_get_merged_issue.return_value.id = 56789
    mock_get_merged_issue.return_value.open = False

    test_issue_generator = TestIssueGenerator()
    issue_tracking_service.CreateOrUpdateIssue(test_issue_generator)

    mock_create_with_issue_generator_fn.assert_called_once_with(
        issue_generator=test_issue_generator)
    self.assertFalse(mock_update_with_issue_generator_fn.called)
    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(66666, fetched_flake_issues[0].issue_id)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that if there is no existing flake for a test, and couldn't
  # find an existing issue about this flaky test on Monorail, then should create
  # a new flake and a new issue and attach the issue to the flake.
  @mock.patch.object(
      issue_tracking_service,
      'SearchOpenIssueIdForFlakyTest',
      return_value=None)
  @mock.patch.object(issue_tracking_service, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(
      issue_tracking_service,
      'CreateIssueWithIssueGenerator',
      return_value=66666)
  def testHasNoFlakeAndNoExistingOpenIssue(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, _):
    step_name = 'step_1'
    test_name = 'test_1'
    test_issue_generator = TestIssueGenerator(
        step_name=step_name, test_name=test_name)
    issue_tracking_service.CreateOrUpdateIssue(test_issue_generator)

    mock_create_with_issue_generator_fn.assert_called_once_with(
        issue_generator=test_issue_generator)
    self.assertFalse(mock_update_with_issue_generator_fn.called)
    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(step_name, fetched_flakes[0].normalized_step_name)
    self.assertEqual(test_name, fetched_flakes[0].normalized_test_name)
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(66666, fetched_flake_issues[0].issue_id)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that if there is a flake for a test, but no flake issue
  # attached and couldn't find an existing issue about this flaky test on
  # Monorail, then should create a new issue and attach the issue to the flake.
  @mock.patch.object(
      issue_tracking_service,
      'SearchOpenIssueIdForFlakyTest',
      return_value=None)
  @mock.patch.object(issue_tracking_service, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(
      issue_tracking_service,
      'CreateIssueWithIssueGenerator',
      return_value=66666)
  def testHasFlakeButNoFlakeIssueAndNoExistingOpenIssue(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, _):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='test')
    flake.put()
    test_issue_generator = TestIssueGenerator()
    issue_tracking_service.CreateOrUpdateIssue(test_issue_generator)

    mock_create_with_issue_generator_fn.assert_called_once_with(
        issue_generator=test_issue_generator)
    self.assertFalse(mock_update_with_issue_generator_fn.called)
    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual('step', fetched_flakes[0].normalized_step_name)
    self.assertEqual('test', fetched_flakes[0].normalized_test_name)
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(66666, fetched_flake_issues[0].issue_id)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that if there is no flake for a test, and found an existing
  # issue about this flaky test on Monorail, then should create a new flake,
  # update the issue and attach the issue to the flake.
  @mock.patch.object(
      issue_tracking_service,
      'SearchOpenIssueIdForFlakyTest',
      return_value=99999)
  @mock.patch.object(issue_tracking_service, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(issue_tracking_service, 'CreateIssueWithIssueGenerator')
  def testHasNoFlakeAndFoundAnExistingOpenIssue(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, _):
    step_name = 'step_2'
    test_name = 'test_2'
    test_issue_generator = TestIssueGenerator(
        step_name=step_name, test_name=test_name)
    issue_tracking_service.CreateOrUpdateIssue(test_issue_generator)

    self.assertFalse(mock_create_with_issue_generator_fn.called)
    mock_update_with_issue_generator_fn.assert_called_once_with(
        issue_id=99999, issue_generator=test_issue_generator)
    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(step_name, fetched_flakes[0].normalized_step_name)
    self.assertEqual(test_name, fetched_flakes[0].normalized_test_name)
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(99999, fetched_flake_issues[0].issue_id)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that if a flake has a flake issue attached and the bug is
  # closed (not merged) on Monorail, but found an existing open issue on
  # Monorail, then should update the issue and attach it to the flake.
  @mock.patch.object(
      issue_tracking_service,
      'SearchOpenIssueIdForFlakyTest',
      return_value=99999)
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(issue_tracking_service, 'CreateIssueWithIssueGenerator')
  def testHasFlakeAndFlakeAndBugIsClosedButFoundAnExistingOpenIssue(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, mock_get_merged_issue, _):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='test')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = False

    test_issue_generator = TestIssueGenerator()
    issue_tracking_service.CreateOrUpdateIssue(test_issue_generator)

    self.assertFalse(mock_create_with_issue_generator_fn.called)
    mock_update_with_issue_generator_fn.assert_called_once_with(
        issue_id=99999, issue_generator=test_issue_generator)
    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual('step', fetched_flakes[0].normalized_step_name)
    self.assertEqual('test', fetched_flakes[0].normalized_test_name)
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(99999, fetched_flake_issues[0].issue_id)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)
