# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Backfill existing analysis data to BigQuery events tables.

Upload historical analysis events to BigQuery. A full design for BigQuery
events and the backfill itself can be found at go/findit-bq-events.
"""
import datetime
import os
import sys

_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
_THIRD_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')
_FIRST_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'first_party')
sys.path.insert(0, _FINDIT_DIR)
sys.path.insert(0, _THIRD_PARTY_DIR)
sys.path.insert(0, _FIRST_PARTY_DIR)

import google
google.__path__.insert(0,
                       os.path.join(
                           os.path.dirname(os.path.realpath(__file__)),
                           'third_party', 'google'))
import pickle
from common.waterfall import failure_type
from local_libs import remote_api
from libs import analysis_status
from model import suspected_cl_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.proto.gen import findit_pb2
from model.wf_try_job import WfTryJob
from model.wf_suspected_cl import WfSuspectedCL
from model.wf_analysis import WfAnalysis
from services import event_reporting
from services.event_reporting import ReportCompileFailureAnalysisCompletionEvent
from services.event_reporting import ReportTestFailureAnalysisCompletionEvent
from services.event_reporting import ReportTestFlakeAnalysisCompletionEvent
from waterfall.flake import triggering_sources

# Active script for Findit production.
remote_api.EnableRemoteApi(app_id='findit-for-me')


def CanReportAnalysis(analysis):
  """Returns True if the analysis can be reported, False otherwise."""
  return analysis.start_time and analysis.end_time


def save_obj(obj, name):
  with open('obj/' + name + '.pkl', 'wb') as f:
    pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)


def load_obj(name):
  try:
    with open('obj/' + name + '.pkl', 'rb') as f:
      return pickle.load(f)
  except IOError:
    print 'couldn\'t load obj'
    return {}


def ReportTestFlakesForRange(start_time, end_time, dup_dict):
  """Reports test flakes to BQ for the given range.

  Optional cursor can be specific to continue.

  Args:
    (datetime) start_time: Start of the range.
    (datetime) end_time: End of the range.
    (Cursor) start_cursor: Marker on where to start the query at.
  """
  analyses_query = MasterFlakeAnalysis.query(
      MasterFlakeAnalysis.request_time > start_time,
      MasterFlakeAnalysis.request_time < end_time).order(
          MasterFlakeAnalysis.request_time)

  print 'reporting test flake events from {}  -->  {}'.format(
      start_time, end_time)

  cursor = None
  more = True
  page_size = 100

  while more:
    print 'fetching {} results...'.format(page_size)
    analyses, cursor, more = analyses_query.fetch_page(
        page_size, start_cursor=cursor)

    for analysis in analyses:
      if not CanReportAnalysis(analysis):
        continue
      success = ReportTestFlakeAnalysisCompletionEvent(analysis)
      if not success:
        print 'encountered error'
        return

      key = '{}/{}/{}/{}/{}'.format(analysis.master_name, analysis.builder_name,
                                    analysis.step_name, analysis.test_name,
                                    analysis.build_number)
      if key not in dup_dict:
        dup_dict[key] = True
      else:
        print 'found dup'
        continue

      print 'new start_time is {}'.format(analysis.request_time)


def ReportTestFailuresForRange(start_time, end_time, dup_dict):
  """Reports test failures to BQ for the given range.

  Optional cursor can be specific to continue.

  Args:
    (datetime) start_time: Start of the range.
    (datetime) end_time: End of the range.
    (Cursor) start_cursor: Marker on where to start the query at.
  """
  analyses_query = WfAnalysis.query(
      WfAnalysis.build_start_time > start_time,
      WfAnalysis.build_start_time < end_time).order(WfAnalysis.build_start_time)

  print 'reporting test failure events to {} from {}  -->  {}'.format(
      event_reporting._TABLE_ID_TEST, start_time, end_time)

  cursor = None
  more = True
  page_size = 100

  while more:
    print 'fetching {} results...'.format(page_size)
    analyses, cursor, more = analyses_query.fetch_page(
        page_size, start_cursor=cursor)

    for analysis in analyses:
      if analysis.build_failure_type != failure_type.TEST:
        continue
      if not CanReportAnalysis(analysis):
        continue
      print 'attempting with datetime {}'.format(analysis.build_start_time)

      success = ReportTestFailureAnalysisCompletionEvent(analysis)
      if not success:
        print 'encountered error'
        return

      key = analysis.key.pairs()[0][1]
      if key not in dup_dict:
        dup_dict[key] = True
      else:
        print 'found dup'
        continue

      print 'new start_time is {}'.format(analysis.build_start_time)


def ReportCompileFailuresForRange(start_time, end_time, dup_dict):
  """Reports compile failures to BQ for the given range.

  Optional cursor can be specific to continue.

  Args:
    (datetime) start_time: Start of the range.
    (datetime) end_time: End of the range.
    (Cursor) start_cursor: Marker on where to start the query at.
  """
  analyses_query = WfAnalysis.query(
      WfAnalysis.build_start_time > start_time,
      WfAnalysis.build_start_time < end_time).order(WfAnalysis.build_start_time)

  print 'reporting compile failure events from {}  -->  {}'.format(
      start_time, end_time)

  cursor = None
  more = True
  page_size = 100

  while more:
    print 'fetching {} results...'.format(page_size)
    analyses, cursor, more = analyses_query.fetch_page(
        page_size, start_cursor=cursor)

    for analysis in analyses:
      if analysis.build_failure_type != failure_type.COMPILE:
        continue
      if not CanReportAnalysis(analysis):
        continue

      success = ReportCompileFailureAnalysisCompletionEvent(analysis)
      if not success:
        print 'encountered errors'
        return

      key = analysis.key.pairs()[0][1]
      if key not in dup_dict:
        dup_dict[key] = True
      else:
        print 'found dup'
        continue

      print 'new start_time is {}'.format(analysis.build_start_time)


def main():
  start_time = datetime.datetime(2018, 2, 28, 18, 22, 43)
  end_time = datetime.datetime(2018, 3, 6)
  # test_dups
  # compile_dups
  dup_dict = load_obj('compile_dups')
  print dup_dict
  try:
    # ReportTestFlakesForRange(start_time, end_time, dup_dict)
    # ReportTestFailuresForRange(start_time, end_time, dup_dict)
    ReportCompileFailuresForRange(start_time, end_time, dup_dict)
  finally:
    save_obj(dup_dict, 'compile_dups')


if __name__ == '__main__':
  main()
