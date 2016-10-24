# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import time
from datetime import timedelta

from common import time_util
from common.base_handler import BaseHandler
from common.base_handler import Permission

from model import result_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis


def FilterMasterFlakeAnalysis(
    master_flake_analysis_query, master_name=None, builder_name=None,
    build_number=None, step_name=None, test_name=None, start_date=None,
    end_date=None, status_code=result_status.UNSPECIFIED):
  if master_name:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.master_name == master_name)
  if builder_name:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.builder_name == builder_name)
  if build_number:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.build_number == build_number)
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

  master_flake_analysis_query.order(-MasterFlakeAnalysis.request_time)
  return master_flake_analysis_query.fetch()


class ListFlakes(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def _GetStartAndEndDates(self, triage):
    start_date = None
    end_date = None

    if triage:
      midnight_today = datetime.combine(time_util.GetUTCNow(), time.min)
      midnight_yesterday = midnight_today - timedelta(days=1)
      midnight_tomorrow = midnight_today + timedelta(days=1)

      start = self.request.get('start_date')
      end = self.request.get('end_date')
      start_date = (datetime.strptime(start, '%Y-%m-%d') if start else
                    midnight_yesterday)
      end_date = (datetime.strptime(end, '%Y-%m-%d') if end else
                  midnight_tomorrow)

    return start_date, end_date

  def HandleGet(self):
    status_code = int(
        self.request.get('result_status', result_status.UNSPECIFIED))
    master_name = self.request.get('master_name').strip()
    builder_name = self.request.get('builder_name').strip()
    build_number = self.request.get('build_number').strip()
    if build_number:
      build_number = int(build_number)
    step_name = self.request.get('step_name').strip()
    test_name = self.request.get('test_name').strip()
    triage = self.request.get('triage') == '1'

    # Only allow querying by start/end dates for admins during triage to avoid
    # overcomplicating the UI for other users.
    start_date, end_date = self._GetStartAndEndDates(triage)

    master_flake_analyses = FilterMasterFlakeAnalysis(
        MasterFlakeAnalysis.query(), master_name, builder_name, build_number,
        step_name, test_name, start_date, end_date, status_code)

    data = {
        'master_flake_analyses': [],
        'result_status_filter': status_code,
        'master_name_filter': master_name,
        'builder_name_filter': builder_name,
        'build_number_filter': build_number,
        'step_name_filter': step_name,
        'test_name_filter': test_name
    }

    if triage:  # pragma: no cover
      data['triage'] = triage
      data['start_date'] = start_date
      data['end_date'] = end_date

    for master_flake_analysis in master_flake_analyses:
      data['master_flake_analyses'].append({
          'master_name': master_flake_analysis.master_name,
          'builder_name': master_flake_analysis.builder_name,
          'build_number': master_flake_analysis.build_number,
          'step_name': master_flake_analysis.step_name,
          'test_name': master_flake_analysis.test_name,
          'status': master_flake_analysis.status_description,
          'suspected_build': master_flake_analysis.suspected_flake_build_number,
          'request_time': time_util.FormatDatetime(
              master_flake_analysis.request_time),
          'result_status': result_status.RESULT_STATUS_TO_DESCRIPTION.get(
              master_flake_analysis.result_status)
      })

    # TODO (stgao): use index instead of in-memory sort.
    # Index doesn't work for now, possibly due to legacy data.
    data['master_flake_analyses'].sort(
        key=lambda e: e['request_time'], reverse=True)

    return {
        'template': 'flake/dashboard.html',
        'data': data
    }
