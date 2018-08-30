# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import mock
import textwrap

from googleapiclient.errors import HttpError
from libs import time_util
from model.flake.detection.flake import Flake
from model.flake.detection.flake_issue import FlakeIssue
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from services import issue_tracking_service
from services.flake_detection import flake_report_util
from services.flake_detection.flake_report_util import (
    GetFlakesNeedToReportToMonorail)
from waterfall.test.wf_testcase import WaterfallTestCase


class FlakeReportUtilTest(WaterfallTestCase):

  def _CreateFlake(self, normalized_step_name, normalized_test_name):
    flake = Flake.Create(
        luci_project='chromium',
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)
    flake.put()
    return flake

  def _CreateFlakeOccurrence(self, build_id, step_name, test_name, gerrit_cl_id,
                             parent_flake_key):
    flake_occurrence = CQFalseRejectionFlakeOccurrence.Create(
        build_id=build_id,
        step_name=step_name,
        test_name=test_name,
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=parent_flake_key,
        luci_project='chromium',
        luci_bucket='try',
        luci_builder='linux_chromium_rel_ng',
        legacy_master_name='tryserver.chromium.linux',
        legacy_build_number=999,
        reference_succeeded_build_id=456,
        time_happened=datetime.datetime.utcnow())
    flake_occurrence.put()

  def _GetDatetimeHoursAgo(self, hours):
    """Returns the utc datetime of some hours ago."""
    return time_util.GetUTCNow() - datetime.timedelta(hours=hours)

  def setUp(self):
    super(FlakeReportUtilTest, self).setUp()
    patcher = mock.patch.object(
        time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 2))
    self.addCleanup(patcher.stop)
    patcher.start()

    flake = self._CreateFlake('step', 'test')
    self._CreateFlakeOccurrence(111, 'step1', 'test1', 98765, flake.key)
    self._CreateFlakeOccurrence(222, 'step2', 'test2', 98764, flake.key)
    self._CreateFlakeOccurrence(333, 'step3', 'test3', 98763, flake.key)

  # This test tests that when all conditions are met, flakes will be reported.
  def testGetFlakesNeedToReportToMonorail(self):
    flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
    self.assertEqual(1, len(flake_tuples_to_report))
    self.assertEqual(3, len(flake_tuples_to_report[0][1]))

  # This test tests that if the number of issues created or updated within the
  # past 24 hours has already reached a limit, then no issues can be created or
  # updated.
  def testCreateOrUpdateIssuesPerDayLimit(self):
    another_flake = self._CreateFlake('another_step', 'another_test')
    self._CreateFlakeOccurrence(111, 'another_step1', 'another_test1', 98765,
                                another_flake.key)
    self._CreateFlakeOccurrence(222, 'another_step2', 'another_test2', 98764,
                                another_flake.key)
    self._CreateFlakeOccurrence(333, 'another_step3', 'another_test3', 98763,
                                another_flake.key)

    with mock.patch.object(flake_report_util,
                           '_CREATE_OR_UPDATE_ISSUES_LIMIT_24H', 0):
      flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
      self.assertEqual(0, len(flake_tuples_to_report))

    with mock.patch.object(flake_report_util,
                           '_CREATE_OR_UPDATE_ISSUES_LIMIT_24H', 1):
      flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
      self.assertEqual(1, len(flake_tuples_to_report))
      self.assertEqual(3, len(flake_tuples_to_report[0][1]))

  # This test tests that in order to report a flake, there needs to be at least
  # some number of occurrences with different CLs, and different patchsets of
  # the same CL are only counted once.
  def testMinimumRequiredFalselyRejectedCLs(self):
    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    for occurrence in occurrences:
      occurrence.gerrit_cl_id = 565656
      occurrence.put()

    flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
    self.assertEqual(0, len(flake_tuples_to_report))

  # This test tests that in order to report a flake, at least one occurrence
  # needs to be within an active flake window.
  @mock.patch.object(flake_report_util, '_ACTIVE_FLAKE_WINDOW_HOURS', 6)
  def testAtLeastOneActiveOccurrence(self):
    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()

    occurrences[0].time_happened = self._GetDatetimeHoursAgo(12)
    occurrences[0].put()
    occurrences[1].time_happened = self._GetDatetimeHoursAgo(12)
    occurrences[1].put()
    occurrences[2].time_happened = self._GetDatetimeHoursAgo(7)
    occurrences[2].put()

    flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
    self.assertEqual(0, len(flake_tuples_to_report))

    occurrences[2].time_happened = self._GetDatetimeHoursAgo(5)
    occurrences[2].put()

    flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
    self.assertEqual(1, len(flake_tuples_to_report))
    self.assertEqual(3, len(flake_tuples_to_report[0][1]))

  # This test tests that occurrences happened more than one day ago are ignored.
  def testIgnoreOutdatedOccurrences(self):
    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    occurrences[2].time_happened = self._GetDatetimeHoursAgo(25)
    occurrences[2].put()

    flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
    self.assertEqual(0, len(flake_tuples_to_report))

  # This test tests that occurrences that were already reported are ignored.
  def testIgnoreAlreadyReportedOccurrences(self):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time = self._GetDatetimeHoursAgo(5)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    occurrences[2].time_detected = self._GetDatetimeHoursAgo(10)
    occurrences[2].put()

    flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
    self.assertEqual(0, len(flake_tuples_to_report))

  # This test tests that the program doesn't crash when a flake has no
  # unreported occurrences.
  def testFlakeHasNoUnreportedOccurrences(self):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time = self._GetDatetimeHoursAgo(5)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    for occurrence in occurrences:
      occurrence.time_detected = self._GetDatetimeHoursAgo(10)
      occurrence.put()

    flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
    self.assertEqual(0, len(flake_tuples_to_report))

  # This test tests that any issue can be created or updated at most once in any
  # 24 hours window.
  def testIssuesCanBeCreatedOrUpdatedAtMostOncePerDay(self):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time = self._GetDatetimeHoursAgo(25)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
    self.assertEqual(1, len(flake_tuples_to_report))
    self.assertEqual(3, len(flake_tuples_to_report[0][1]))

    flake_issue.last_updated_time = self._GetDatetimeHoursAgo(1)
    flake_tuples_to_report = GetFlakesNeedToReportToMonorail()
    self.assertEqual(0, len(flake_tuples_to_report))

  # This test tests that when a flake has no flake issue attached, it creates
  # a new issue and attach it to the flake.
  @mock.patch.object(
      issue_tracking_service,
      'SearchOpenIssueIdForFlakyTest',
      return_value=None)
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'CreateBug', return_value=66666)
  def testReportFlakeToMonorailCreateIssue(self, mock_create_bug_fn,
                                           mock_update_bug_fn, _):
    flake = Flake.query().fetch()[0]
    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    flake_report_util.ReportFlakesToMonorail([(flake, occurrences)])

    expected_status = 'Untriaged'
    expected_summary = 'test is flaky'

    expected_wrong_result_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?status=Unconfirmed&'
        'labels=Pri-1,Test-Findit-Wrong&components=Tools%3ETest%3EFindit%3E'
        'Flakiness&summary=%5BFindit%5D%20Flake%20Detection%20-%20Wrong%20'
        'result%20for%20test&comment=Link%20to%20flake%20occurrences%3A%20'
        'https://findit-for-me.appspot.com/flake/detection/show-flake?key={}'
    ).format(flake.key.urlsafe())

    expected_description = textwrap.dedent("""
step: test is flaky.

Findit has detected 3 flake occurrences of this test within the
past 24 hours. List of all flake occurrences can be found at:
https://findit-for-me.appspot.com/flake/detection/show-flake?key={}.

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
        fetched_flake_issues[0].last_updated_time)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that when a flake has a flake issue attached but the issue
  # was closed, it creates a new issue with a previous tracking issue id and
  # attach it to the flake.
  @mock.patch.object(
      issue_tracking_service,
      'SearchOpenIssueIdForFlakyTest',
      return_value=None)
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'CreateBug', return_value=66666)
  def testReportFlakeToMonorailCreateIssueWithPreviousTrackingBugId(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_merged_issue, _):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()
    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = False

    flake_report_util.ReportFlakesToMonorail([(flake, occurrences)])

    expected_previous_bug_description = (
        '\n\nThis flaky test was previously tracked in bug 12345.\n\n')
    issue = mock_create_bug_fn.call_args_list[0][0][0]
    self.assertIn(expected_previous_bug_description, issue.description)
    self.assertFalse(mock_update_bug_fn.called)

  # This test tests that when a flake has a flake issue attached and the issue
  # is still open, it directly updates the issue.
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testReportFlakeToMonorailUpdateIssue(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_merged_issue):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()
    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    mock_get_merged_issue.return_value.id = 12345
    mock_get_merged_issue.return_value.open = True
    flake_report_util.ReportFlakesToMonorail([(flake, occurrences)])

    expected_wrong_result_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?status=Unconfirmed&'
        'labels=Pri-1,Test-Findit-Wrong&components=Tools%3ETest%3EFindit%3E'
        'Flakiness&summary=%5BFindit%5D%20Flake%20Detection%20-%20Wrong%20'
        'result%20for%20test&comment=Link%20to%20flake%20occurrences%3A%20'
        'https://findit-for-me.appspot.com/flake/detection/show-flake?key={}'
    ).format(flake.key.urlsafe())

    expected_comment = textwrap.dedent("""
Findit has detected 3 new flake occurrences of this test. List
of all flake occurrences can be found at:
https://findit-for-me.appspot.com/flake/detection/show-flake?key={}.

Since this test is still flaky, this issue has been moved back onto the Sheriff
Bug Queue if it's not already there.

If the result above is wrong, please file a bug using this link:
{}

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N)."""
                                      ).format(flake.key.urlsafe(),
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
        fetched_flake_issues[0].last_updated_time)
    self.assertEqual(fetched_flakes[0].flake_issue_key,
                     fetched_flake_issues[0].key)

  # This test tests that when a flake has a flake issue attached and the issue
  # was merged to another open bug, it updates the destination bug with
  # a previous tracking bug id.
  @mock.patch.object(issue_tracking_service, 'GetMergedDestinationIssueForId')
  @mock.patch.object(issue_tracking_service, 'UpdateBug')
  @mock.patch.object(issue_tracking_service, 'CreateBug')
  def testReportFlakeToMonorailUpdateIssueWithPreviousTrackingBugId(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_merged_issue):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()
    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    mock_get_merged_issue.return_value.id = 56789
    mock_get_merged_issue.return_value.open = True
    flake_report_util.ReportFlakesToMonorail([(flake, occurrences)])

    expected_previous_bug_description = (
        '\n\nThis flaky test was previously tracked in bug 12345.\n\n')
    comment = mock_update_bug_fn.call_args_list[0][0][1]
    self.assertIn(expected_previous_bug_description, comment)
    self.assertFalse(mock_create_bug_fn.called)
    self.assertTrue(mock_update_bug_fn.called)

  # This test tests that when Flake Detection tries to create or update multiple
  # bugs, if it encounters failures such as no permissions to update a specific
  # bug, it shouldn't crash, instead, it should move on to next ones.
  @mock.patch.object(issue_tracking_service, 'IssueTrackerAPI')
  def testReportFlakeToMonorailRecoversFromFailures(self,
                                                    mock_issue_tracker_api):
    mock_issue_tracker_api.side_effect = HttpError(
        mock.Mock(status=403), 'Error happened')

    flake1 = Flake.query().fetch()[0]
    occurrences1 = CQFalseRejectionFlakeOccurrence.query(
        ancestor=flake1.key).fetch()
    flake2 = self._CreateFlake('step_other', 'test_other')
    self._CreateFlakeOccurrence(777, 'step1_other', 'test1_other', 54321,
                                flake2.key)
    self._CreateFlakeOccurrence(888, 'step2_other', 'test2_other', 54322,
                                flake2.key)
    self._CreateFlakeOccurrence(999, 'step3_other', 'test3_other', 54323,
                                flake2.key)
    occurrences2 = CQFalseRejectionFlakeOccurrence.query(
        ancestor=flake2.key).fetch()

    flake_report_util.ReportFlakesToMonorail([(flake1, occurrences1),
                                              (flake2, occurrences2)])
