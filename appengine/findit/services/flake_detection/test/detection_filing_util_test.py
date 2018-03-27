# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
import mock
import datetime

from libs import time_util
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.detection.flake_occurrence import FlakeType
from model.flake.detection.flake_issue import FlakeIssue
from services import issue_tracking_service
from services.flake_detection import detection_filing_util
from waterfall.test import wf_testcase


class DetectionFilingUtilTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  def testHasFlakeDetectionUpdateLimitBeenReached(self, _):
    now = time_util.GetUTCNow()
    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=1)).put()
    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=2)).put()
    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=3)).put()
    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=4)).put()
    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=5)).put()
    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=6)).put()
    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=7)).put()
    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=8)).put()
    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=9)).put()
    self.assertFalse(
        detection_filing_util.HasFlakeDetectionUpdateLimitBeenReached())

    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=25)).put()
    self.assertFalse(
        detection_filing_util.HasFlakeDetectionUpdateLimitBeenReached())

    FlakeIssue(last_updated_time=now - datetime.timedelta(hours=23)).put()
    self.assertTrue(
        detection_filing_util.HasFlakeDetectionUpdateLimitBeenReached())

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  def testGetTotalRecentFlakeOccurrences(self, _):
    step_name = 's'
    test_name = 't'
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    build_id = 1
    flake_type = FlakeType.CQ_FALSE_REJECTION

    now = time_util.GetUTCNow()
    flake = Flake.Create(step_name, test_name)
    flake.put()

    fo = FlakeOccurrence.Create(
        step_name=step_name,
        test_name=test_name,
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=now - datetime.timedelta(hours=1),
        flake_type=flake_type).put()
    FlakeOccurrence.Create(
        step_name=step_name,
        test_name=test_name,
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=now - datetime.timedelta(hours=2),
        flake_type=flake_type).put()
    FlakeOccurrence.Create(
        step_name=step_name,
        test_name=test_name,
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=now - datetime.timedelta(hours=3),
        flake_type=flake_type).put()
    FlakeOccurrence.Create(
        step_name=step_name,
        test_name=test_name,
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=now - datetime.timedelta(hours=25),
        flake_type=flake_type).put()

    self.assertEqual(
        detection_filing_util.GetTotalRecentFlakeOccurrences(
            flake, delta=datetime.timedelta(hours=10)), 3)

    fo.delete()
    self.assertEqual(
        detection_filing_util.GetTotalRecentFlakeOccurrences(flake), 2)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  def testFlakeHasEnoughOccurrencesToFileBugCQRejection(self, _):
    step_name = 's'
    test_name = 't'
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    build_id = 1
    flake_type = FlakeType.CQ_FALSE_REJECTION
    now = time_util.GetUTCNow()

    flake = Flake.Create(step_name, test_name)
    flake.put()

    self.assertFalse(
        detection_filing_util.FlakeHasEnoughOccurrencesToFileBug(flake))

    FlakeOccurrence.Create(
        step_name=step_name,
        test_name=test_name,
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=now - datetime.timedelta(hours=1),
        flake_type=flake_type).put()
    FlakeOccurrence.Create(
        step_name=step_name,
        test_name=test_name,
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=now - datetime.timedelta(hours=2),
        flake_type=flake_type).put()
    FlakeOccurrence.Create(
        step_name=step_name,
        test_name=test_name,
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=now - datetime.timedelta(hours=3),
        flake_type=flake_type).put()

    self.assertTrue(
        detection_filing_util.FlakeHasEnoughOccurrencesToFileBug(flake))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  def testFlakeHasEnoughOccurrencesToFileBugOutrightFlake(self, _):
    step_name = 's'
    test_name = 't'
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    build_id = 1
    flake_type = FlakeType.OUTRIGHT_FLAKE
    now = time_util.GetUTCNow()

    flake = Flake.Create(step_name, test_name)
    flake.put()

    self.assertFalse(
        detection_filing_util.FlakeHasEnoughOccurrencesToFileBug(flake))

    FlakeOccurrence.Create(
        step_name=step_name,
        test_name=test_name,
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=now - datetime.timedelta(hours=1),
        flake_type=flake_type).put()

    self.assertTrue(
        detection_filing_util.FlakeHasEnoughOccurrencesToFileBug(flake))

  @mock.patch.object(issue_tracking_service, 'GetExistingBugForCustomizedField')
  def testUpdateFlakeWithExistingBug(self, mock_get_bug_fn):
    issue_id = '100'

    mock_bug = mock.Mock()
    mock_bug.id = issue_id
    mock_get_bug_fn.return_value = mock_bug

    flake = Flake()
    detection_filing_util.UpdateFlakeWithExistingBug(flake)
    self.assertEqual(flake.flake_issue.issue_id, issue_id)

  @mock.patch.object(issue_tracking_service, 'GetExistingBugForCustomizedField')
  def testUpdateFlakeWithExistingBugNoExistingBug(self, mock_get_bug_fn):
    mock_get_bug_fn.return_value = None

    flake = Flake()
    detection_filing_util.UpdateFlakeWithExistingBug(flake)
    self.assertIsNone(flake.flake_issue)

  @mock.patch.object(issue_tracking_service, 'GetExistingBugForCustomizedField')
  def testUpdateFlakeWithExistingBugWithAlreadyExistingFlakeIssue(
      self, mock_get_bug_fn):
    issue_id = '100'

    mock_bug = mock.Mock()
    mock_bug.id = issue_id
    mock_get_bug_fn.return_value = mock_bug

    flake = Flake()
    flake.flake_issue = FlakeIssue()
    flake.flake_issue.id = '200'
    detection_filing_util.UpdateFlakeWithExistingBug(flake)
    self.assertNotEqual(flake.flake_issue.issue_id, issue_id)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  def testHasExistingFlakeBugBeenUpdated(self, mock_get_bug_fn, _):
    now = time_util.GetUTCNow()
    issue_id = '100'

    flake = Flake()
    flake.flake_issue = FlakeIssue()
    flake.flake_issue.issue_id = issue_id
    flake.put()

    mock_bug = mock.Mock()
    mock_bug.open = True
    mock_bug.updated = now - datetime.timedelta(hours=20)
    mock_get_bug_fn.return_value = mock_bug

    self.assertTrue(detection_filing_util.HasExistingFlakeBugBeenUpdated(flake))
    mock_get_bug_fn.assert_called_with(issue_id)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  def testHasExistingFlakeBugBeenUpdatedBugClosedButUpdated(
      self, mock_get_bug_fn, _):
    now = time_util.GetUTCNow()
    issue_id = '100'

    flake = Flake()
    flake.flake_issue = FlakeIssue()
    flake.flake_issue.issue_id = issue_id
    flake.put()

    mock_bug = mock.Mock()
    mock_bug.open = False
    mock_bug.updated = now - datetime.timedelta(hours=20)
    mock_get_bug_fn.return_value = mock_bug

    self.assertTrue(detection_filing_util.HasExistingFlakeBugBeenUpdated(flake))
    mock_get_bug_fn.assert_called_with(issue_id)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  def testHasExistingFlakeBugBeenUpdatedBugClosedNotUpdated(
      self, mock_get_bug_fn, _):
    now = time_util.GetUTCNow()
    issue_id = '100'

    flake = Flake()
    flake.flake_issue = FlakeIssue()
    flake.flake_issue.issue_id = issue_id
    flake.put()

    mock_bug = mock.Mock()
    mock_bug.open = False
    mock_bug.updated = now - datetime.timedelta(hours=40)
    mock_get_bug_fn.return_value = mock_bug

    self.assertFalse(
        detection_filing_util.HasExistingFlakeBugBeenUpdated(flake))
    mock_get_bug_fn.assert_called_with(issue_id)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 1, 1))
  @mock.patch.object(issue_tracking_service, 'GetBugForId')
  def testHasExistingFlakeBugBeenUpdatedNoFlakeIssue(self, mock_get_bug_fn, _):
    flake = Flake()
    flake.put()

    self.assertFalse(
        detection_filing_util.HasExistingFlakeBugBeenUpdated(flake))
    mock_get_bug_fn.assert_not_called()

  @mock.patch.object(
      detection_filing_util,
      'HasFlakeDetectionUpdateLimitBeenReached',
      return_value=False)
  @mock.patch.object(
      detection_filing_util,
      'FlakeHasEnoughOccurrencesToFileBug',
      return_value=True)
  @mock.patch.object(detection_filing_util, 'UpdateFlakeWithExistingBug')
  @mock.patch.object(
      detection_filing_util,
      'HasExistingFlakeBugBeenUpdated',
      return_value=False)
  @mock.patch.object(
      detection_filing_util, 'GetTotalRecentFlakeOccurrences', return_value=10)
  @mock.patch.object(issue_tracking_service, 'CreateBugForDetectedFlake')
  def testCheckAndFileBugForDetectedFlakeCreate(self, create_bug_fn, *_):
    flake = Flake()
    flake.put()

    detection_filing_util.CheckAndFileBugForDetectedFlake(flake.key.urlsafe())
    create_bug_fn.assert_called_with(flake, 10, old_bug_id=None)

  @mock.patch.object(
      detection_filing_util,
      'HasFlakeDetectionUpdateLimitBeenReached',
      return_value=False)
  @mock.patch.object(
      detection_filing_util,
      'FlakeHasEnoughOccurrencesToFileBug',
      return_value=True)
  @mock.patch.object(detection_filing_util, 'UpdateFlakeWithExistingBug')
  @mock.patch.object(
      detection_filing_util, 'GetTotalRecentFlakeOccurrences', return_value=10)
  @mock.patch.object(
      detection_filing_util,
      'HasExistingFlakeBugBeenUpdated',
      return_value=False)
  @mock.patch.object(issue_tracking_service, 'CreateBugForDetectedFlake')
  def testCheckAndFileBugForDetectedFlakeCreateWithOldBug(
      self, create_bug_fn, has_existing_bug_fn, *_):
    issue_id = '100'

    flake = Flake()
    flake.flake_issue = FlakeIssue()
    flake.flake_issue.issue_id = issue_id
    flake.put()

    def remove_flake_issue_side_effect(flake):
      flake.flake_issue = None

    has_existing_bug_fn.side_effect = remove_flake_issue_side_effect

    detection_filing_util.CheckAndFileBugForDetectedFlake(flake.key.urlsafe())
    create_bug_fn.assert_called_with(flake, 10, old_bug_id=issue_id)

  @mock.patch.object(
      detection_filing_util,
      'HasFlakeDetectionUpdateLimitBeenReached',
      return_value=False)
  @mock.patch.object(
      detection_filing_util,
      'FlakeHasEnoughOccurrencesToFileBug',
      return_value=True)
  @mock.patch.object(detection_filing_util, 'UpdateFlakeWithExistingBug')
  @mock.patch.object(
      detection_filing_util,
      'HasExistingFlakeBugBeenUpdated',
      return_value=False)
  @mock.patch.object(
      detection_filing_util, 'GetTotalRecentFlakeOccurrences', return_value=10)
  @mock.patch.object(issue_tracking_service, 'UpdateBugForDetectedFlake')
  def testCheckAndFileBugForDetectedFlakeUpdate(self, update_bug_fn, *_):
    issue_id = '100'

    flake = Flake()
    flake.flake_issue = FlakeIssue()
    flake.flake_issue.issue_id = issue_id
    flake.put()

    detection_filing_util.CheckAndFileBugForDetectedFlake(flake.key.urlsafe())
    update_bug_fn.assert_called_with(flake, 10)

  @mock.patch.object(
      detection_filing_util,
      'FlakeHasEnoughOccurrencesToFileBug',
      return_value=True)
  @mock.patch.object(detection_filing_util, 'UpdateFlakeWithExistingBug')
  @mock.patch.object(
      detection_filing_util,
      'HasExistingFlakeBugBeenUpdated',
      return_value=False)
  @mock.patch.object(
      detection_filing_util,
      'HasFlakeDetectionUpdateLimitBeenReached',
      return_value=True)
  def testCheckAndFileBugForDetectedFlakeUpdateLimitReached(
      self, limit_reached_fn, *_):
    flake = Flake()
    flake.put()
    detection_filing_util.CheckAndFileBugForDetectedFlake(flake.key.urlsafe())
    limit_reached_fn.assert_called()

  @mock.patch.object(detection_filing_util, 'UpdateFlakeWithExistingBug')
  @mock.patch.object(
      detection_filing_util,
      'HasExistingFlakeBugBeenUpdated',
      return_value=False)
  @mock.patch.object(
      detection_filing_util,
      'HasFlakeDetectionUpdateLimitBeenReached',
      return_value=False)
  @mock.patch.object(
      detection_filing_util,
      'FlakeHasEnoughOccurrencesToFileBug',
      return_value=False)
  def testCheckAndFileBugForDetectedFlakeNotEnoughOccurrences(
      self, enough_occurrences_fn, *_):
    flake = Flake()
    flake.put()
    detection_filing_util.CheckAndFileBugForDetectedFlake(flake.key.urlsafe())
    enough_occurrences_fn.assert_called_with(flake)

  @mock.patch.object(
      detection_filing_util,
      'HasFlakeDetectionUpdateLimitBeenReached',
      return_value=False)
  @mock.patch.object(
      detection_filing_util,
      'FlakeHasEnoughOccurrencesToFileBug',
      return_value=True)
  @mock.patch.object(detection_filing_util, 'UpdateFlakeWithExistingBug')
  @mock.patch.object(
      detection_filing_util,
      'HasExistingFlakeBugBeenUpdated',
      return_value=True)
  def testCheckAndFileBugForDetectedFlakeExistingBug(
      self, has_existing_bug_been_updated_fn, *_):
    flake = Flake()
    flake.put()
    detection_filing_util.CheckAndFileBugForDetectedFlake(flake.key.urlsafe())
    has_existing_bug_been_updated_fn.assert_called_with(flake)
