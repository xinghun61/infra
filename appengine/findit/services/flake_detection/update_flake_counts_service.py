# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy

from google.appengine.ext import ndb

from libs import time_util
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake import FlakeCountsByType
from model.flake.flake_type import FlakeType
from model.flake.flake_type import FLAKE_TYPE_WEIGHT
from services import constants

# Minimum number of distinct impacted CLs for a flake's false rejections or
# retry with patch occurrences to calculate the flake score.
_MIN_NON_HIDDEN_DISTINCT_CL_NUMBER = 3

# Minimum number of distinct impacted CLs for a flake to calculate the flake
# score, including occurrences of false rejection, retry with patch flakes and
# hidden flakes.
_MIN_TOTAL_DISTINCT_CL_NUMBER = 20


def _GetTypedFlakeOccurrencesQuery(flake, start_date, flake_type):
  return FlakeOccurrence.query(ancestor=flake.key).filter(
      ndb.AND(FlakeOccurrence.flake_type == flake_type,
              FlakeOccurrence.time_happened > start_date))


def _GetTypedCQFlakeCounts(flake, start_date, flake_type,
                           counted_gerrit_cl_ids):
  """Gets counts of cq flake typed occurrences for a flake within a time range.

  Args:
    flake(Flake): Object to be updated.
    start_date(datetime): Earliest time to check.
    flake_type(FlakeType): Type of the flake.
    counted_gerrit_cl_ids(set): A set of gerrit cl ids that have been counted.

  Returns:
    (FlakeCountsByType, set): A FlakeCountsByType to store the counts of a type
      of the flake, and a set of counted cls.
  """

  query = _GetTypedFlakeOccurrencesQuery(flake, start_date, flake_type)
  more = True
  cursor = None
  occurrence_count = 0
  impacted_cl_count = 0
  while more:
    occurrences, cursor, more = query.fetch_page(
        500, start_cursor=cursor, projection=[FlakeOccurrence.gerrit_cl_id])
    occurrence_count += len(occurrences)
    if not occurrence_count:
      return None, counted_gerrit_cl_ids

    # Only count the CL as being impacted if it was not counted before.
    gerrit_cl_ids = set([occurrence.gerrit_cl_id for occurrence in occurrences
                        ]) - counted_gerrit_cl_ids
    counted_gerrit_cl_ids = counted_gerrit_cl_ids | gerrit_cl_ids

    impacted_cl_count += len(gerrit_cl_ids)

  return FlakeCountsByType(
      flake_type=flake_type,
      occurrence_count=occurrence_count,
      impacted_cl_count=impacted_cl_count), counted_gerrit_cl_ids


def _CalculateWeightedFlakeScore(flake_counts_last_week):
  """Calculates flake score by occurrences of each type and their weights.

  Args:
    flake_counts_last_week(list): A list of FlakeCountsByType.
  """
  flake_score_last_week = 0
  for typed_counts in flake_counts_last_week:
    if typed_counts.flake_type == FlakeType.CI_FAILED_STEP:
      flake_score_last_week += (
          typed_counts.occurrence_count *
          FLAKE_TYPE_WEIGHT[typed_counts.flake_type])
      continue
    flake_score_last_week += (
        typed_counts.impacted_cl_count *
        FLAKE_TYPE_WEIGHT[typed_counts.flake_type])
  return flake_score_last_week


