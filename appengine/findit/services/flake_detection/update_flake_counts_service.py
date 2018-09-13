# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from libs import time_util
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from model.flake.flake import Flake
from services import constants


def _GetFlakeCounts(flake, start_date):
  """Gets the counts of the flake within certain time range.

  Args:
    flake(Flake): Object to be updated.
    start_date(datetime): Earliest time to check.
  """
  if flake.last_occurred_time <= start_date:
    return 0, 0

  occurrences = CQFalseRejectionFlakeOccurrence.query(
      ancestor=flake.key).filter(
          CQFalseRejectionFlakeOccurrence.time_happened > start_date).fetch()

  false_rejection_count = len(occurrences)

  gerrit_cl_ids = set([occurrence.gerrit_cl_id for occurrence in occurrences])
  impacted_cl_count = len(gerrit_cl_ids)

  return false_rejection_count, impacted_cl_count


def _UpdateCountsForNewFlake(start_date):
  """Updates counts for new or re-occurred flakes.

  Args:
    start_date(datetime): Earliest time to check.
  """
  flakes = Flake.query().filter(Flake.last_occurred_time > start_date).filter(
      Flake.false_rejection_count_last_week == 0).fetch()

  for flake in flakes:
    flake.false_rejection_count_last_week, flake.impacted_cl_count_last_week = (
        _GetFlakeCounts(flake, start_date))

  ndb.put_multi(flakes)


def _UpdateCountsForOldFlake(start_date):
  """Updates counts for old flakes - flakes with counts greater than 0.

  a. if the flake has 1+ occurrences within the time range, updates counts.
  b. if the flake didn't occurred within the time range, resets counts.

  Args:
    start_date(datetime): Earliest time to check.
  """
  flakes = Flake.query().filter(
      Flake.false_rejection_count_last_week > 0).fetch()

  for flake in flakes:
    flake.false_rejection_count_last_week, flake.impacted_cl_count_last_week = (
        _GetFlakeCounts(flake, start_date))

  ndb.put_multi(flakes)


def UpdateFlakeCounts():
  """Updates flakes periodically on statistical fields.

  Currently we only have weekly counts to update. Later we may also maintain
  daily or monthly counts.
  """
  start_date = time_util.GetDateDaysBeforeNow(days=constants.DAYS_IN_A_WEEK)
  _UpdateCountsForOldFlake(start_date)
  _UpdateCountsForNewFlake(start_date)
