# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import time
from datetime import timedelta
import json

from common import time_util
from common.base_handler import BaseHandler, Permission
from model.wf_try_job_data import WfTryJobData


NOT_AVAILABLE = 'N/A'


def _FormatDuration(start_time, end_time):
  if not start_time or not end_time:
    return NOT_AVAILABLE
  return time_util.FormatTimedelta(end_time - start_time)


def _PrepareBuildbucketResponseForDisplay(buildbucket_response):
  """Prepares a buildbucket response for display in the template.

    buildbucket_response contains json inside json, which causes problems when
    pretty printing in the corresponding template file. This function reformats
    internal json as a dict.

  Args:
    buildbucket_response: A raw buildbucket response json object.

  Returns:
    A copy of the original buildbucket response dict, with json fields replaced
    by dicts.
  """
  if buildbucket_response is None:
    return None

  new_response = {}

  for key, value in buildbucket_response.iteritems():
    if 'json' in key:
      value = json.loads(value)

    new_response[key] = value

  return new_response


class TryJobDashboard(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Shows a list of Findit try job results and statuses in an HTML page."""
    midnight_today = datetime.combine(time_util.GetUTCNow(), time.min)
    midnight_yesterday = midnight_today - timedelta(days=1)
    midnight_tomorrow = midnight_today + timedelta(days=1)

    start = self.request.get('start_date')
    end = self.request.get('end_date')
    start_date = (datetime.strptime(start, '%Y-%m-%d') if start else
                  midnight_yesterday)
    end_date = (datetime.strptime(end, '%Y-%m-%d') if end else
                midnight_tomorrow)

    if start or not end:  # pragma: no branch
      # If a start date is specified, get everything since then.
      try_job_query = WfTryJobData.query(
          WfTryJobData.request_time >= start_date,
          WfTryJobData.request_time < end_date)
    else:  # pragma: no cover
      # If no start date specified, then get everything up until end_date.
      start_date = None
      try_job_query = WfTryJobData.query(
          WfTryJobData.request_time < end_date)

    try_job_data_list = try_job_query.fetch()

    # Sort try job data list by most recent request first.
    try_job_data_list.sort(key=lambda x: x.request_time, reverse=True)

    try_jobs_in_progress = []
    try_jobs_with_error = []
    successfully_completed_try_jobs = []

    for try_job_data in try_job_data_list:
      try_job_display_data = {
          'master_name': try_job_data.master_name,
          'builder_name': try_job_data.builder_name,
          'build_number': try_job_data.build_number,
          'try_job_type': try_job_data.try_job_type,
          'pending_time': _FormatDuration(
              try_job_data.request_time, try_job_data.start_time),
          'request_time': time_util.FormatDatetime(try_job_data.request_time),
          'try_job_url': try_job_data.try_job_url,
          'last_buildbucket_response': json.dumps(
              _PrepareBuildbucketResponseForDisplay(
                  try_job_data.last_buildbucket_response), sort_keys=True)
      }

      if not try_job_data.end_time and not try_job_data.error:
        try_job_display_data['elapsed_time'] = (
            _FormatDuration(try_job_data.request_time, time_util.GetUTCNow()) if
            try_job_data.request_time else None)
        try_job_display_data['status'] = (
            'running' if try_job_data.start_time else 'pending')
        try_jobs_in_progress.append(try_job_display_data)
      elif try_job_data.error:
        try_job_display_data['error'] = try_job_data.error['message']
        # It is possible end_time is not available if the error was timeout.
        try_job_display_data['execution_time'] = _FormatDuration(
            try_job_data.start_time, try_job_data.end_time)
        try_jobs_with_error.append(try_job_display_data)
      else:
        try_job_display_data['culprit_found'] = bool(try_job_data.culprits)
        try_job_display_data['execution_time'] = _FormatDuration(
            try_job_data.start_time, try_job_data.end_time)
        successfully_completed_try_jobs.append(try_job_display_data)

    data = {
        'start_date': time_util.FormatDatetime(start_date),
        'end_date': time_util.FormatDatetime(end_date),
        'try_jobs_in_progress': try_jobs_in_progress,
        'try_jobs_with_error': try_jobs_with_error,
        'successfully_completed_try_jobs': successfully_completed_try_jobs
    }

    return {
        'template': 'try_job_dashboard.html',
        'data': data
    }
