# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Calculates confidence scores for all suspected CLs so far and save the scores
   to data store.
"""

import argparse
from collections import defaultdict
import datetime
import json
import os
import sys

_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
sys.path.insert(1, _FINDIT_DIR)
from local_libs import remote_api

from common.waterfall import failure_type
from lib import time_util
from model import analysis_approach_type
from model import suspected_cl_status
from model.suspected_cl_confidence import SuspectedCLConfidence
from model.suspected_cl_confidence import ConfidenceInformation
from model.wf_suspected_cl import WfSuspectedCL

TRIAGED_STATUS = [
    suspected_cl_status.CORRECT, suspected_cl_status.INCORRECT,
    suspected_cl_status.PARTIALLY_CORRECT, suspected_cl_status.PARTIALLY_TRIAGED
]


def _CreateConfidenceInformation(result, score=None):
  correct_number = result[suspected_cl_status.CORRECT]
  incorrect_number = result[suspected_cl_status.INCORRECT]
  total_number = correct_number + incorrect_number
  confidence = (float(correct_number) / total_number if total_number else -1.0)

  return ConfidenceInformation(
      correct=correct_number,
      total=total_number,
      confidence=confidence,
      score=score)


def _CalculateConfidenceLevelsForHeuristic(new_results):
  updated_results = []

  for score, result in new_results.iteritems():
    updated_results.append(_CreateConfidenceInformation(result, score=score))

  return updated_results


def _SavesNewCLConfidence(date_start, date_end, result_heuristic,
                          result_try_job, result_both):

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

  SuspectedCLConfidence.Get().Update(
      date_start, date_end, new_compile_heuristic, new_compile_try_job,
      new_compile_heuristic_try_job, new_test_heuristic, new_test_try_job,
      new_test_heuristic_try_job)
  return SuspectedCLConfidence.Get()


def _AddMoreConstrainsToQuery(query, failure_args, date_start, date_end):
  if 'compile' in failure_args:
    query = query.filter(WfSuspectedCL.failure_type == failure_type.COMPILE)
  elif 'test' in failure_args:
    query = query.filter(WfSuspectedCL.failure_type == failure_type.TEST)

  if date_start:
    query = query.filter(WfSuspectedCL.updated_time >= date_start)
  query = query.filter(WfSuspectedCL.updated_time < date_end)
  return query


def _GetCLDataForHeuristic(failure_args, date_start, date_end):

  suspected_cls_query = WfSuspectedCL.query(
      remote_api.ndb.AND(
          WfSuspectedCL.status.IN(TRIAGED_STATUS), WfSuspectedCL.approaches ==
          analysis_approach_type.HEURISTIC))

  suspected_cls_query = _AddMoreConstrainsToQuery(
      suspected_cls_query, failure_args, date_start, date_end)

  suspected_cls = suspected_cls_query.fetch()

  cl_by_top_score_dict = defaultdict(
      lambda: defaultdict(lambda: defaultdict(int)))
  for cl in suspected_cls:
    if not cl.builds:
      continue

    failures = []
    for build in cl.builds.values():
      if (build['failures'] in failures or not build['top_score'] or
          build['status'] is None):
        continue

      if (('compile' in failure_args and
           build['failure_type'] == failure_type.TEST) or
          ('test' in failure_args and
           build['failure_type'] == failure_type.COMPILE)):
        continue

      failures.append(build['failures'])

      failure = build['failure_type']
      top_score = build['top_score']
      status = build['status']
      cl_by_top_score_dict[failure][top_score][status] += 1

  return cl_by_top_score_dict


def _GetCLDataForTryJob(failure_args, date_start, date_end):
  suspected_cls_query = WfSuspectedCL.query(
      remote_api.ndb.AND(
          WfSuspectedCL.status.IN(TRIAGED_STATUS), WfSuspectedCL.approaches ==
          analysis_approach_type.TRY_JOB))

  suspected_cls_query = _AddMoreConstrainsToQuery(
      suspected_cls_query, failure_args, date_start, date_end)

  suspected_cls = suspected_cls_query.fetch()

  try_job_cls_dict = defaultdict(lambda: defaultdict(int))
  both_cls_dict = defaultdict(lambda: defaultdict(int))
  for cl in suspected_cls:
    if not cl.builds:
      continue

    failures = []
    for build in cl.builds.values():
      if build['failures'] in failures or build['status'] is None:
        continue

      if (('compile' in failure_args and
           build['failure_type'] == failure_type.TEST) or
          ('test' in failure_args and
           build['failure_type'] == failure_type.COMPILE)):
        continue

      failures.append(build['failures'])

      try_job_cls_dict[build['failure_type']][build['status']] += 1

      if analysis_approach_type.HEURISTIC in build['approaches']:
        # Both heuristic and try job found this CL on this build.
        both_cls_dict[build['failure_type']][build['status']] += 1

  return try_job_cls_dict, both_cls_dict


def _FormatResult(result):
  if not result:
    return None

  new_result = {}
  if isinstance(result, list):
    for score_result in result:
      new_result[score_result.score] = score_result.ToDict()
  elif isinstance(result, dict):
    new_result = result
  else:
    new_result = result.ToDict()

  return new_result


def _PrintResult(date_start, date_end, result_heuristic, result_try_job,
                 result_both):
  print 'Start Date: ', date_start
  print 'End Date: ', date_end
  print '--------------------------------------------------------------------'
  if result_heuristic:
    print 'compile_heuristic'
    print json.dumps(
        _FormatResult(result_heuristic.get(failure_type.COMPILE)), indent=2)
    print
    print 'test_heuristic'
    print json.dumps(
        _FormatResult(result_heuristic.get(failure_type.TEST)), indent=2)
    print
  if result_try_job:
    print 'compile_try_job'
    print json.dumps(
        _FormatResult(result_try_job.get(failure_type.COMPILE)), indent=2)
    print
    print 'test_try_job'
    print json.dumps(
        _FormatResult(result_try_job.get(failure_type.TEST)), indent=2)
    print
  if result_both:
    print 'compile_heuristic_try_job'
    print json.dumps(
        _FormatResult(result_both.get(failure_type.COMPILE)), indent=2)
    print
    print 'test_heuristic_try_job'
    print json.dumps(
        _FormatResult(result_both.get(failure_type.TEST)), indent=2)
    print


def _ValidDate(date_str):
  try:
    return datetime.datetime.strptime(date_str, '%Y-%m-%d')
  except ValueError:
    raise argparse.ArgumentTypeError('Type of date is invalid.')


def _GetArguments():
  parser = argparse.ArgumentParser()

  # Uses group to make -c|-t are exclusive from each other, because if both
  # arguments are there, it means query everything.
  # Same for -r|-j.
  failure_group = parser.add_mutually_exclusive_group()
  failure_group.add_argument(
      '-c',
      action='store_true',
      dest='compile',
      help='get confidence score for compile failures.')
  failure_group.add_argument(
      '-t',
      action='store_true',
      dest='test',
      help='get confidence score for test failures.')

  approach_group = parser.add_mutually_exclusive_group()
  # Uses -r for heuristic failures because -h is already used for help.
  approach_group.add_argument(
      '-r',
      action='store_true',
      dest='heuristic',
      help='get confidence score for heuristic failures.')
  # Uses -j for try job failures because -t is already used for test failures.
  approach_group.add_argument(
      '-j',
      action='store_true',
      dest='try_job',
      help='get confidence score for try job failures.')

  parser.add_argument(
      '-s',
      type=_ValidDate,
      dest='start_date',
      help='The Start Date - format YYYY-MM-DD')
  parser.add_argument(
      '-e',
      type=_ValidDate,
      dest='end_date',
      help='The End Date - format YYYY-MM-DD')

  args_dict = vars(parser.parse_args())
  useful_args = {}
  for arg, value in args_dict.iteritems():
    if value:
      useful_args[arg] = value

  return useful_args


if __name__ == '__main__':
  # Set up the Remote API to use services on the live App Engine.
  remote_api.EnableRemoteApi(app_id='findit-for-me')

  args = _GetArguments()

  default_end_date = time_util.GetUTCNow().replace(
      hour=0, minute=0, second=0, microsecond=0)
  end_date = args.get('end_date', default_end_date)

  start_date = args.get('start_date')
  if not args:  # Limits start_date to roughly half years ago.
    start_date = end_date - datetime.timedelta(days=183)

  heuristic_result = None
  try_job_result = None
  both_result = None
  if 'heuristic' in args:  # Only calculates results for heuristic.
    heuristic_result = _GetCLDataForHeuristic(args, start_date, end_date)
  elif 'try_job' in args:  # Only calculates results for try job.
    try_job_result, both_result = _GetCLDataForTryJob(args, start_date,
                                                      end_date)
  else:  # A full calculation for CLs for both failure types.
    heuristic_result = _GetCLDataForHeuristic(args, start_date, end_date)
    try_job_result, both_result = _GetCLDataForTryJob(args, start_date,
                                                      end_date)

  if not args:  # Saves new confidence score for full calculation only.
    cl_confidence = _SavesNewCLConfidence(
        start_date, end_date, heuristic_result, try_job_result, both_result)

    heuristic_result = {
        failure_type.COMPILE: cl_confidence.compile_heuristic,
        failure_type.TEST: cl_confidence.test_heuristic
    }
    try_job_result = {
        failure_type.COMPILE: cl_confidence.compile_try_job,
        failure_type.TEST: cl_confidence.test_try_job
    }
    both_result = {
        failure_type.COMPILE: cl_confidence.compile_heuristic_try_job,
        failure_type.TEST: cl_confidence.test_heuristic_try_job
    }
    _PrintResult(start_date, end_date, heuristic_result, try_job_result,
                 both_result)

  else:
    _PrintResult(start_date, end_date, heuristic_result, try_job_result,
                 both_result)
