# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import mock
import textwrap

from googleapiclient.errors import HttpError
from libs import time_util
from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FlakeType
from services import flake_issue_util
from services import monorail_util
from services.issue_generator import FlakeAnalysisIssueGenerator
from services.issue_generator import FlakyTestIssueGenerator
from waterfall.test.wf_testcase import WaterfallTestCase


class TestIssueGenerator(FlakyTestIssueGenerator):
  """A FlakyTestIssueGenerator used for testing."""

  def __init__(self,
               step_name='step',
               test_name='suite.test',
               test_label_name='*/suite.test/*'):
    super(TestIssueGenerator, self).__init__()
    self.step_name = step_name
    self.test_name = test_name
    self.test_label_name = test_label_name
    #self._previous_tracking_bug_id = None

  def GetStepName(self):
    return self.step_name

  def GetTestName(self):
    return self.test_name

  def GetTestLabelName(self):
    return self.test_label_name

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


class FlakeReportUtilTest(WaterfallTestCase):

  def _CreateFlake(self,
                   normalized_step_name,
                   normalized_test_name,
                   test_label_name,
                   test_suite_name=None):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)
    if test_suite_name:
      flake.tags.append('suite::%s' % test_suite_name)
    flake.put()
    return flake

  def _CreateFlakeOccurrence(self, build_id, step_ui_name, test_name,
                             gerrit_cl_id, parent_flake_key):
    flake_occurrence = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
        build_id=build_id,
        step_ui_name=step_ui_name,
        test_name=test_name,
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=parent_flake_key,
        luci_project='chromium',
        luci_bucket='try',
        luci_builder='linux_chromium_rel_ng',
        legacy_master_name='tryserver.chromium.linux',
        legacy_build_number=999,
        time_happened=datetime.datetime.utcnow())
    flake_occurrence.put()
    return flake_occurrence

  def _GetDatetimeHoursAgo(self, hours):
    """Returns the utc datetime of some hours ago."""
    return time_util.GetUTCNow() - datetime.timedelta(hours=hours)

  def setUp(self):
    super(FlakeReportUtilTest, self).setUp()
    self.UpdateUnitTestConfigSettings('flake_detection_settings',
                                      {'report_flakes_to_flake_analyzer': True})
    patcher = mock.patch.object(
        time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 2))
    self.addCleanup(patcher.stop)
    patcher.start()

    self.flake = self._CreateFlake('step', 'test', 'test_label')
    self._CreateFlakeOccurrence(111, 'step1', 'test1', 98765, self.flake.key)
    self._CreateFlakeOccurrence(222, 'step2', 'test2', 98764, self.flake.key)
    self._CreateFlakeOccurrence(333, 'step3', 'test3', 98763, self.flake.key)

  # This test tests that getting flakes with enough occurrences works properly.
  def testGetFlakesWithEnoughOccurrences(self):
    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    self.assertEqual(1, len(flakes_with_occurrences))
    self.assertEqual(3, len(flakes_with_occurrences[0][1]))
    self.assertIsNone(flakes_with_occurrences[0][2])

  # This test tests that in order for a flake to have enough occurrences, there
  # needs to be at least 3 (_MIN_REQUIRED_FALSELY_REJECTED_CLS_24H) occurrences
  # with different CLs, and different patchsets of the same CL are only counted
  # once.
  def testMinimumRequiredFalselyRejectedCLs(self):
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    for occurrence in occurrences:
      occurrence.gerrit_cl_id = 565656
      occurrence.put()

    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    self.assertEqual(0, len(flakes_with_occurrences))

  # This test tests that occurrences happened more than one day ago are ignored.
  def testIgnoreOutdatedOccurrences(self):
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    occurrences[2].time_happened = self._GetDatetimeHoursAgo(25)
    occurrences[2].put()

    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    self.assertEqual(0, len(flakes_with_occurrences))

  # This test tests that if the number of issues created or updated within the
  # past 24 hours has already reached a limit, then no issues can be created or
  # updated.
  @mock.patch.object(flake_issue_util, 'CreateOrUpdateIssue')
  def testCreateOrUpdateIssuesPerDayLimit(self, mock_update_or_create_bug):
    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    self.assertEqual(1, len(flakes_with_occurrences))
    self.assertEqual(3, len(flakes_with_occurrences[0][1]))
    self.UpdateUnitTestConfigSettings('action_settings',
                                      {'max_flake_bug_updates_per_day': 0})
    flake_issue_util.ReportFlakesToMonorail(flakes_with_occurrences)
    self.assertFalse(mock_update_or_create_bug.called)

  # This test tests that flakes that were updated within 24h are ignored.
  def testIgnoreFlakesAlreadyUpdatedWith24h(self):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time_by_flake_detection = (
        self._GetDatetimeHoursAgo(5))
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    occurrences[2].time_detected = self._GetDatetimeHoursAgo(10)
    occurrences[2].put()

    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    self.assertEqual(0, len(flakes_with_occurrences))

  # This test tests that the program doesn't crash when a flake has no
  # unreported occurrences.
  def testFlakeHasNoUnreportedOccurrences(self):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time_by_flake_detection = (
        self._GetDatetimeHoursAgo(5))
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    for occurrence in occurrences:
      occurrence.time_detected = self._GetDatetimeHoursAgo(10)
      occurrence.put()

    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    self.assertEqual(0, len(flakes_with_occurrences))

  # This test tests a flake has some unreported occurrences.
  def testFlakeHasUnreportedOccurrences(self):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time_by_flake_detection = (
        self._GetDatetimeHoursAgo(30))
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    for occurrence in occurrences:
      occurrence.time_detected = self._GetDatetimeHoursAgo(10)
      occurrence.put()

    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    self.assertEqual(1, len(flakes_with_occurrences))
    self.assertEqual(flake_issue, flakes_with_occurrences[0][2])

  # This test tests that if the feature to create and update bugs is disabled,
  # flakes will NOT be reported to Monorail.
  @mock.patch.object(monorail_util, 'UpdateBug')
  @mock.patch.object(monorail_util, 'CreateBug')
  def testDisableCreateAndUpdateBugs(self, mock_create_bug_fn,
                                     mock_update_bug_fn):
    self.UpdateUnitTestConfigSettings('action_settings',
                                      {'max_flake_bug_updates_per_day': 0})

    flake = Flake.query().fetch()[0]
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    flake_issue_util.ReportFlakesToMonorail([(flake, occurrences)])
    self.assertFalse(mock_create_bug_fn.called)
    self.assertFalse(mock_update_bug_fn.called)

  # This test tests that when a flake has no flake issue attached, it creates
  # a new issue and attach it to the flake.
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=None)
  @mock.patch.object(monorail_util, 'UpdateBug')
  @mock.patch.object(monorail_util, 'CreateBug', return_value=66666)
  def testCreateIssue(self, mock_create_bug_fn, mock_update_bug_fn, _):
    flake = Flake.query().fetch()[0]
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    flake_issue_util.ReportFlakesToMonorail([(flake, occurrences)])

    expected_status = 'Untriaged'
    expected_summary = 'test_label is flaky'

    expected_wrong_result_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?status=Unconfirmed&'
        'labels=Pri-1,Test-Findit-Wrong&components=Tools%3ETest%3EFindit%3E'
        'Flakiness&summary=%5BFindit%5D%20Flake%20Detection%20-%20Wrong%20'
        'result%3A%20test&comment=Link%20to%20flake%20details%3A%20'
        'https://findit-for-me.appspot.com/flake/occurrences?key={}').format(
            flake.key.urlsafe())

    expected_description = textwrap.dedent("""
test_label is flaky.

Findit has detected 3 flake occurrences of this test within the
past 24 hours. List of all flake occurrences can be found at:
https://findit-for-me.appspot.com/flake/occurrences?key={}.

Unless the culprit CL is found and reverted, please disable this test first
within 30 minutes then find an appropriate owner.

If the result above is wrong, please file a bug using this link:
{}

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N)."""
                                          ).format(flake.key.urlsafe(),
                                                   expected_wrong_result_link)

    expected_labels = [
        'Sheriff-Chromium', 'Type-Bug', 'Test-Flaky', 'Test-Findit-Detected',
        'Pri-1'
    ]

    self.assertTrue(mock_create_bug_fn.called)
    self.assertFalse(mock_update_bug_fn.called)
    issue = mock_create_bug_fn.call_args_list[0][0][0]
    self.assertEqual(expected_status, issue.status)
    self.assertEqual(expected_summary, issue.summary)
    self.assertEqual(expected_description, issue.description)
    self.assertEqual(expected_labels, issue.labels)
    self.assertEqual(1, len(issue.field_values))
    self.assertEqual('Flaky-Test', issue.field_values[0].to_dict()['fieldName'])
    self.assertEqual('test', issue.field_values[0].to_dict()['fieldValue'])

    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(66666, fetched_flake_issues[0].issue_id)
    self.assertEqual(
        datetime.datetime(2018, 1, 2),
        fetched_flake_issues[0].last_updated_time_by_flake_detection)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that when a flake has a flake issue attached but the issue
  # was closed, it creates a new issue with a previous tracking issue id and
  # attach it to the flake.
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=None)
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  @mock.patch.object(monorail_util, 'UpdateBug')
  @mock.patch.object(monorail_util, 'CreateBug', return_value=66666)
  def testCreateIssueWithPreviousTrackingBugId(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_merged_issue, _):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = False

    flake_issue_util.ReportFlakesToMonorail([(flake, occurrences)])

    expected_previous_bug_description = (
        '\n\nThis flaky test was previously tracked in bug 12345.\n\n')
    issue = mock_create_bug_fn.call_args_list[0][0][0]
    self.assertIn(expected_previous_bug_description, issue.description)
    self.assertFalse(mock_update_bug_fn.called)

  # This test tests that when a flake has a flake issue attached and the issue
  # is still open, it directly updates the issue.
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  @mock.patch.object(monorail_util, 'UpdateBug')
  @mock.patch.object(monorail_util, 'CreateBug')
  def testUpdateIssue(self, mock_create_bug_fn, mock_update_bug_fn,
                      mock_get_merged_issue):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = True
    flake_issue_util.ReportFlakesToMonorail([(flake, occurrences)])

    expected_wrong_result_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?status=Unconfirmed&'
        'labels=Pri-1,Test-Findit-Wrong&components=Tools%3ETest%3EFindit%3E'
        'Flakiness&summary=%5BFindit%5D%20Flake%20Detection%20-%20Wrong%20'
        'result%3A%20test&comment=Link%20to%20flake%20details%3A%20'
        'https://findit-for-me.appspot.com/flake/occurrences?key={}').format(
            flake.key.urlsafe())

    sheriff_queue_message = (
        'Since these tests are still flaky, this issue has been moved back onto'
        ' the Sheriff Bug Queue if it hasn\'t already.')

    expected_comment = textwrap.dedent("""
test_label is flaky.

Findit has detected 3 new flake occurrences of this test. List
of all flake occurrences can be found at:
https://findit-for-me.appspot.com/flake/occurrences?key={}.

{}

If the result above is wrong, please file a bug using this link:
{}

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N)."""
                                      ).format(flake.key.urlsafe(),
                                               sheriff_queue_message,
                                               expected_wrong_result_link)

    self.assertFalse(mock_create_bug_fn.called)
    self.assertTrue(mock_update_bug_fn)
    comment = mock_update_bug_fn.call_args_list[0][0][1]
    self.assertEqual(expected_comment, comment)

    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(12345, fetched_flake_issues[0].issue_id)
    self.assertEqual(
        datetime.datetime(2018, 1, 2),
        fetched_flake_issues[0].last_updated_time_by_flake_detection)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that when a flake has a flake issue attached and the issue
  # was merged to another open bug, it updates the destination bug with
  # a previous tracking bug id.
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  @mock.patch.object(monorail_util, 'UpdateBug')
  @mock.patch.object(monorail_util, 'CreateBug')
  def testUpdateIssueWithPreviousTrackingBugId(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_merged_issue):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    mock_get_merged_issue.return_value.id = 56789
    mock_get_merged_issue.return_value.open = True
    flake_issue_util.ReportFlakesToMonorail([(flake, occurrences)])

    expected_previous_bug_description = (
        '\n\nThis flaky test was previously tracked in bug 12345.\n\n')
    comment = mock_update_bug_fn.call_args_list[0][0][1]
    self.assertIn(expected_previous_bug_description, comment)
    self.assertFalse(mock_create_bug_fn.called)
    self.assertTrue(mock_update_bug_fn.called)

  # This test tests that when Flake Detection tries to create or update multiple
  # bugs, if it encounters failures such as no permissions to update a specific
  # bug, it shouldn't crash, instead, it should move on to next ones.
  @mock.patch.object(monorail_util, 'IssueTrackerAPI')
  def testReportFlakeToMonorailRecoversFromFailures(self,
                                                    mock_issue_tracker_api):
    mock_issue_tracker_api.side_effect = HttpError(
        mock.Mock(status=403), 'Error happened')

    flake1 = Flake.query().fetch()[0]
    occurrences1 = FlakeOccurrence.query(ancestor=flake1.key).filter(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    flake2 = self._CreateFlake('step_other', 'test_other', 'test_label_other')
    self._CreateFlakeOccurrence(777, 'step1_other', 'test1_other', 54321,
                                flake2.key)
    self._CreateFlakeOccurrence(888, 'step2_other', 'test2_other', 54322,
                                flake2.key)
    self._CreateFlakeOccurrence(999, 'step3_other', 'test3_other', 54323,
                                flake2.key)
    occurrences2 = FlakeOccurrence.query(ancestor=flake2.key).filter(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()

    flake_issue_util.ReportFlakesToMonorail([(flake1, occurrences1),
                                             (flake2, occurrences2)])

  # This test tests that if the feature to report flakes to Flake Analyzer is
  # disabled, flakes will NOT be reported.
  @mock.patch.object(flake_issue_util, 'AnalyzeDetectedFlakeOccurrence')
  def testDisableReportFlakesToFlakeAnalyzer(self,
                                             mock_analyze_flake_occurrence):
    self.UpdateUnitTestConfigSettings(
        'flake_detection_settings', {'report_flakes_to_flake_analyzer': False})

    flake = Flake.query().fetch()[0]
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()
    flake_issue_util.ReportFlakesToFlakeAnalyzer([(flake, occurrences)])
    self.assertFalse(mock_analyze_flake_occurrence.called)

  @mock.patch.object(flake_issue_util, 'AnalyzeDetectedFlakeOccurrence')
  def testReportFlakesToFlakeAnalyzer(self, mock_analyze_flake_occurrence):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION).fetch()

    flake_issue_util.ReportFlakesToFlakeAnalyzer([(flake, occurrences)])
    self.assertEqual(3, mock_analyze_flake_occurrence.call_count)
    expected_call_args = []
    for occurrence in occurrences:
      expected_call_args.append(((flake, occurrence, 12345),))

    self.assertEqual(expected_call_args,
                     mock_analyze_flake_occurrence.call_args_list)

  # This test tests that an open issue related to flaky tests will NOT be found
  # if it ONLY has the test name inside the summary.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(monorail_util, 'GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryNotFound(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test'
    issue.labels = []
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        None, flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and the 'Test-Flaky' label.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(monorail_util, 'GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithFlakeLabel(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test'
    issue.labels = ['Test-Flaky']
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and the 'Tests>Flaky' component.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(monorail_util, 'GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithFlakeComponent(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test'
    issue.labels = []
    issue.components = ['Tests>Flaky']
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and any of the flake keywords.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(monorail_util, 'GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithKeywordFlake(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test is a flake'
    issue.labels = []
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and any of the flake keywords.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(monorail_util, 'GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithKeywordFlaky(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test is flaky'
    issue.labels = []
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and any of the flake keywords.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(monorail_util, 'GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithKeywordFlakiness(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test is causing flakiness'
    issue.labels = []
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will not be found
  # if has the Test-FIndit-Wrong label.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(monorail_util, 'GetOpenIssues')
  def testSearchOpenIssueFlakyTestInSummaryWithTestFinditWrongLabel(
      self, mock_get_open_issues, mock_get_issue_id_by_customized_field):
    issue = mock.Mock()
    issue.summary = 'suite.test is causing flakiness'
    issue.labels = ['Test-Findit-Wrong']
    issue.components = []
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        None, flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with('summary:suite.test is:open',
                                                 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the Flaky-Test customized field.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestBySummary',
      return_value=None)
  @mock.patch.object(monorail_util, 'GetOpenIssues')
  def testSearchOpenIssueFlakyTestInCustomizedField(
      self, mock_get_open_issues, mock_get_issue_id_by_summary):
    issue = mock.Mock()
    issue.id = 123

    mock_get_open_issues.return_value = [issue]
    self.assertEqual(
        123, flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test'))
    mock_get_open_issues.assert_called_once_with(
        'Flaky-Test=suite.test is:open', 'chromium')
    mock_get_issue_id_by_summary.assert_called_once_with(
        'suite.test', 'chromium')

  # This test tests that the util first searches for open bugs by summary on
  # Monorail and if it is found, then skip searching for customized field.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestBySummary',
      return_value=12345)
  def testSearchAndFoundOpenIssueBySummary(
      self, mock_get_issue_id_by_summary,
      mock_get_issue_id_by_customized_field):
    self.assertEqual(
        12345,
        flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test',
                                                       'chromium'))
    mock_get_issue_id_by_summary.assert_called_once_with(
        'suite.test', 'chromium')
    mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that the util first searches for open bugs on Monorail and
  # if it is not found, then searches for customized field.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=12345)
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestBySummary',
      return_value=None)
  def testSearchAndFoundOpenIssueByCustomizedField(
      self, mock_get_issue_id_by_summary,
      mock_get_issue_id_by_customized_field):
    self.assertEqual(
        12345,
        flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test',
                                                       'chromium'))
    mock_get_issue_id_by_summary.assert_called_once_with(
        'suite.test', 'chromium')
    mock_get_issue_id_by_customized_field.assert_called_once_with(
        'suite.test', 'chromium')

  # This test tests that the util first searches for open bugs on Monorail and
  # if it is not found, then searches for customized field, and if still not
  # found, returns None.
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(
      flake_issue_util,
      '_GetOpenIssueIdForFlakyTestBySummary',
      return_value=None)
  def testSearchAndNotFoundOpenIssue(self, mock_get_issue_id_by_summary,
                                     mock_get_issue_id_by_customized_field):
    self.assertEqual(
        None,
        flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test',
                                                       'chromium'))
    mock_get_issue_id_by_summary.assert_called_once_with(
        'suite.test', 'chromium')
    mock_get_issue_id_by_customized_field.assert_called_once_with(
        'suite.test', 'chromium')

  # This test tests that when there are multiple issues related to the flaky
  # test, returns the id of the issue that was filed earliest.
  @mock.patch.object(monorail_util, 'GetOpenIssues')
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
        flake_issue_util.SearchOpenIssueIdForFlakyTest('suite.test',
                                                       'chromium'))

  # This test tests that if a flake has a flake issue attached and the bug is
  # open (not merged) on Monorail, then should directly update that bug.
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(monorail_util, 'CreateIssueWithIssueGenerator')
  def testHasFlakeAndFlakeIssueAndBugIsOpen(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, mock_get_merged_issue):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='suite.test',
        test_label_name='*/suite.test/*')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = True

    test_issue_generator = TestIssueGenerator()
    flake_issue_util.CreateOrUpdateIssue(test_issue_generator)

    self.assertFalse(mock_create_with_issue_generator_fn.called)
    mock_update_with_issue_generator_fn.assert_called_once_with(
        issue_id=12345, issue_generator=test_issue_generator)
    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertIn(flake, fetched_flakes)
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(12345, fetched_flake_issues[0].issue_id)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that if a flake has a flake issue attached and the bug is
  # closed (not merged) on Monorail, then should create a new one if an existing
  # open bug is not found on Monorail.
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=None)
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(
      monorail_util, 'CreateIssueWithIssueGenerator', return_value=66666)
  def testHasFlakeAndFlakeIssueAndBugIsClosed(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, mock_get_merged_issue, _):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='suite.test',
        test_label_name='*/suite.test/*')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = False

    test_issue_generator = TestIssueGenerator()
    flake_issue_util.CreateOrUpdateIssue(test_issue_generator)

    mock_create_with_issue_generator_fn.assert_called_once_with(
        issue_generator=test_issue_generator)
    self.assertFalse(mock_update_with_issue_generator_fn.called)
    fetched_flakes = Flake.query().fetch()

    new_flake_issue = FlakeIssue.Get(
        monorail_project='chromium', issue_id=66666)
    self.assertEqual(fetched_flakes[0].flake_issue_key, new_flake_issue.key)

  @mock.patch.object(
      MasterFlakeAnalysis,
      'GetRepresentativeSwarmingTaskId',
      return_value='task_id')
  @mock.patch.object(Flake, 'NormalizeStepName', return_value='normalized_step')
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=None)
  @mock.patch.object(monorail_util, 'UpdateBug')
  @mock.patch.object(monorail_util, 'CreateBug', return_value=66666)
  def testCreateIssueWhenFlakeAndIssueDoesNotExist(self, mock_create_bug_fn,
                                                   mock_update_bug_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    culprit = FlakeCulprit.Create('git', 'rev', 1)
    culprit.put()
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number
    analysis.data_points = [
        DataPoint.Create(commit_position=200, pass_rate=.5, git_hash='hash')
    ]
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.confidence_in_culprit = .5
    analysis.Save()

    issue_generator = FlakeAnalysisIssueGenerator(analysis)
    description = issue_generator.GetDescription()
    self.assertEqual(66666,
                     flake_issue_util.CreateOrUpdateIssue(issue_generator))
    self.assertTrue(mock_create_bug_fn.called)
    self.assertFalse(mock_update_bug_fn.called)
    self.assertIn('Test-Findit-Wrong', description)

    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(66666, fetched_flake_issues[0].issue_id)
    self.assertEqual(
        None, fetched_flake_issues[0].last_updated_time_by_flake_detection)

  @mock.patch.object(
      MasterFlakeAnalysis,
      'GetRepresentativeSwarmingTaskId',
      return_value='task_id')
  @mock.patch.object(Flake, 'NormalizeTestName', return_value='normalized_test')
  @mock.patch.object(Flake, 'NormalizeStepName', return_value='normalized_step')
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=None)
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  @mock.patch.object(monorail_util, 'UpdateBug')
  @mock.patch.object(monorail_util, 'CreateBug')
  def testUpdateIssueWhenFlakeAndIssueExists(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_merged_issue, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number
    analysis.Save()

    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='normalized_step',
        normalized_test_name='normalized_test',
        test_label_name='test_label')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()
    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = True

    issue_generator = FlakeAnalysisIssueGenerator(analysis)
    flake_issue_util.CreateOrUpdateIssue(issue_generator)
    self.assertFalse(mock_create_bug_fn.called)
    self.assertTrue(mock_update_bug_fn.called)

    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertIn(flake, fetched_flakes)
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(12345, fetched_flake_issues[0].issue_id)
    self.assertEqual(
        None, fetched_flake_issues[0].last_updated_time_by_flake_detection)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that if there is no flake for a test, and found an existing
  # issue about this flaky test on Monorail, then should create a new flake,
  # update the issue and attach the issue to the flake.
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=99999)
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(monorail_util, 'CreateIssueWithIssueGenerator')
  def testHasNoFlakeAndFoundAnExistingOpenIssue(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, _):
    step_name = 'step_2'
    test_name = 'test_2'
    test_issue_generator = TestIssueGenerator(
        step_name=step_name, test_name=test_name)
    flake_issue_util.CreateOrUpdateIssue(test_issue_generator)

    self.assertFalse(mock_create_with_issue_generator_fn.called)
    mock_update_with_issue_generator_fn.assert_called_once_with(
        issue_id=99999, issue_generator=test_issue_generator)
    fetched_flake_issues = FlakeIssue.query().fetch()

    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(99999, fetched_flake_issues[0].issue_id)

  # This test tests that if a flake has a flake issue attached and the bug is
  # closed (not merged) on Monorail, but found an existing open issue on
  # Monorail, then should update the issue and attach it to the flake.
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=99999)
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(monorail_util, 'CreateIssueWithIssueGenerator')
  def testHasFlakeAndFlakeAndBugIsClosedButFoundAnExistingOpenIssue(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, mock_get_merged_issue, _):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='suite.test',
        test_label_name='*/suite.test/*')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = False

    test_issue_generator = TestIssueGenerator()
    flake_issue_util.CreateOrUpdateIssue(test_issue_generator)

    self.assertFalse(mock_create_with_issue_generator_fn.called)
    mock_update_with_issue_generator_fn.assert_called_once_with(
        issue_id=99999, issue_generator=test_issue_generator)
    fetched_flakes = Flake.query().fetch()
    self.assertEqual('step', fetched_flakes[0].normalized_step_name)
    self.assertEqual('suite.test', fetched_flakes[0].normalized_test_name)

    original_issues = FlakeIssue.query(FlakeIssue.issue_id == 12345).fetch()
    self.assertEqual(1, len(original_issues))

    new_flake_issue = FlakeIssue.Get(
        monorail_project='chromium', issue_id=99999)
    self.assertEqual(fetched_flakes[0].flake_issue_key, new_flake_issue.key)

  # This test tests that if a flake has a flake issue attached and the bug was
  # merged to another bug on Monorail, but that destination bug was closed, then
  # should create a new one if an existing open bug is not found on Monorail.
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=None)
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(
      monorail_util, 'CreateIssueWithIssueGenerator', return_value=66666)
  def testHasFlakeAndFlakeIssueAndBugWasMergedToAClosedBug(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, mock_get_merged_issue, _):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='suite.test',
        test_label_name='*/suite.test/*')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    # Merged issue is already in data store.
    FlakeIssue.Create(monorail_project='chromium', issue_id=56789).put()

    mock_get_merged_issue.return_value.id = 56789
    mock_get_merged_issue.return_value.open = False

    test_issue_generator = TestIssueGenerator()
    flake_issue_util.CreateOrUpdateIssue(test_issue_generator)

    mock_create_with_issue_generator_fn.assert_called_once_with(
        issue_generator=test_issue_generator)
    self.assertFalse(mock_update_with_issue_generator_fn.called)
    fetched_flakes = Flake.query().fetch()
    original_issue = FlakeIssue.Get(monorail_project='chromium', issue_id=12345)
    merged_issue = FlakeIssue.Get(monorail_project='chromium', issue_id=56789)
    self.assertEqual(original_issue.merge_destination_key, merged_issue.key)

    new_flake_issue = FlakeIssue.Get(
        monorail_project='chromium', issue_id=66666)
    self.assertEqual(fetched_flakes[0].flake_issue_key, new_flake_issue.key)

  # This test tests that if there is no existing flake for a test, and couldn't
  # find an existing issue about this flaky test on Monorail, then should create
  # a new flake and a new issue and attach the issue to the flake.
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=None)
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(
      monorail_util, 'CreateIssueWithIssueGenerator', return_value=66666)
  def testHasNoFlakeAndNoExistingOpenIssue(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, _):
    step_name = 'step_1'
    test_name = 'test_1'
    test_issue_generator = TestIssueGenerator(
        step_name=step_name, test_name=test_name)
    flake_issue_util.CreateOrUpdateIssue(test_issue_generator)

    mock_create_with_issue_generator_fn.assert_called_once_with(
        issue_generator=test_issue_generator)
    self.assertFalse(mock_update_with_issue_generator_fn.called)
    fetched_flake_issues = FlakeIssue.query().fetch()

    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(66666, fetched_flake_issues[0].issue_id)

  # This test tests that if there is a flake for a test, but no flake issue
  # attached and couldn't find an existing issue about this flaky test on
  # Monorail, then should create a new issue and attach the issue to the flake.
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=None)
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(
      monorail_util, 'CreateIssueWithIssueGenerator', return_value=66666)
  def testHasFlakeButNoFlakeIssueAndNoExistingOpenIssue(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, _):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='suite.test',
        test_label_name='*/suite.test/*')
    flake.put()
    test_issue_generator = TestIssueGenerator()
    flake_issue_util.CreateOrUpdateIssue(test_issue_generator)

    mock_create_with_issue_generator_fn.assert_called_once_with(
        issue_generator=test_issue_generator)
    self.assertFalse(mock_update_with_issue_generator_fn.called)
    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    self.assertIn(flake, fetched_flakes)
    self.assertEqual('step', fetched_flakes[0].normalized_step_name)
    self.assertEqual('suite.test', fetched_flakes[0].normalized_test_name)
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(66666, fetched_flake_issues[0].issue_id)
    self.assertEqual(flake.flake_issue_key, fetched_flake_issues[0].key)

  # This test tests that if a flake has a flake issue attached and the bug was
  # merged to another bug on Monorail, and that destination bug is open, then
  # should update the destination bug.
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(monorail_util, 'CreateIssueWithIssueGenerator')
  def testHasFlakeAndFlakeIssueAndBugWasMergedToAnOpenBug(
      self, mock_create_with_issue_generator_fn,
      mock_update_with_issue_generator_fn, mock_get_merged_issue):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='suite.test',
        test_label_name='*/suite.test/*')
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    leaf_flake_issue = FlakeIssue.Create(
        monorail_project='chromium', issue_id=67890)
    leaf_flake_issue.merge_destination_key = flake_issue.key
    leaf_flake_issue.put()

    mock_get_merged_issue.return_value.id = 45678
    mock_get_merged_issue.return_value.open = True

    test_issue_generator = TestIssueGenerator()
    flake_issue_util.CreateOrUpdateIssue(test_issue_generator)

    self.assertFalse(mock_create_with_issue_generator_fn.called)
    mock_update_with_issue_generator_fn.assert_called_once_with(
        issue_id=45678, issue_generator=test_issue_generator)
    fetched_flakes = Flake.query().fetch()

    original_issue = FlakeIssue.Get(monorail_project='chromium', issue_id=12345)

    merged_issue = FlakeIssue.Get(monorail_project='chromium', issue_id=45678)
    self.assertEqual(original_issue.merge_destination_key, merged_issue.key)
    self.assertEqual(fetched_flakes[0].flake_issue_key, original_issue.key)

  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=True)
  def testOpenIssueAlreadyExistsForFlakyTest(self, _):
    self.assertTrue(flake_issue_util.OpenIssueAlreadyExistsForFlakyTest('t'))

  def testGetFlakeIssueDataInconsistent(self):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake_issue_key = flake_issue.key
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name='step',
        normalized_test_name='suite.test',
        test_label_name='*/suite.test/*')
    flake.flake_issue_key = flake_issue_key
    flake.put()

    flake_issue_key.delete()

    self.assertIsNone(flake_issue_util.GetFlakeIssue(flake))

  @mock.patch.object(flake_issue_util, 'GetAndUpdateMergedIssue')
  def testGetFlakeGroupsForActionsOnBugs(self, mock_get_merged_issue):
    # New flake, no linked issue.
    flake1 = self._CreateFlake('s1', 'suite1.t1', 'suite1.t1', 'suite1')
    occurrences1 = [
        self._CreateFlakeOccurrence(1, 's1', 'suite1.t1', 12345, flake1.key),
        self._CreateFlakeOccurrence(2, 's1', 'suite1.t1', 12346, flake1.key)
    ]
    # New flake, no linked issue, same group as flake1.
    flake2 = self._CreateFlake('s1', 'suite1.t2', 'suite1.t2', 'suite1')
    occurrences2 = [
        self._CreateFlakeOccurrence(1, 's1', 'suite1.t2', 12345, flake2.key),
        self._CreateFlakeOccurrence(2, 's1', 'suite1.t2', 12346, flake2.key)
    ]
    # New flake, no linked issue, same step and suite as flake1&2,
    # but different occurrences.
    flake3 = self._CreateFlake('s3', 'suite1.t3', 'suite1.t3', 'suite1')
    occurrences3 = [
        self._CreateFlakeOccurrence(1, 's1', 'suite1.t3', 12345, flake3.key),
        self._CreateFlakeOccurrence(3, 's1', 'suite1.t3', 12347, flake3.key)
    ]
    # New flake, no linked issue, different step and suite.
    flake4 = self._CreateFlake('s2', 'suite2.t4', 'suite2.t4', 'suite2')
    occurrences4 = [
        self._CreateFlakeOccurrence(1, 's2', 'suite2.t4', 12345, flake4.key),
        self._CreateFlakeOccurrence(2, 's2', 'suite2.t4', 12346, flake4.key)
    ]
    # Old flake, with issue.
    flake_issue1 = FlakeIssue.Create(
        monorail_project='chromium', issue_id=56789)
    flake_issue1.put()
    flake5 = self._CreateFlake('s2', 'suite2.t5', 'suite2.t5')
    flake5.flake_issue_key = flake_issue1.key
    flake5.put()
    occurrences5 = [
        self._CreateFlakeOccurrence(1, 's2', 'suite2.t4', 12345, flake5.key),
        self._CreateFlakeOccurrence(2, 's2', 'suite2.t4', 12346, flake5.key)
    ]
    # Old flake, with same issue as flake5.
    flake6 = self._CreateFlake('s3', 'suite3.t6', 'suite3.t6')
    flake6.flake_issue_key = flake_issue1.key
    flake6.put()
    occurrences6 = [
        self._CreateFlakeOccurrence(3, 's3', 'suite3.t6', 34467, flake6.key),
        self._CreateFlakeOccurrence(4, 's3', 'suite3.t6', 35546, flake6.key),
        self._CreateFlakeOccurrence(5, 's3', 'suite3.t6', 67543, flake6.key)
    ]
    # Old flake, different issue.
    flake_issue2 = FlakeIssue.Create(
        monorail_project='chromium', issue_id=67890)
    flake_issue2.put()
    flake7 = self._CreateFlake('s3', 'suite3.t7', 'suite3.t7')
    flake7.flake_issue_key = flake_issue2.key
    flake7.put()
    occurrences7 = [
        self._CreateFlakeOccurrence(1, 's3', 'suite3.t7', 12345, flake7.key),
        self._CreateFlakeOccurrence(2, 's3', 'suite3.t7', 12346, flake7.key)
    ]

    flake_group1 = flake_issue_util.FlakeGroupByOccurrences(
        flake1, occurrences1)
    flake_group1.AddFlakeIfBelong(flake2, occurrences2)

    flake_group2 = flake_issue_util.FlakeGroupByOccurrences(
        flake3, occurrences3)
    flake_group3 = flake_issue_util.FlakeGroupByOccurrences(
        flake4, occurrences4)

    flake_group4 = flake_issue_util.FlakeGroupByFlakeIssue(
        flake_issue1, flake5, occurrences5, flake_issue1)
    flake_group4.AddFlakeIfBelong(flake6, occurrences6)

    flake_group5 = flake_issue_util.FlakeGroupByFlakeIssue(
        flake_issue2, flake7, occurrences7, flake_issue2)

    flake_tuples_to_report = [(flake1, occurrences1, None),
                              (flake2, occurrences2, None),
                              (flake3, occurrences3, None),
                              (flake4, occurrences4, None),
                              (flake5, occurrences5, flake_issue1),
                              (flake6, occurrences6, flake_issue1),
                              (flake7, occurrences7, flake_issue2)]

    mock_get_merged_issue.return_value.open = True

    flake_groups_without_issue, flake_groups_with_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs(flake_tuples_to_report))

    self.assertItemsEqual(
        [flake_group1.ToDict(),
         flake_group2.ToDict(),
         flake_group3.ToDict()],
        [group.ToDict() for group in flake_groups_without_issue])

    self.assertItemsEqual(
        [flake_group4.ToDict(), flake_group5.ToDict()],
        [group.ToDict() for group in flake_groups_with_issue])

  # This test is for when the issue linked to flakes is closed, should not
  # group flakes by issue in this case.
  @mock.patch.object(flake_issue_util, 'GetAndUpdateMergedIssue')
  def testGetFlakeGroupsForActionsOnBugsIssueClosed(self,
                                                    mock_get_merged_issue):
    mock_get_merged_issue.return_value.open = False
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=56789)
    flake_issue.put()
    flake = self._CreateFlake('s2', 'suite2.t5', 'suite2.t5')
    flake.flake_issue_key = flake_issue.key
    flake.put()
    occurrences = [
        self._CreateFlakeOccurrence(1, 's2', 'suite2.t4', 12345, flake.key),
        self._CreateFlakeOccurrence(2, 's2', 'suite2.t4', 12346, flake.key)
    ]

    flake_group = flake_issue_util.FlakeGroupByOccurrences(flake, occurrences)

    flake_groups_without_issue, flake_groups_with_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs([(flake, occurrences,
                                                          flake_issue)]))
    self.assertEqual([flake_group.ToDict()],
                     [group.ToDict() for group in flake_groups_without_issue])
    self.assertEqual([], flake_groups_with_issue)

  # This test is for when the issue linked to flakes is merged to an open bug.
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  def testGetFlakeGroupsForActionsOnBugsIssueNewMergeIssue(
      self, mock_get_merged_issue):
    mock_get_merged_issue.return_value.open = True
    mock_get_merged_issue.return_value.id = 54321
    flake_issue1 = FlakeIssue.Create(
        monorail_project='chromium', issue_id=56789)
    flake_issue1.put()
    flake_issue2 = FlakeIssue.Create(
        monorail_project='chromium', issue_id=54321)
    flake_issue2.put()
    flake = self._CreateFlake('s2', 'suite2.t5', 'suite2.t5')
    flake.flake_issue_key = flake_issue1.key
    flake.put()
    occurrences = [
        self._CreateFlakeOccurrence(1, 's2', 'suite2.t4', 12345, flake.key),
        self._CreateFlakeOccurrence(2, 's2', 'suite2.t4', 12346, flake.key)
    ]

    flake_group = flake_issue_util.FlakeGroupByFlakeIssue(
        flake_issue2, flake, occurrences, flake_issue1)

    flake_groups_without_issue, flake_groups_with_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs([(flake, occurrences,
                                                          flake_issue1)]))
    self.assertEqual([], flake_groups_without_issue)
    self.assertEqual([flake_group.ToDict()],
                     [group.ToDict() for group in flake_groups_with_issue])

  def testUpdateIssueLeaves(self):
    final_issue = FlakeIssue.Create('chromium', 3)
    final_issue.put()

    obsolete_merged_issue = FlakeIssue.Create('chromium', 2)
    obsolete_merged_issue.put()

    flake_issue = FlakeIssue.Create('chromium', 1)
    flake_issue.merge_destination_key = obsolete_merged_issue.key
    flake_issue.put()

    flake_issue_util.UpdateIssueLeaves(obsolete_merged_issue.key,
                                       final_issue.key)
    flake_issue = flake_issue.key.get()
    self.assertEqual(flake_issue.merge_destination_key, final_issue.key)
