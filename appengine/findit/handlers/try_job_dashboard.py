# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import time
from datetime import timedelta
import json

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model.flake.flake_try_job_data import FlakeTryJobData
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


def _FormatDisplayData(try_job_data):
  """Returns information of a WfTryJobData/FlakeTryJobData as a dict."""
  display_data = try_job_data.to_dict()

  for attribute in ('start_time', 'end_time', 'request_time'):
    display_data[attribute] = time_util.FormatDatetime(
        display_data[attribute])

  display_data['pending_time'] = _FormatDuration(
      try_job_data.request_time, try_job_data.start_time)
  display_data['last_buildbucket_response'] = json.dumps(
      _PrepareBuildbucketResponseForDisplay(
          display_data['last_buildbucket_response']), sort_keys=True)

  if isinstance(try_job_data, FlakeTryJobData):
    # Flake try job data does not include try_job_type.
    display_data['try_job_type'] = 'flake'

  # Do not include the try job key in the response.
  display_data.pop('try_job_key', None)

  return display_data


def _GetMidnightToday():
  return datetime.combine(time_util.GetUTCNow(), time.min)


def _GetStartEndDates(start, end):
  midnight_today = _GetMidnightToday()
  midnight_yesterday = midnight_today - timedelta(days=1)
  midnight_tomorrow = midnight_today + timedelta(days=1)

  if not start and not end:
    # If neither start nor end specified, get everything since yesterday.
    return midnight_yesterday, midnight_tomorrow
  elif not start and end:
    # If only end is specified, get everything up until then.
    return None, midnight_tomorrow
  elif start and not end:
    # If only start is specified, get everything since then.
    return datetime.strptime(start, '%Y-%m-%d'), midnight_tomorrow

  # Both start and end are specified, get everything in between.
  return (datetime.strptime(start, '%Y-%m-%d'),
          datetime.strptime(end, '%Y-%m-%d'))


class TryJobDashboard(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Shows a list of Findit try job results and statuses in an HTML page."""
    category = self.request.get('category')
    start = self.request.get('start_date')
    end = self.request.get('end_date')

    start_date, end_date = _GetStartEndDates(start, end)

    if category.lower() == 'flake':
      try_job_data_list = FlakeTryJobData.query(
          FlakeTryJobData.request_time >= start_date,
          FlakeTryJobData.request_time < end_date).fetch()
    elif category.lower() == 'waterfall':
      try_job_data_list = WfTryJobData.query(
          WfTryJobData.request_time >= start_date,
          WfTryJobData.request_time < end_date).fetch()
    else:
      wf_try_job_query = WfTryJobData.query(
          WfTryJobData.request_time >= start_date,
          WfTryJobData.request_time < end_date)
      flake_try_job_query = FlakeTryJobData.query(
          FlakeTryJobData.request_time >= start_date,
          FlakeTryJobData.request_time < end_date)
      try_job_data_list = wf_try_job_query.fetch() + flake_try_job_query.fetch()

    # Sort try job data list by most recent request first.
    try_job_data_list.sort(key=lambda x: x.request_time, reverse=True)

    try_jobs_in_progress = []
    try_jobs_with_error = []
    successfully_completed_try_jobs = []

    for try_job_data in try_job_data_list:
      display_data = _FormatDisplayData(try_job_data)

      if not try_job_data.end_time and not try_job_data.error:
        display_data['elapsed_time'] = (
            _FormatDuration(try_job_data.request_time, time_util.GetUTCNow()) if
            try_job_data.request_time else None)
        display_data['status'] = (
            'running' if try_job_data.start_time else 'pending')
        try_jobs_in_progress.append(display_data)
      elif try_job_data.error:
        display_data['error'] = try_job_data.error['message']
        # It is possible end_time is not available if the error was timeout.
        display_data['execution_time'] = _FormatDuration(
            try_job_data.start_time, try_job_data.end_time)
        try_jobs_with_error.append(display_data)
      else:
        display_data['culprit_found'] = (
            bool(try_job_data.culprits) if isinstance(
                try_job_data, WfTryJobData) else 'N/A')
        display_data['execution_time'] = _FormatDuration(
            try_job_data.start_time, try_job_data.end_time)
        successfully_completed_try_jobs.append(display_data)

    data = {
        'start_date': time_util.FormatDatetime(start_date),
        'end_date': time_util.FormatDatetime(end_date),
        'category': category,
        'try_jobs_in_progress': try_jobs_in_progress,
        'try_jobs_with_error': try_jobs_with_error,
        'successfully_completed_try_jobs': successfully_completed_try_jobs
    }

    return {
        'template': 'try_job_dashboard.html',
        'data': data
    }
