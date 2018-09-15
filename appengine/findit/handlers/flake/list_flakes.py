# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs import dashboard_util
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import analysis_status
from libs import time_util
from model import result_status
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis

PAGE_SIZE = 100


def _GetFlakeAnalysisFilterQuery(master_flake_analysis_query,
                                 step_name=None,
                                 test_name=None,
                                 start_date=None,
                                 end_date=None,
                                 status_code=result_status.UNSPECIFIED):
  if step_name:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.step_name == step_name)
  if test_name:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.test_name == test_name)
  if start_date:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.request_time >= start_date)
  if end_date:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.request_time < end_date)
  if status_code != result_status.UNSPECIFIED:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.result_status == status_code)

  return master_flake_analysis_query


class ListFlakes(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def _GetStartAndEndDates(self, triage):
    if not triage:
      return None, None

    return dashboard_util.GetStartAndEndDates(
        self.request.get('start_date'), self.request.get('end_date'))

  def HandleGet(self):
    status_code = int(
        self.request.get('result_status', result_status.UNSPECIFIED))
    step_name = self.request.get('step_name').strip()
    test_name = self.request.get('test_name').strip()
    triage = self.request.get('triage') == '1'

    # Only allow querying by start/end dates for admins during triage to avoid
    # overcomplicating the UI for other users.
    start_date, end_date = self._GetStartAndEndDates(triage)

    master_flake_analysis_query = _GetFlakeAnalysisFilterQuery(
        MasterFlakeAnalysis.query(), step_name, test_name, start_date, end_date,
        status_code)

    # If filters by step_name and/or test_name, don't do paging.
    if step_name or test_name:
      analyses = master_flake_analysis_query.order(
          -MasterFlakeAnalysis.request_time).fetch()
      prev_cursor = ''
      cursor = ''
    else:
      analyses, prev_cursor, cursor = dashboard_util.GetPagedResults(
          master_flake_analysis_query, [MasterFlakeAnalysis.request_time],
          self.request.get('cursor'),
          self.request.get('direction').strip(),
          page_size=PAGE_SIZE)

    data = {
        'master_flake_analyses': [],
        'result_status_filter': status_code,
        'step_name_filter': step_name,
        'test_name_filter': test_name,
        'prev_cursor': prev_cursor,
        'cursor': cursor,
    }

    if triage:  # pragma: no cover
      data['triage'] = triage
      data['start_date'] = start_date
      data['end_date'] = end_date

    for analysis in analyses:
      culprit = None
      if analysis.culprit_urlsafe_key:
        culprit_key = ndb.Key(urlsafe=analysis.culprit_urlsafe_key)
        # TODO(crbug.com/799308): Remove this hack when bug is fixed.
        assert culprit_key.pairs()[0]
        assert culprit_key.pairs()[0][0]  # Name of the model.
        assert culprit_key.pairs()[0][1]  # Id of the model.
        culprit = ndb.Key(culprit_key.pairs()[0][0],
                          culprit_key.pairs()[0][1]).get()

      status = analysis.status
      if (analysis.try_job_status == analysis_status.ERROR or
          analysis.heuristic_analysis_status == analysis_status.ERROR):
        status = analysis_status.ERROR

      timestamp = (
          time_util.ConvertToTimestamp(analysis.request_time)
          if analysis.request_time else 'None')

      data['master_flake_analyses'].append({
          'master_name':
              analysis.original_master_name or analysis.master_name,
          'builder_name':
              analysis.original_builder_name or analysis.builder_name,
          'build_number':
              analysis.original_build_number or analysis.build_number,
          'step_name':
              analysis.original_step_name or analysis.step_name,
          'test_name':
              analysis.original_test_name or analysis.test_name,
          'bug_id':
              analysis.bug_id,
          'confidence_in_culprit':
              analysis.confidence_in_culprit,
          'culprit':
              culprit.to_dict() if culprit else {},
          'key':
              analysis.key.urlsafe(),
          'request_utc_timestamp':
              timestamp,
          'result_status':
              result_status.RESULT_STATUS_TO_DESCRIPTION.get(
                  analysis.result_status),
          'suspected_build':
              analysis.suspected_flake_build_number,
          'status':
              analysis_status.STATUS_TO_DESCRIPTION.get(status),
      })

    return {'template': 'flake/dashboard.html', 'data': data}
