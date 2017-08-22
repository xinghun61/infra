# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
from collections import defaultdict

from google.appengine.ext import ndb

from common.waterfall import failure_type
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model import analysis_approach_type
from model import suspected_cl_status
from model.suspected_cl_confidence import SuspectedCLConfidence
from model.suspected_cl_confidence import ConfidenceInformation
from model.wf_suspected_cl import WfSuspectedCL

TRIAGED_STATUS = [
    suspected_cl_status.CORRECT, suspected_cl_status.INCORRECT,
    suspected_cl_status.PARTIALLY_CORRECT, suspected_cl_status.PARTIALLY_TRIAGED
]

TIME_RANGE_DAYS = 183  # Query CLs in the past half year.


def _CreateConfidenceInformation(result, score=None):
  """Calculates confidence score for one type of result."""
  correct_number = result.get(suspected_cl_status.CORRECT, 0)
  incorrect_number = result.get(suspected_cl_status.INCORRECT, 0)
  total_number = correct_number + incorrect_number
  confidence = (float(correct_number) / total_number if total_number else -1.0)

  return ConfidenceInformation(
      correct=correct_number,
      total=total_number,
      confidence=confidence,
      score=score)


def _CalculateConfidenceLevelsForHeuristic(new_results):
  """Calculates confidence score for heuristic results."""
  updated_results = []

  for score, result in new_results.iteritems():
    updated_results.append(_CreateConfidenceInformation(result, score=score))

  return updated_results


def _GetCLDataForHeuristic(date_start, date_end):
  """Gets All triaged CLs which were found by heuristic approaches."""
  suspected_cls_query = WfSuspectedCL.query(
      ndb.AND(
          WfSuspectedCL.status.IN(TRIAGED_STATUS), WfSuspectedCL.approaches ==
          analysis_approach_type.HEURISTIC, WfSuspectedCL.updated_time >=
          date_start, WfSuspectedCL.updated_time < date_end))

  suspected_cls = suspected_cls_query.fetch()
  cl_by_top_score_dict = defaultdict(
      lambda: defaultdict(lambda: defaultdict(int)))

  for cl in suspected_cls:
    if not cl.builds:
      continue

    failures = []
    for build in cl.builds.values():
      # Deduplicate and ignore the builds which were not found by heuristic
      # approach and ignore the builds which were not triaged.
      if (build['failures'] in failures or not build['top_score'] or
          build['status'] is None):  # pragma: no cover
        continue

      failures.append(build['failures'])

      failure = build['failure_type']
      top_score = build['top_score']
      status = build['status']
      cl_by_top_score_dict[failure][top_score][status] += 1

  return cl_by_top_score_dict


def _GetCLDataForTryJob(date_start, date_end):
  """Gets All triaged CLs which were found by try job approaches."""
  suspected_cls_query = WfSuspectedCL.query(
      ndb.AND(
          WfSuspectedCL.status.IN(TRIAGED_STATUS), WfSuspectedCL.approaches ==
          analysis_approach_type.TRY_JOB, WfSuspectedCL.updated_time >=
          date_start, WfSuspectedCL.updated_time < date_end))

  suspected_cls = suspected_cls_query.fetch()
  try_job_cls_dict = defaultdict(lambda: defaultdict(int))
  both_cls_dict = defaultdict(lambda: defaultdict(int))
  for cl in suspected_cls:
    if not cl.builds:
      continue

    failures = []
    for build in cl.builds.values():
      # Deduplicate and ignore the builds which were not triaged.
      if (build['failures'] in failures or
          build['status'] is None):  # pragma: no cover
        continue

      failures.append(build['failures'])

      try_job_cls_dict[build['failure_type']][build['status']] += 1

      if analysis_approach_type.HEURISTIC in build['approaches']:
        # Both heuristic and try job found this CL on this build.
        both_cls_dict[build['failure_type']][build['status']] += 1

  return try_job_cls_dict, both_cls_dict


def _SavesNewCLConfidence():
  """Queries all CLs and calculates confidence of each type of results."""
  date_end = time_util.GetUTCNow().replace(
      hour=0, minute=0, second=0, microsecond=0)
  date_start = date_end - datetime.timedelta(days=TIME_RANGE_DAYS)
  result_heuristic = _GetCLDataForHeuristic(date_start, date_end)
  result_try_job, result_both = _GetCLDataForTryJob(date_start, date_end)

  new_compile_heuristic = _CalculateConfidenceLevelsForHeuristic(
      result_heuristic[failure_type.COMPILE])
  new_test_heuristic = _CalculateConfidenceLevelsForHeuristic(
      result_heuristic[failure_type.TEST])
  new_compile_try_job = _CreateConfidenceInformation(
      result_try_job[failure_type.COMPILE])
  new_test_try_job = _CreateConfidenceInformation(
      result_try_job[failure_type.TEST])
  new_compile_heuristic_try_job = _CreateConfidenceInformation(
      result_both[failure_type.COMPILE])
  new_test_heuristic_try_job = _CreateConfidenceInformation(
      result_both[failure_type.TEST])

  confidence = SuspectedCLConfidence.Get()
  confidence.Update(date_start, date_end, new_compile_heuristic,
                    new_compile_try_job, new_compile_heuristic_try_job,
                    new_test_heuristic, new_test_try_job,
                    new_test_heuristic_try_job)
  return confidence


class CalculateConfidenceScores(BaseHandler):
  """Calculates confidence scores for each kind of Findit results.

  Currently following analysis categories are considered:
    1. Compile Failures with Heuristic results
    2. Compile Failures with try job results
    3. Compile Failures with both results
    4. Test Failures with Heuristic results
    5. Test Failures with try job results
    6. Test Failures with both results
  """

  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    # Calculates confidence scores for results of the last half year.
    _SavesNewCLConfidence()
