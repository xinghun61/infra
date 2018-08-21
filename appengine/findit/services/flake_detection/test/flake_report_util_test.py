# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import mock

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

  @mock.patch.object(issue_tracking_service, 'CreateBugForFlakeDetection')
  def testCreateIssueForFlake(self, mock_create_bug_fn):
    mock_create_bug_fn.return_value = 12345

    flake = Flake.query().fetch()[0]
    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    flake_report_util.CreateIssueForFlake(
        flake=flake, occurrences=occurrences, previous_tracking_bug_id=56789)

    expected_flake_url = (
        'https://findit-for-me.appspot.com/flake/detection/show-flake?key=%s'
    ) % flake.key.urlsafe()
    mock_create_bug_fn.assert_called_once_with(
        normalized_step_name='step',
        normalized_test_name='test',
        num_occurrences=3,
        monorail_project='chromium',
        flake_url=expected_flake_url,
        previous_tracking_bug_id=56789)

    flake_issue = flake.flake_issue_key.get()
    self.assertEqual(12345, flake_issue.issue_id)
    self.assertEqual('chromium', flake_issue.monorail_project)
    self.assertIsNotNone(flake_issue.last_updated_time)

  @mock.patch.object(issue_tracking_service, 'UpdateBugForFlakeDetection')
  def testUpdateIssueForFlake(self, mock_update_bug_fn):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    flake_report_util.UpdateIssueForFlake(
        flake=flake, occurrences=occurrences, previous_tracking_bug_id=56789)

    expected_flake_url = (
        'https://findit-for-me.appspot.com/flake/detection/show-flake?key=%s'
    ) % flake.key.urlsafe()
    mock_update_bug_fn.assert_called_once_with(
        bug_id=12345,
        normalized_test_name='test',
        num_occurrences=3,
        monorail_project='chromium',
        flake_url=expected_flake_url,
        previous_tracking_bug_id=56789)

    flake_issue = flake.flake_issue_key.get()
    self.assertEqual(
        datetime.datetime(2018, 1, 2), flake_issue.last_updated_time)

  # This test tests that if a flake has a flake issue attached and the bug is
  # open (not merged) on Monorail, then should directly update that bug with
  # new occurrences.
  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  @mock.patch.object(flake_report_util, 'UpdateIssueForFlake')
  @mock.patch.object(flake_report_util, 'CreateIssueForFlake')
  def testReportFlakeHasFlakeIssueAndBugIsOpen(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_bug_for_id):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_get_bug_for_id.return_value.id = 12345
    mock_get_bug_for_id.return_value.open = True

    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    flake_tuples_to_report = [(flake, occurrences)]
    flake_report_util.ReportFlakesToMonorail(flake_tuples_to_report)

    mock_create_bug_fn.assert_not_called()
    mock_update_bug_fn.assert_called_once_with(flake, occurrences, None)

  # This test tests that if a flake has a flake issue attached, but the bug was
  # merged to another bug, and that destination bug is open on Monorail, then
  # should update the destination bug with new occurrences.
  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  @mock.patch.object(flake_report_util, 'UpdateIssueForFlake')
  @mock.patch.object(flake_report_util, 'CreateIssueForFlake')
  def testReportFlakeHasFlakeIssueAndBugWasMergedToAnOpenBug(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_bug_for_id):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_issue = mock.Mock()
    mock_get_bug_for_id.return_value = mock_issue
    mock_issue.id = 66666
    mock_issue.open = True

    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    flake_tuples_to_report = [(flake, occurrences)]
    flake_report_util.ReportFlakesToMonorail(flake_tuples_to_report)

    self.assertEqual(66666, flake.flake_issue_key.get().issue_id)
    mock_create_bug_fn.assert_not_called()
    mock_update_bug_fn.assert_called_once_with(flake, occurrences, 12345)

  # This test tests that if a flake has a flake issue attached, but the bug was
  # merged to another bug, and that destination bug is closed on Monorail, then
  # should create a new bug with new occurrences.
  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  @mock.patch.object(flake_report_util, 'UpdateIssueForFlake')
  @mock.patch.object(flake_report_util, 'CreateIssueForFlake')
  def testReportFlakeHasFlakeIssueAndBugWasMergedToAClosedBug(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_get_bug_for_id):
    flake = Flake.query().fetch()[0]
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=12345)
    flake_issue.put()
    flake.flake_issue_key = flake_issue.key
    flake.put()

    mock_issue = mock.Mock()
    mock_get_bug_for_id.return_value = mock_issue
    mock_issue.id = 66666
    mock_issue.open = False

    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    flake_tuples_to_report = [(flake, occurrences)]
    flake_report_util.ReportFlakesToMonorail(flake_tuples_to_report)

    self.assertEqual(66666, flake.flake_issue_key.get().issue_id)
    mock_create_bug_fn.assert_called_once_with(flake, occurrences, 66666)
    mock_update_bug_fn.assert_not_called()

  # This test tests that if a flake has no flake issue attached, but find an
  # existing bug about this flaky test on this Monorail, then should attach that
  # bug to this flake and update it with new occurrences.
  @mock.patch.object(
      issue_tracking_service,
      'SearchOpenIssueIdForFlakyTest',
      return_value=56789)
  @mock.patch.object(flake_report_util, 'UpdateIssueForFlake')
  @mock.patch.object(flake_report_util, 'CreateIssueForFlake')
  def testReportFlakeHasNoFlakeIssueAndFindAnExistingOpenBug(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_search_issue):
    flake = Flake.query().fetch()[0]
    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    flake_tuples_to_report = [(flake, occurrences)]
    flake_report_util.ReportFlakesToMonorail(flake_tuples_to_report)

    self.assertTrue(flake.flake_issue_key)
    self.assertEqual(56789, flake.flake_issue_key.get().issue_id)
    mock_create_bug_fn.assert_not_called()
    mock_update_bug_fn.assert_called_once_with(flake, occurrences, None)
    mock_search_issue.assert_called_once_with(flake.normalized_test_name,
                                              'chromium')

  # This test tests that if a flake has no flake issue attached, and couldn't
  # find an existing bug about this flaky test on this Monorail, then should
  # attach that bug to this flake and update it with new occurrences.
  @mock.patch.object(
      issue_tracking_service,
      'SearchOpenIssueIdForFlakyTest',
      return_value=None)
  @mock.patch.object(flake_report_util, 'UpdateIssueForFlake')
  @mock.patch.object(flake_report_util, 'CreateIssueForFlake')
  def testReportFlakeHasNoFlakeIssueAndCantFindAnExistingOpenBug(
      self, mock_create_bug_fn, mock_update_bug_fn, mock_search_issue):
    flake = Flake.query().fetch()[0]
    occurrences = CQFalseRejectionFlakeOccurrence.query().fetch()
    flake_tuples_to_report = [(flake, occurrences)]
    flake_report_util.ReportFlakesToMonorail(flake_tuples_to_report)

    mock_create_bug_fn.assert_called_once_with(flake, occurrences, None)
    mock_update_bug_fn.assert_not_called()
    mock_search_issue.assert_called_once_with(flake.normalized_test_name,
                                              'chromium')