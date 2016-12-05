# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import time
from datetime import timedelta

from google.appengine.datastore.datastore_query import Cursor

from common.base_handler import BaseHandler
from common.base_handler import Permission
from lib import time_util
from model import result_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis


PAGE_SIZE = 100


def FilterMasterFlakeAnalysis(
    master_flake_analysis_query, step_name=None, test_name=None,
    start_date=None, end_date=None, status_code=result_status.UNSPECIFIED,
    cursor=None, direction='next'):
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

  master_flake_analysis_query_older = master_flake_analysis_query.order(
      -MasterFlakeAnalysis.request_time)

  # If filters by step_name and/or test_name, don't do paging.
  if step_name or test_name:
    analyses = master_flake_analysis_query_older.fetch()
    return analyses, None, False

  if direction.lower() == 'previous':
    master_flake_analysis_query_newer = master_flake_analysis_query.order(
        MasterFlakeAnalysis.request_time)
    analyses, next_cursor, more = master_flake_analysis_query_newer.fetch_page(
        PAGE_SIZE, start_cursor=cursor.reversed())
    analyses.reverse()
  else:
    analyses, next_cursor, more = master_flake_analysis_query_older.fetch_page(
        PAGE_SIZE, start_cursor=cursor)

  return analyses, next_cursor, more


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
    step_name = self.request.get('step_name').strip()
    test_name = self.request.get('test_name').strip()
    triage = self.request.get('triage') == '1'
    cursor = Cursor(urlsafe=self.request.get('cursor'))
    direction = self.request.get('direction').strip()

    # Only allow querying by start/end dates for admins during triage to avoid
    # overcomplicating the UI for other users.
    start_date, end_date = self._GetStartAndEndDates(triage)

    master_flake_analyses, next_cursor, more = FilterMasterFlakeAnalysis(
        MasterFlakeAnalysis.query(), step_name, test_name, start_date, end_date,
        status_code, cursor, direction)

    next_cursor = next_cursor.urlsafe() if next_cursor else ''
    used_cursor = cursor.urlsafe() if cursor else ''
    if direction == 'previous':
      prev_cursor = next_cursor if more else ''
      cursor = used_cursor
    else:
      prev_cursor = used_cursor
      cursor = next_cursor if more else ''

    data = {
        'master_flake_analyses': [],
        'result_status_filter': status_code,
        'step_name_filter': step_name,
        'test_name_filter': test_name,
        'prev_cursor': prev_cursor,
        'cursor': cursor,
        'more': more,
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

    return {
        'template': 'flake/dashboard.html',
        'data': data
    }
