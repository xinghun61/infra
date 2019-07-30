# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import mock
import textwrap

from googleapiclient.errors import HttpError
from libs import time_util
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FlakeType
from monorail_api import Issue
from services import flake_issue_util
from services import monorail_util
from services.issue_generator import FlakeDetectionGroupIssueGenerator
from services.issue_generator import FlakyTestIssueGenerator
from waterfall.test.wf_testcase import WaterfallTestCase

# pylint:disable=unused-argument, unused-variable
# https://crbug.com/947753


class FlakeReportUtilTest(WaterfallTestCase):

  def _CreateFlake(self,
                   normalized_step_name,
                   normalized_test_name,
                   test_label_name,
                   test_suite_name=None,
                   canonical_step_name=None,
                   flake_score_last_week=0):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)
    if test_suite_name:
      flake.tags.append('suite::%s' % test_suite_name)
    flake.tags.append('test_type::{}'.format(canonical_step_name or
                                             normalized_step_name))
    flake.flake_score_last_week = flake_score_last_week
    flake.put()
    return flake

  def _CreateFlakeOccurrence(self,
                             build_id,
                             step_ui_name,
                             test_name,
                             gerrit_cl_id,
                             parent_flake_key,
                             flake_type=FlakeType.CQ_FALSE_REJECTION):
    flake_occurrence = FlakeOccurrence.Create(
        flake_type=flake_type,
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
    self._CreateFlakeOccurrence(
        222,
        'step2',
        'test2',
        98764,
        self.flake.key,
        flake_type=FlakeType.RETRY_WITH_PATCH)
    self._CreateFlakeOccurrence(333, 'step3', 'test3', 98763, self.flake.key)

  # This test tests that getting flakes with enough occurrences works properly.
  def testGetFlakesWithEnoughOccurrences(self):
    flake_with_higher_score = self._CreateFlake(
        'step1', 'test1', 'test_label1', flake_score_last_week=100)
    self._CreateFlakeOccurrence(111, 'step1_1', 'test1_1', 98765,
                                flake_with_higher_score.key)
    self._CreateFlakeOccurrence(222, 'step1_2', 'test1_2', 98764,
                                flake_with_higher_score.key)
    self._CreateFlakeOccurrence(333, 'step1_3', 'test1_3', 98763,
                                flake_with_higher_score.key)

    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    self.assertEqual(2, len(flakes_with_occurrences))
    self.assertEqual(3, len(flakes_with_occurrences[1][1]))
    self.assertIsNone(flakes_with_occurrences[1][2])
    self.assertEqual(flake_with_higher_score.key,
                     flakes_with_occurrences[0][0].key)

  # This test tests that in order for a flake to have enough occurrences, there
  # needs to be at least 3 (min_required_impacted_cls_per_day) occurrences
  # with different CLs, and different patchsets of the same CL are only counted
  # once.
  def testMinimumRequiredFalselyRejectedCLs(self):
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()
    for occurrence in occurrences:
      occurrence.gerrit_cl_id = 565656
      occurrence.put()

    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    self.assertEqual(0, len(flakes_with_occurrences))

  # This test tests that occurrences happened more than one day ago are ignored.
  def testIgnoreOutdatedOccurrences(self):
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()
    occurrences[2].time_happened = self._GetDatetimeHoursAgo(25)
    occurrences[2].put()

    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    self.assertEqual(0, len(flakes_with_occurrences))

  # This test tests that if the number of issues created or updated within the
  # past 24 hours has already reached a limit, then no issues can be created or
  # updated.
  @mock.patch.object(flake_issue_util, '_CreateIssuesForFlakes')
  def testCreateOrUpdateIssuesPerDayLimit(self, mock_create_bug):
    flakes_with_occurrences = flake_issue_util.GetFlakesWithEnoughOccurrences()
    groups_wo_issue, groups_w_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs(flakes_with_occurrences)
    )
    self.UpdateUnitTestConfigSettings(
        'action_settings', {'max_flake_detection_bug_updates_per_day': 0})
    flake_issue_util.ReportFlakesToMonorail(groups_wo_issue, groups_w_issue)
    self.assertFalse(mock_create_bug.called)

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
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()
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
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()
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
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()
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
    self.UpdateUnitTestConfigSettings(
        'action_settings', {'max_flake_detection_bug_updates_per_day': 0})

    flake = Flake.query().fetch()[0]
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()
    groups_wo_issue, groups_w_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs([(flake, occurrences,
                                                          None)]))
    flake_issue_util.ReportFlakesToMonorail(groups_wo_issue, groups_w_issue)
    self.assertFalse(mock_create_bug_fn.called)
    self.assertFalse(mock_update_bug_fn.called)

  # This test tests that:
  # 1. When a flake has no flake issue attached, it creates a new issue and
  # attach it to the flake.
  @mock.patch.object(
      flake_issue_util,
      'SearchRecentlyClosedIssueIdForFlakyTest',
      return_value=None)
  @mock.patch('services.monorail_util.UpdateIssueWithIssueGenerator')
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=None)
  @mock.patch.object(monorail_util, 'UpdateBug')
  @mock.patch.object(monorail_util, 'CreateBug', return_value=666661)
  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  def testCreateIssue(self, mock_issue, mock_create_bug_fn, mock_update_bug_fn,
                      *_):
    mock_issue.return_value = Issue({
        'status': 'Untriaged',
        'priority': 1,
        'updated': '2018-12-07T17:52:45',
        'id': '666666',
    })
    flake = Flake.query().fetch()[0]
    flake.tags.append('component::Blink')
    flake.put()
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type.IN(
            [FlakeType.CQ_FALSE_REJECTION,
             FlakeType.RETRY_WITH_PATCH])).fetch()

    groups_wo_issue, groups_w_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs([(flake, occurrences,
                                                          None)]))
    flake_issue_util.ReportFlakesToMonorail(groups_wo_issue, groups_w_issue)

    expected_status = 'Untriaged'
    expected_summary = 'test_label is flaky'

    expected_wrong_result_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?status=Unconfirmed&'
        'labels=Pri-1,Test-Findit-Wrong&components=Infra%3ETest%3EFlakiness&'
        'summary=%5BFindit%5D%20Flake%20Detection%20-%20Wrong%20'
        'result%3A%20test&comment=Link%20to%20flake%20details%3A%20'
        'https://analysis.chromium.org'
        '/p/chromium/flake-portal/flakes/occurrences?key={}').format(
            flake.key.urlsafe())

    expected_description = textwrap.dedent("""
test_label is flaky.

Findit has detected 3 flake occurrences of this test within the
past 24 hours. List of all flake occurrences can be found at:
https://analysis.chromium.org/p/chromium/flake-portal/flakes/occurrences?key={}.

Unless the culprit CL is found and reverted, please disable this test first
within 30 minutes then find an appropriate owner.

If the result above is wrong, please file a bug using this link:
{}

Automatically posted by the findit-for-me app (https://goo.gl/Ne6KtC)."""
                                          ).format(flake.key.urlsafe(),
                                                   expected_wrong_result_link)

    expected_labels = [
        'Type-Bug', 'Test-Flaky', 'Test-Findit-Detected', 'Pri-1',
        'Sheriff-Chromium'
    ]

    self.assertTrue(mock_create_bug_fn.called)
    self.assertFalse(mock_update_bug_fn.called)
    issue = mock_create_bug_fn.call_args_list[0][0][0]
    self.assertEqual(expected_status, issue.status)
    self.assertEqual(expected_summary, issue.summary)
    self.assertEqual(expected_description, issue.description)
    self.assertItemsEqual(expected_labels, issue.labels)
    self.assertEqual(['Blink'], issue.components)
    self.assertEqual(1, len(issue.field_values))
    self.assertEqual('Flaky-Test', issue.field_values[0].to_dict()['fieldName'])
    self.assertEqual('test', issue.field_values[0].to_dict()['fieldValue'])

    flake = Flake.Get('chromium', 'step', 'test')
    flake_issue = FlakeIssue.Get('chromium', 666661)
    self.assertEqual(
        datetime.datetime(2018, 1, 2),
        flake_issue.last_updated_time_by_flake_detection)
    self.assertEqual(flake.flake_issue_key, flake_issue.key)

  @mock.patch.object(
      flake_issue_util,
      'GetRemainingPreAnalysisDailyBugUpdatesCount',
      return_value=1)
  @mock.patch.object(
      flake_issue_util,
      'SearchRecentlyClosedIssueIdForFlakyTest',
      return_value=None)
  @mock.patch.object(flake_issue_util, 'SearchOpenIssueIdForFlakyTest')
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  @mock.patch.object(monorail_util, 'CreateBug', return_value=666662)
  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  def testLinkIssueFromMonorail(self, mock_issue, mock_create_bug_fn,
                                mock_update_bug_fn, mock_search_open_bug, *_):
    """ This test tests that:
      1. If bug can be created or updated, and an existing bug
        is found for a flake, link the bug to the flake and updating it.
      2. If no more bug can be created nor updated, but an existing bug
        is found for a flake, link the bug to the flake without updating it.
    """
    mock_issue.return_value = Issue({
        'status': 'Untriaged',
        'priority': 1,
        'updated': '2018-12-07T17:52:45',
        'id': '666666',
    })
    flake = Flake.query().fetch()[0]
    flake.tags.append('component::Blink')
    flake.put()
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type.IN(
            [FlakeType.CQ_FALSE_REJECTION,
             FlakeType.RETRY_WITH_PATCH])).fetch()

    flake1 = self._CreateFlake('step0', 'test0', 'test_label1')
    occurrences1 = [
        self._CreateFlakeOccurrence(111, 'step1', 'test01', 98765, flake1.key),
        self._CreateFlakeOccurrence(222, 'step2', 'test02', 98764, flake1.key),
        self._CreateFlakeOccurrence(333, 'step3', 'test03', 98763, flake1.key)
    ]

    def MockSearchOpenBug(test_name, _monorail_project):
      return 12345 if test_name == 'test0' else 666662

    mock_search_open_bug.side_effect = MockSearchOpenBug

    groups_wo_issue, groups_w_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs(
            [(flake, occurrences, None), (flake1, occurrences1, None)]))
    flake_issue_util.ReportFlakesToMonorail(groups_wo_issue, groups_w_issue)

    self.assertFalse(mock_create_bug_fn.called)
    self.assertTrue(mock_update_bug_fn.called)
    flake = Flake.Get('chromium', 'step', 'test')
    flake_issue = FlakeIssue.Get('chromium', 666662)
    self.assertIsNone(flake_issue.last_updated_time_by_flake_detection)
    self.assertEqual(flake.flake_issue_key, flake_issue.key)

    flake1 = Flake.Get('chromium', 'step0', 'test0')
    flake_issue1 = FlakeIssue.Get('chromium', 12345)
    self.assertEqual(
        datetime.datetime(2018, 1, 2),
        flake_issue1.last_updated_time_by_flake_detection)
    self.assertEqual(flake1.flake_issue_key, flake_issue1.key)

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
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()
    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = True
    groups_wo_issue, groups_w_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs([(flake, occurrences,
                                                          flake_issue)]))
    flake_issue_util.ReportFlakesToMonorail(groups_wo_issue, groups_w_issue)

    expected_wrong_result_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?status=Unconfirmed&'
        'labels=Pri-1,Test-Findit-Wrong&components=Infra%3ETest%3EFlakiness'
        '&summary=%5BFindit%5D%20Flake%20Detection%20-%20Wrong%20'
        'result%3A%20test&comment=Link%20to%20flake%20details%3A%20'
        'https://analysis.chromium.org'
        '/p/chromium/flake-portal/flakes/occurrences?key={}').format(
            flake.key.urlsafe())

    sheriff_queue_message = (
        'Since these tests are still flaky, this issue has been moved back onto'
        ' the Sheriff Bug Queue if it hasn\'t already.')

    expected_comment = textwrap.dedent("""
test_label is flaky.

Findit has detected 3 new flake occurrences of this test. List
of all flake occurrences can be found at:
https://analysis.chromium.org/p/chromium/flake-portal/flakes/occurrences?key={}.

{}

If the result above is wrong, please file a bug using this link:
{}

Automatically posted by the findit-for-me app (https://goo.gl/Ne6KtC)."""
                                      ).format(flake.key.urlsafe(),
                                               sheriff_queue_message,
                                               expected_wrong_result_link)

    self.assertFalse(mock_create_bug_fn.called)
    self.assertTrue(mock_update_bug_fn)
    comment = mock_update_bug_fn.call_args_list[0][0][1]
    self.assertEqual(expected_comment, comment)

    fetched_flakes = Flake.query().fetch()
    fetched_flake_issues = FlakeIssue.query().fetch()
    flake_issue = FlakeIssue.Get('chromium', 12345)
    self.assertEqual(1, len(fetched_flakes))
    self.assertEqual(1, len(fetched_flake_issues))
    self.assertEqual(12345, fetched_flake_issues[0].issue_id)
    self.assertEqual(
        datetime.datetime(2018, 1, 2),
        flake_issue.last_updated_time_by_flake_detection)
    self.assertEqual(fetched_flakes[0].flake_issue_key, flake_issue.key)

  # This test tests that when a flake has a flake issue attached and the issue
  # was merged to another open bug, it updates the destination bug with
  # a previous tracking bug id.
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  @mock.patch.object(monorail_util, 'UpdateBug')
  @mock.patch.object(monorail_util, 'CreateBug')
  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  def testUpdateIssueWithPreviousTrackingBugId(
      self, mock_issue, mock_create_bug_fn, mock_update_bug_fn,
      mock_get_merged_issue):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()
    mock_issue.return_value = Issue({
        'status': 'Available',
        'labels': ['Type-Bug', 'Pri-1'],
        'updated': '2018-12-07T17:52:45',
        'id': '56789',
    })
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()
    mock_get_merged_issue.return_value.id = 56789
    mock_get_merged_issue.return_value.open = True
    groups_wo_issue, groups_w_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs([(flake, occurrences,
                                                          flake_issue)]))
    flake_issue_util.ReportFlakesToMonorail(groups_wo_issue, groups_w_issue)

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
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()
    flake2 = self._CreateFlake('step_other', 'test_other', 'test_label_other')
    self._CreateFlakeOccurrence(777, 'step1_other', 'test1_other', 54321,
                                flake2.key)
    self._CreateFlakeOccurrence(888, 'step2_other', 'test2_other', 54322,
                                flake2.key)
    self._CreateFlakeOccurrence(999, 'step3_other', 'test3_other', 54323,
                                flake2.key)
    occurrences2 = FlakeOccurrence.query(ancestor=flake2.key).filter(
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()

    groups_wo_issue, groups_w_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs(
            [(flake1, occurrences1, None), (flake2, occurrences2, None)]))
    flake_issue_util.ReportFlakesToMonorail(groups_wo_issue, groups_w_issue)

  # This test tests that if the feature to report flakes to Flake Analyzer is
  # disabled, flakes will NOT be reported.
  @mock.patch.object(flake_issue_util, 'AnalyzeDetectedFlakeOccurrence')
  def testDisableReportFlakesToFlakeAnalyzer(self,
                                             mock_analyze_flake_occurrence):
    self.UpdateUnitTestConfigSettings(
        'flake_detection_settings', {'report_flakes_to_flake_analyzer': False})

    flake = Flake.query().fetch()[0]
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()
    flake_issue_util.ReportFlakesToFlakeAnalyzer([(flake, occurrences, None)])
    self.assertFalse(mock_analyze_flake_occurrence.called)

  @mock.patch.object(flake_issue_util, 'AnalyzeDetectedFlakeOccurrence')
  def testReportFlakesToFlakeAnalyzer(self, mock_analyze_flake_occurrence):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()
    occurrences = FlakeOccurrence.query(
        FlakeOccurrence.flake_type.IN([
            FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH,
            FlakeType.CI_FAILED_STEP
        ])).fetch()

    flake_issue_util.ReportFlakesToFlakeAnalyzer([(flake, occurrences,
                                                   flake_issue)])
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
      '_GetIssueIdForFlakyTestByCustomizedField',
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
    # Assertions have never worked properly because we were using mock 1.0.1.
    # After rolling to mock 2.0.0, which fixes assertions, these assertions now
    # fail. https://crbug.com/947753.
    # mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the summary and the 'Test-Flaky' label.
  @mock.patch.object(
      flake_issue_util,
      '_GetIssueIdForFlakyTestByCustomizedField',
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
  # it has the test name inside the summary and any of the flake keywords.
  @mock.patch.object(
      flake_issue_util,
      '_GetIssueIdForFlakyTestByCustomizedField',
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
      '_GetIssueIdForFlakyTestByCustomizedField',
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
      '_GetIssueIdForFlakyTestByCustomizedField',
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
      '_GetIssueIdForFlakyTestByCustomizedField',
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
    # Assertions have never worked properly because we were using mock 1.0.1.
    # After rolling to mock 2.0.0, which fixes assertions, these assertions now
    # fail. https://crbug.com/947753.
    # mock_get_issue_id_by_customized_field.assert_not_called()

  # This test tests that an open issue related to flaky tests will be found if
  # it has the test name inside the Flaky-Test customized field.
  @mock.patch.object(
      flake_issue_util, '_GetIssueIdForFlakyTestBySummary', return_value=None)
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
      '_GetIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(
      flake_issue_util, '_GetIssueIdForFlakyTestBySummary', return_value=12345)
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
      '_GetIssueIdForFlakyTestByCustomizedField',
      return_value=12345)
  @mock.patch.object(
      flake_issue_util, '_GetIssueIdForFlakyTestBySummary', return_value=None)
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
      '_GetIssueIdForFlakyTestByCustomizedField',
      return_value=None)
  @mock.patch.object(
      flake_issue_util, '_GetIssueIdForFlakyTestBySummary', return_value=None)
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

  @mock.patch.object(
      flake_issue_util,
      'SearchRecentlyClosedIssueIdForFlakyTest',
      return_value=None)
  @mock.patch.object(
      flake_issue_util, 'SearchOpenIssueIdForFlakyTest', return_value=True)
  def testOpenIssueAlreadyExistsForFlakyTest(self, *_):
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

  @mock.patch.object(
      time_util,
      'GetDateDaysBeforeNow',
      return_value=datetime.datetime(2019, 1, 28))
  @mock.patch.object(flake_issue_util, 'GetAndUpdateMergedIssue')
  def testGetFlakeGroupsForActionsOnBugs(self, mock_get_merged_issue, _):
    # New flake, no linked issue.
    flake1 = self._CreateFlake(
        's1', 'suite1.t1', 'suite1.t1', 'suite1', canonical_step_name='s1_c')
    occurrences1 = [
        self._CreateFlakeOccurrence(1, 's1', 'suite1.t1', 12345, flake1.key),
        self._CreateFlakeOccurrence(2, 's1', 'suite1.t1', 12346, flake1.key)
    ]
    # New flake, no linked issue, same group as flake1.
    flake2 = self._CreateFlake(
        's1', 'suite1.t2', 'suite1.t2', 'suite1', canonical_step_name='s1_c')
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
    # Old flake, issue closed within a week.
    flake_issue3 = FlakeIssue.Create(
        monorail_project='chromium', issue_id=67893)
    flake_issue3.put()
    flake8 = self._CreateFlake('s3', 'suite3.t8', 'suite3.t8')
    flake8.flake_issue_key = flake_issue3.key
    flake8.put()
    occurrences8 = [
        self._CreateFlakeOccurrence(1, 's3', 'suite3.t8', 12345, flake8.key),
        self._CreateFlakeOccurrence(2, 's3', 'suite3.t8', 12346, flake8.key)
    ]
    # Old flake, issue closed over a week.
    flake_issue4 = FlakeIssue.Create(
        monorail_project='chromium', issue_id=67894)
    flake_issue4.put()
    flake9 = self._CreateFlake('s3', 'suite3.t9', 'suite3.t9')
    flake9.flake_issue_key = flake_issue4.key
    flake9.put()
    occurrences9 = [
        self._CreateFlakeOccurrence(1, 's3', 'suite3.t9', 12345, flake9.key),
        self._CreateFlakeOccurrence(2, 's3', 'suite3.t9', 12346, flake9.key)
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

    flake_group6 = flake_issue_util.FlakeGroupByFlakeIssue(
        flake_issue3, flake8, occurrences8, flake_issue3)

    flake_group7 = flake_issue_util.FlakeGroupByOccurrences(
        flake9, occurrences9)

    flake_tuples_to_report = [(flake1, occurrences1, None),
                              (flake2, occurrences2, None),
                              (flake3, occurrences3, None),
                              (flake4, occurrences4, None),
                              (flake5, occurrences5, flake_issue1),
                              (flake6, occurrences6, flake_issue1),
                              (flake7, occurrences7, flake_issue2),
                              (flake8, occurrences8, flake_issue3),
                              (flake9, occurrences9, flake_issue4)]

    def MockedGetmergedIssue(flake_issue):
      issue_id_to_monorail_issue = {
          flake_issue1.key:
              Issue({
                  'id': '56789',
                  'status': 'Available',
                  'updated': '2018-12-10T0:0:0',
                  'state': 'open'
              }),
          flake_issue2.key:
              Issue({
                  'id': '67890',
                  'status': 'Available',
                  'updated': '2018-12-10T0:0:0',
                  'state': 'open'
              }),
          flake_issue3.key:
              Issue({
                  'id': '67893',
                  'status': 'Fixed',
                  'closed': '2019-1-29T2:0:0',
              }),
          flake_issue4.key:
              Issue({
                  'id': '67894',
                  'status': 'Fixed',
                  'closed': '2018-12-10T0:0:0',
              })
      }
      return issue_id_to_monorail_issue[flake_issue.key]

    mock_get_merged_issue.side_effect = MockedGetmergedIssue

    flake_groups_without_issue, flake_groups_with_issue = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs(flake_tuples_to_report))

    self.assertItemsEqual([
        flake_group1.ToDict(),
        flake_group2.ToDict(),
        flake_group3.ToDict(),
        flake_group7.ToDict()
    ], [group.ToDict() for group in flake_groups_without_issue])

    self.assertItemsEqual(
        [flake_group4.ToDict(),
         flake_group5.ToDict(),
         flake_group6.ToDict()],
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

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 2))
  @mock.patch.object(
      monorail_util,
      'GetMonorailIssueForIssueId',
      return_value=Issue({
          'status': 'Untriaged',
          'priority': 1,
          'updated': '2018-12-07T17:52:45',
          'id': '234567',
      }))
  @mock.patch.object(monorail_util, 'CreateBug', return_value=234567)
  @mock.patch.object(monorail_util, 'PostCommentOnMonorailBug')
  def testCreateIssueForAGroup(self, mock_first_comment, mock_create_bug, *_):
    flake1 = self._CreateFlake('s1', 'suite1.t1', 'suite1.t1')
    flake1.tags.append('component::Blink')
    flake1.put()
    occurrences1 = [
        self._CreateFlakeOccurrence(1, 's1', 'suite1.t1', 12345, flake1.key),
        self._CreateFlakeOccurrence(2, 's1', 'suite1.t1', 12346, flake1.key)
    ]
    flake2 = self._CreateFlake('s1', 'suite1.t2', 'suite1.t2')
    occurrences2 = [
        self._CreateFlakeOccurrence(1, 's1', 'suite1.t2', 12345, flake2.key),
        self._CreateFlakeOccurrence(2, 's1', 'suite1.t2', 12346, flake2.key)
    ]
    flake_group = flake_issue_util.FlakeGroupByOccurrences(flake1, occurrences1)
    flake_group.AddFlakeIfBelong(flake2, occurrences2)

    flake_issue_util._CreateIssuesForFlakes([flake_group], 30)

    flake_issue = flake_issue_util.GetFlakeIssue(flake1)
    self.assertEqual(234567, flake_issue.issue_id)
    self.assertEqual(
        datetime.datetime(2018, 1, 2),
        flake_issue.last_updated_time_by_flake_detection)
    self.assertTrue(mock_first_comment.called)

    expected_labels = [
        'Type-Bug', 'Test-Flaky', 'Test-Findit-Detected', 'Pri-1',
        'Sheriff-Chromium'
    ]
    issue = mock_create_bug.call_args_list[0][0][0]
    self.assertEqual(['Blink'], issue.components)
    self.assertItemsEqual(expected_labels, issue.labels)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 2))
  @mock.patch.object(
      monorail_util,
      'GetMonorailIssueForIssueId',
      return_value=Issue({
          'status': 'Untriaged',
          'priority': 1,
          'updated': '2018-12-07T17:52:45',
          'id': '234567',
      }))
  @mock.patch.object(monorail_util, 'CreateBug')
  def testNotCreateIssueForAGroupIfReachLimit(self, mock_create_bug, *_):
    flake1 = self._CreateFlake('s1', 'suite1.t1', 'suite1.t1')
    flake1.tags.append('component::Blink')
    flake1.put()
    occurrences1 = [
        self._CreateFlakeOccurrence(1, 's1', 'suite1.t1', 12345, flake1.key),
        self._CreateFlakeOccurrence(2, 's1', 'suite1.t1', 12346, flake1.key)
    ]
    flake2 = self._CreateFlake('s1', 'suite1.t2', 'suite1.t2')
    occurrences2 = [
        self._CreateFlakeOccurrence(1, 's1', 'suite1.t2', 12345, flake2.key),
        self._CreateFlakeOccurrence(2, 's1', 'suite1.t2', 12346, flake2.key)
    ]
    flake_group = flake_issue_util.FlakeGroupByOccurrences(flake1, occurrences1)
    flake_group.AddFlakeIfBelong(flake2, occurrences2)

    flake_issue_util._CreateIssuesForFlakes([flake_group], 0)

    self.assertFalse(mock_create_bug.called)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 2))
  @mock.patch.object(monorail_util, 'UpdateIssueWithIssueGenerator')
  def testUpdateIssueForAGroup(self, *_):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=56789)
    flake_issue.put()
    flake5 = self._CreateFlake('s2', 'suite2.t5', 'suite2.t5')
    flake5.flake_issue_key = flake_issue.key
    flake5.put()
    occurrences5 = [
        self._CreateFlakeOccurrence(1, 's2', 'suite2.t4', 12345, flake5.key),
        self._CreateFlakeOccurrence(2, 's2', 'suite2.t4', 12346, flake5.key)
    ]
    # Old flake, with same issue as flake5.
    flake6 = self._CreateFlake('s3', 'suite3.t6', 'suite3.t6')
    flake6.flake_issue_key = flake_issue.key
    flake6.put()
    occurrences6 = [
        self._CreateFlakeOccurrence(3, 's3', 'suite3.t6', 34467, flake6.key),
        self._CreateFlakeOccurrence(4, 's3', 'suite3.t6', 35546, flake6.key),
        self._CreateFlakeOccurrence(5, 's3', 'suite3.t6', 67543, flake6.key)
    ]
    flake_group = flake_issue_util.FlakeGroupByFlakeIssue(
        flake_issue, flake5, occurrences5, flake_issue)
    flake_group.AddFlakeIfBelong(flake6, occurrences6)

    flake_issue_util._UpdateIssuesForFlakes([flake_group])
    flake_issue = flake_issue_util.GetFlakeIssue(flake6)
    self.assertEqual(
        datetime.datetime(2018, 1, 2),
        flake_issue.last_updated_time_by_flake_detection)

  def testUpdateFlakeIssueWithMonorailIssue(self):
    flake_issue = FlakeIssue.Create('chromium', 1)
    flake_issue.put()
    monorail_issue = Issue({
        'id': '1',
        'labels': ['Type-Bug', 'Pri-2'],
        'status': 'Assigned',
        'updated': '2018-12-10T0:0:0',
    })

    flake_issue_util._UpdateFlakeIssueWithMonorailIssue(flake_issue,
                                                        monorail_issue)
    self.assertEqual('Assigned', flake_issue.status)
    self.assertEqual(
        datetime.datetime(2018, 12, 10),
        flake_issue.last_updated_time_in_monorail)
    self.assertEqual(['Type-Bug', 'Pri-2'], flake_issue.labels)

  def testGetOrCreateFlakeIssueExisting(self):
    flake_issue = FlakeIssue.Create('chromium', 1)
    flake_issue.put()
    self.assertEqual(flake_issue,
                     flake_issue_util._GetOrCreateFlakeIssue(1, 'chromium'))

  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  def testGetOrCreateFlakeIssueNewIssue(self, mocked_issue):
    mocked_issue.return_value = Issue({
        'id': '2',
        'labels': ['Type-Bug', 'Pri-2'],
        'status': 'Assigned',
        'updated': '2018-12-10T0:0:0',
    })
    expected_flake_issue = FlakeIssue.Create('chromium', 2)
    expected_flake_issue.status = 'Assigned'
    expected_flake_issue.last_updated_time_in_monorail = datetime.datetime(
        2018, 12, 10)
    expected_flake_issue.labels = ['Type-Bug', 'Pri-2']

    self.assertEqual(expected_flake_issue,
                     flake_issue_util._GetOrCreateFlakeIssue(2, 'chromium'))

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

  def testGetIssueStatusesNeedingUpdating(self):
    self.assertEqual([
        None, 'Assigned', 'Available', 'ExternalDependency', 'Started',
        'Unconfirmed', 'Untriaged'
    ], flake_issue_util._GetIssueStatusesNeedingUpdating())

  def testGetFlakeIssuesNeedingUpdating(self):
    open_flake_issue = FlakeIssue.Create('chromium', 1)
    open_flake_issue.status = 'Assigned'
    open_flake_issue.put()

    closed_flake_issue = FlakeIssue.Create('chromium', 2)
    closed_flake_issue.status = 'Verified'
    closed_flake_issue.put()

    self.assertEqual([open_flake_issue],
                     flake_issue_util._GetFlakeIssuesNeedingUpdating())

  @mock.patch.object(monorail_util, 'GetMonorailIssueForIssueId')
  @mock.patch.object(monorail_util, 'GetMergedDestinationIssueForId')
  def testSyncOpenFlakeIssuesWithMonorail(self, mocked_merged_issue,
                                          mocked_issue):
    # Scenario:
    # 1. FlakeIssue 1 is a duplicate of FlakeIssue 2, and already has
    #    |merge_destination_key| pointing to 2.
    # 2. FlakeIssue 2 status is 'Available'.
    # 3. Bug 2 in monorail was manually merged into bug 3, which is to be
    #    detected and updated accordingly.
    # 4. FlakeIssue 4 is closed, should detach it from flakes.
    #
    # Expected result:
    # 1. FlakeIssue 3 is created and set to 'Assigned'.
    # 2. FlakeIssue 2's status is set to 'Duplicate'.
    # 3. FlakeIssue 2's |merge_destination_key| is set to FlakeIssue3's key.
    # 4. FlakeIssue 1's |merge_destination_key| is set to FlakeIssue3's key.
    # 5. Flakes link to FlakeIssue 4 now link to no FlakeIssue.

    # |flake_issue_2| is what's active according to Findit, but is out of date
    # with Monorail.
    flake_issue_2 = FlakeIssue.Create('chromium', 2)
    flake_issue_2.status = 'Available'
    flake_issue_2.put()

    # |flake_issue_1| was previously updated to be a duplicate of
    # |flake_issue_2|, but that too is now outdated.
    flake_issue_1 = FlakeIssue.Create('chromium', 1)
    flake_issue_1.status = 'Duplicate'
    flake_issue_1.merge_destination_key = flake_issue_2.key
    flake_issue_1.put()

    flake_issue_4 = FlakeIssue.Create('chromium', 4)
    flake_issue_4.status = 'Started'
    flake_issue_4.put()

    flake = self._CreateFlake('s', 'suite.t1', 'suite.t2')
    flake.flake_issue_key = flake_issue_4.key
    flake.put()

    expected_labels = ['Type-Bug', 'Pri-2']
    expected_last_updated_time = datetime.datetime(2018, 12, 10)

    monorail_issue_2 = Issue({
        'id': '2',
        'labels': expected_labels,
        'merged_into': '3',
        'status': 'Duplicate',
        'updated': '2018-12-10T0:0:0',
    })

    monorail_issue_3 = Issue({
        'id': '3',
        'labels': expected_labels,
        'status': 'Assigned',
        'updated': '2018-12-10T0:0:0',
    })

    monorail_issue_4 = Issue({
        'id': '4',
        'labels': expected_labels,
        'status': 'Fixed',
        'closed': '2018-12-10T0:0:0',
    })

    def MockedGetMonorailIssueForIssueId(issue_id, _):
      issue_id_to_monorail_issue = {
          2: monorail_issue_2,
          3: monorail_issue_3,
          4: monorail_issue_4
      }
      return issue_id_to_monorail_issue[issue_id]

    mocked_issue.side_effect = MockedGetMonorailIssueForIssueId
    mocked_merged_issue.return_value = monorail_issue_3

    flake_issue_util.SyncOpenFlakeIssuesWithMonorail()
    flake_issue_1 = flake_issue_1.key.get()
    flake_issue_2 = flake_issue_2.key.get()
    flake_issue_3 = FlakeIssue.Get('chromium', 3)

    self.assertEqual(flake_issue_1.merge_destination_key, flake_issue_3.key)

    self.assertEqual(expected_last_updated_time,
                     flake_issue_2.last_updated_time_in_monorail)
    self.assertEqual('Duplicate', flake_issue_2.status)
    self.assertEqual(expected_labels, flake_issue_2.labels)
    self.assertEqual(flake_issue_3.key, flake_issue_2.merge_destination_key)

    self.assertIsNotNone(flake_issue_3)
    self.assertEqual('Assigned', flake_issue_3.status)
    self.assertEqual(expected_labels, flake_issue_3.labels)
    self.assertEqual(expected_last_updated_time,
                     flake_issue_3.last_updated_time_in_monorail)

    flake_issue_4 = FlakeIssue.Get('chromium', 4)
    self.assertEqual('Fixed', flake_issue_4.status)
    flake = Flake.Get('chromium', 's', 'suite.t1')
    self.assertEqual(flake_issue_4.key, flake.flake_issue_key)
    self.assertTrue(flake.archived)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 12, 20))
  def testGetRemainingPreAnalysisDailyBugUpdatesCount(self, _):
    self.UpdateUnitTestConfigSettings(
        'action_settings', {'max_flake_detection_bug_updates_per_day': 5})
    flake_issue_1 = FlakeIssue.Create('chromium', 12345)
    flake_issue_1.last_updated_time_by_flake_detection = datetime.datetime(
        2018, 12, 19, 12, 1, 0)  # Updated within 24 hours, counts.
    flake_issue_1.put()
    flake_issue_2 = FlakeIssue.Create('chromium', 12346)
    flake_issue_2.last_updated_time_by_flake_detection = datetime.datetime(
        2018, 12, 19, 0, 0, 0)  # Updated exactly 24 ago, doesn't count.'
    flake_issue_2.put()
    flake_issue_3 = FlakeIssue.Create('chromium', 12347)
    flake_issue_3.last_updated_time_by_flake_detection = datetime.datetime(
        2018, 12, 18, 12, 0, 0)  # Over 24 hours old, doesn't count.'
    flake_issue_3.put()
    self.assertEqual(
        4, flake_issue_util.GetRemainingPreAnalysisDailyBugUpdatesCount())

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 12, 20))
  def testGetRemainingPostAnalysisDailyBugUpdatesCount(self, _):
    self.UpdateUnitTestConfigSettings(
        'action_settings', {'max_flake_analysis_bug_updates_per_day': 5})
    flake_issue_1 = FlakeIssue.Create('chromium', 12345)
    flake_issue_1.last_updated_time_with_analysis_results = datetime.datetime(
        2018, 12, 19, 1, 0, 0)  # Updated within 24 hours, counts.
    flake_issue_1.put()
    flake_issue_2 = FlakeIssue.Create('chromium', 12346)
    flake_issue_2.last_updated_time_with_analysis_results = datetime.datetime(
        2018, 12, 19, 0, 0, 0)  # Updated exaxstly 24 hours ago, doesn't count.
    flake_issue_2.put()
    flake_issue_3 = FlakeIssue.Create('chromium', 12347)
    flake_issue_3.last_updated_time_with_analysis_results = datetime.datetime(
        2018, 12, 18, 12, 0, 0)  # Over 24 hours old, doesn't count.'
    flake_issue_3.put()
    self.assertEqual(
        4, flake_issue_util.GetRemainingPostAnalysisDailyBugUpdatesCount())

  @mock.patch.object(
      time_util,
      'GetDateDaysBeforeNow',
      return_value=datetime.datetime(2019, 1, 1))
  def testIsFlakeIssueActionable(self, _):
    flake_issue = FlakeIssue.Create('chromium', 12367)
    flake_issue.put()
    self.assertEqual(True, flake_issue_util.IsFlakeIssueActionable(flake_issue))

    flake_issue.status = 'Assigned'
    flake_issue.put()
    self.assertEqual(True, flake_issue_util.IsFlakeIssueActionable(flake_issue))

    flake_issue.status = 'Fixed'
    flake_issue.last_updated_time_in_monorail = datetime.datetime(2019, 1, 5)
    flake_issue.put()
    self.assertEqual(True, flake_issue_util.IsFlakeIssueActionable(flake_issue))

    flake_issue.last_updated_time_in_monorail = datetime.datetime(2018, 1, 5)
    flake_issue.put()
    self.assertEqual(False,
                     flake_issue_util.IsFlakeIssueActionable(flake_issue))
