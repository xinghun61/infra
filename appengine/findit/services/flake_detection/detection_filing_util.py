# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import logging

from google.appengine.ext import ndb

from libs import time_util
from model.flake.detection import flake_occurrence
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.detection.flake_occurrence import FlakeType
from model.flake.detection.flake_issue import FlakeIssue
from services import issue_tracking_service

# TODO(crbug.com/815254): Move to config.
# The number of issue allowed to be updated per day.
_MAX_UPDATED_ISSUES_PER_DAY = 10

# TODO(crbug.com/815254): Move to config.
# Threshold for cq false rejection.
_CQ_REJECTION_THRESHOLD = 3

# TODO(crbug.com/815254): Move to config.
# Threshold for outright flake
_OUTRIGHT_FLAKE_THRESHOLD = 1


def HasFlakeDetectionUpdateLimitBeenReached():
  """Check if the daily limit for issue updating has been reached."""
  one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
  num_updates_last_day = FlakeIssue.query(
      FlakeIssue.last_updated_time > one_day_ago).count()
  return num_updates_last_day >= _MAX_UPDATED_ISSUES_PER_DAY


def GetTotalRecentFlakeOccurrences(flake, delta=datetime.timedelta(days=1)):
  """Gets the number of flake occurrences in the past 24H."""
  one_day_ago = time_util.GetUTCNow() - delta
  return len([
      occurrence for occurrence in flake.flake_occurrences
      if occurrence.time_reported > one_day_ago
  ])


def FlakeHasEnoughOccurrencesToFileBug(flake):
  """Returns True if the flake has enough occurrences in the last 24H.

  If the given flake has enough occurrences in the last 24H, returns True. The
  thresholds for the occurrences are different for different types of flakes.

  Args:
    flake (model.flake.detection.flake): The parent flake for the occurrences.
  Returns:
    (boolean) True if the thresholds have been passed, False otherwise.
  """
  one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
  num_cq_false_rejection = len([
      occurrence for occurrence in flake.flake_occurrences
      if occurrence.time_reported > one_day_ago and
      occurrence.flake_type == FlakeType.CQ_FALSE_REJECTION
  ])
  num_outright_flake = len([
      occurrence for occurrence in flake.flake_occurrences
      if occurrence.time_reported > one_day_ago and
      occurrence.flake_type == FlakeType.OUTRIGHT_FLAKE
  ])
  return (num_cq_false_rejection >= _CQ_REJECTION_THRESHOLD or
          num_outright_flake >= _OUTRIGHT_FLAKE_THRESHOLD)


def UpdateFlakeWithExistingBug(flake):
  """Search for an existing bug and update the model with it."""
  if not flake.flake_issue:
    existing_bug = issue_tracking_service.GetExistingBugForCustomizedField(
        flake.test_name)
    if existing_bug:
      flake.flake_issue = FlakeIssue()
      flake.flake_issue.FromMonorailIssue(existing_bug)
      flake.put()


def HasExistingFlakeBugBeenUpdated(flake):
  """Checks if the existing flake bug has been updated in the past 24H.

  If the bug has been closed, then the entry in flake will be zeroed out.

  Args:
    flake (model.flake.detection.flake): The parent Flake to examine.
  Returns:
    (boolean) True if there has been an update in the past 24H, False otherwise.
  """
  if flake.flake_issue:
    one_day_ago = time_util.GetUTCNow() - datetime.timedelta(days=1)
    existing_bug = issue_tracking_service.GetBugForId(
        flake.flake_issue.issue_id)

    # If the issue isn't open, zero out the datastore entry for it.
    if not existing_bug.open:
      flake.flake_issue = None
      flake.put()

    # Don't update a bug if it's been updated in the last 24H
    if existing_bug.updated > one_day_ago:
      logging.info('Issue for Flake %r updated less than 24 hours ago', flake)
      return True

  logging.info('Issue for Flake %r has not been updated in the last 24 hours',
               flake)
  return False


@ndb.transactional
def CheckAndFileBugForDetectedFlake(flake):
  """Checks conditions for flake detection bug updated/filing.

  Args:
    flake (model.flake.detection.flake): The parent Flake to examine.
  """
  if HasFlakeDetectionUpdateLimitBeenReached():
    logging.info('Not filing because update limit has been reached.')
    return

  if not FlakeHasEnoughOccurrencesToFileBug(flake):
    logging.info('Flake %r does not have enough occurrences to file', flake)
    return

  UpdateFlakeWithExistingBug(flake)

  # Track the old bug id, even if it's been closed.
  old_bug_id = None
  if flake.flake_issue:
    old_bug_id = flake.flake_issue.issue_id

  # This call will zero out the flake_issue datastore if the bug isn't open.
  if HasExistingFlakeBugBeenUpdated(flake):
    logging.info('Issue for Flake %r has been updated in the past 24H', flake)
    return

  occurrence_count = GetTotalRecentFlakeOccurrences(flake)

  if flake.flake_issue:
    issue_tracking_service.UpdateBugForDetectedFlake(flake, occurrence_count)
  else:
    issue_tracking_service.CreateBugForDetectedFlake(
        flake, occurrence_count, old_bug_id=old_bug_id)
