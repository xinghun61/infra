# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys

_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
_THIRD_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')
_FIRST_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'first_party')
sys.path.insert(1, _FINDIT_DIR)
sys.path.insert(0, _THIRD_PARTY_DIR)

import google

google.__path__.insert(0,
                       os.path.join(
                           os.path.dirname(os.path.realpath(__file__)),
                           'third_party', 'google'))

from local_libs import remote_api

# Activate us as findit prod.
remote_api.EnableRemoteApi(app_id='findit-for-me')

import datetime

from common.waterfall import failure_type
from libs import analysis_status

from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.proto.gen import findit_pb2
from model import suspected_cl_status
from model.wf_try_job import WfTryJob
from model.wf_suspected_cl import WfSuspectedCL
from model.wf_analysis import WfAnalysis

from services import event_reporting
from services.event_reporting import ReportTestFlakeAnalysisCompletionEvent
from services.event_reporting import ReportCompileFailureAnalysisCompletionEvent

from waterfall.flake import triggering_sources


def CanReportFlakeAnalysis(analysis):
  return analysis.start_time and analysis.end_time


def ReportFlakesFromDay(day, month, year):
  analyses_query = MasterFlakeAnalysis.query(
      MasterFlakeAnalysis.request_time > datetime.datetime(year, month, day),
      MasterFlakeAnalysis.request_time < datetime.datetime(
          year, month, day, 23, 59))

  analyses = []
  cursor = None
  more = True
  page_size = 500

  while more:
    cur_analyses, cursor, more = analyses_query.fetch_page(
        page_size, start_cursor=cursor)
    analyses.extend(cur_analyses)

  for analysis in analyses:
    if CanReportFlakeAnalysis(analysis):
      ReportTestFlakeAnalysisCompletionEvent(analysis)
      print 'found analysis, reporting'
    else:
      print 'skipping analysis'


def ReportBuildFailuresFromDay(day, month, year):
  analyses_query = WfAnalysis.query(
      WfAnalysis.build_start_time > datetime.datetime(year, month, day),
      WfAnalysis.build_start_time < datetime.datetime(year, month, day, 23, 59))

  analyses = []
  cursor = None
  more = True
  page_size = 500

  while more:
    cur_analyses, cursor, more = analyses_query.fetch_page(
        page_size, start_cursor=cursor)
    analyses.extend(cur_analyses)

  for analysis in analyses:
    if analysis.build_failure_type != failure_type.COMPILE:
      continue
    ReportCompileFailureAnalysisCompletionEvent(analysis)
    print 'found analysis, reporting'


def main():
  day = 10
  month = 12
  year = 2017
  ReportFlakesFromDay(day, month, year)
  # ReportBuildFailuresFromDay(day, month, year)


if __name__ == '__main__':
  main()