def _UpdateFlakeCountsAndScore(flake, start_date):
  """Gets the counts of the flake within certain time range.

  Args:
    flake(Flake): Object to be updated.
    start_date(datetime): Earliest time to check.
  """
  flake.false_rejection_count_last_week = 0
  flake.impacted_cl_count_last_week = 0
  flake.flake_counts_last_week = []
  flake.flake_score_last_week = 0

  if flake.last_occurred_time <= start_date:
    return

  counted_gerrit_cl_ids = set([])

  for flake_type in [FlakeType.CQ_FALSE_REJECTION, FlakeType.RETRY_WITH_PATCH]:
    # Counts the occurrences/impacted CLs of the flake from the type with the
    # highest impact to the type with the lowest impact.
    # So that we don't count the same CL multiple times.
    typed_counts, counted_gerrit_cl_ids = _GetTypedCQFlakeCounts(
        flake, start_date, flake_type, counted_gerrit_cl_ids)
    if not typed_counts:
      continue

    flake.flake_counts_last_week.append(typed_counts)

    # This is a workaround: we don't differentiate flakes from different types
    # for now, so that we can bring back the flakes on our dashboard quickly.
    # TODO(crbug/896006): Remove false_rejection_count_last_week and
    # impacted_cl_count_last_week.
    flake.false_rejection_count_last_week += typed_counts.occurrence_count
    flake.impacted_cl_count_last_week += typed_counts.impacted_cl_count

  # Store CL ids that are impacted by false rejection or retry with patch.
  non_hidden_flake_gerrit_cl_ids = copy.deepcopy(counted_gerrit_cl_ids)

  # Counts hidden flake occurrences.
  typed_counts, counted_gerrit_cl_ids = _GetTypedCQFlakeCounts(
      flake, start_date, FlakeType.CQ_HIDDEN_FLAKE, counted_gerrit_cl_ids)
  if typed_counts:
    flake.flake_counts_last_week.append(typed_counts)

  # Counts CI flake occurrences.
  ci_flake_occurrence_count = _GetTypedFlakeOccurrencesQuery(
      flake, start_date, FlakeType.CI_FAILED_STEP).count()
  if ci_flake_occurrence_count:
    flake.flake_counts_last_week.append(
        FlakeCountsByType(
            flake_type=FlakeType.CI_FAILED_STEP,
            occurrence_count=ci_flake_occurrence_count,
            impacted_cl_count=-1))

  if (len(non_hidden_flake_gerrit_cl_ids) < _MIN_NON_HIDDEN_DISTINCT_CL_NUMBER
      and len(counted_gerrit_cl_ids) < _MIN_TOTAL_DISTINCT_CL_NUMBER and
      ci_flake_occurrence_count == 0):
    # If there is not enough occurrences for the flake, bail out.
    return

  flake.flake_score_last_week = _CalculateWeightedFlakeScore(
      flake.flake_counts_last_week)


def _UpdateCountsForNewFlake(start_date):
  """Updates counts for new, re-occurred or rare flakes.

  Args:
    start_date(datetime): Earliest time to check.
  """
  more = True
  cursor = None

  while more:
    ndb.get_context().clear_cache()
    flakes, cursor, more = Flake.query().filter(
        Flake.last_occurred_time > start_date).filter(
            Flake.flake_score_last_week == 0).fetch_page(
                100, start_cursor=cursor)
    for flake in flakes:
      _UpdateFlakeCountsAndScore(flake, start_date)

    ndb.put_multi(flakes)


def _UpdateCountsForOldFlake(start_date):
  """Updates counts for old flakes - flakes with score greater than 0.

  a. if the flake has 1+ occurrences within the time range, updates counts.
  b. if the flake didn't occurred within the time range, resets counts.

  Args:
    start_date(datetime): Earliest time to check.
  """
  more = True
  cursor = None

  while more:
    ndb.get_context().clear_cache()
    flakes, cursor, more = Flake.query().filter(
        Flake.flake_score_last_week > 0).fetch_page(
            100, start_cursor=cursor)
    for flake in flakes:
      _UpdateFlakeCountsAndScore(flake, start_date)

    ndb.put_multi(flakes)


def UpdateFlakeCounts():
  """Updates flakes periodically on statistical fields.

  Currently we only have weekly counts to update. Later we may also maintain
  daily or monthly counts.
  """
  start_date = time_util.GetDateDaysBeforeNow(days=constants.DAYS_IN_A_WEEK)
  _UpdateCountsForOldFlake(start_date)
  _UpdateCountsForNewFlake(start_date)
