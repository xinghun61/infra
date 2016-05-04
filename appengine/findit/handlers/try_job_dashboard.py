# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
from datetime import time
from datetime import timedelta

from common.base_handler import BaseHandler
from common.base_handler import Permission
from model.wf_try_job_data import WfTryJobData


# TODO(lijeffrey): Refactor formatting functions into a separate module that
# can be shared across Findit.
def _RemoveMicrosecondsFromDelta(delta):
  """Returns a timedelta object without microseconds based on delta."""
  return delta - timedelta(microseconds=delta.microseconds)


def _FormatTimedelta(delta):
  if not delta:
    return None
  hours, remainder = divmod(delta.seconds, 3600)
  minutes, seconds = divmod(remainder, 60)
  return '%02d:%02d:%02d' % (hours, minutes, seconds)


def _FormatDatetime(date):
  if not date:
    return None
  else:
    return date.strftime('%Y-%m-%d %H:%M:%S UTC')


class TryJobDashboard(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Shows a list of Findit try job results and statuses in an HTML page."""
    midnight_today = datetime.combine(datetime.utcnow(), time.min)
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
    try_jobs_in_progress = []
    try_jobs_with_error = []
    successfully_completed_try_jobs = []

    for try_job_data in try_job_data_list:
      try_job_display_data = {
          'master_name': try_job_data.master_name,
          'builder_name': try_job_data.builder_name,
          'build_number': try_job_data.build_number,
          'try_job_type': try_job_data.try_job_type,
          'start_time': _FormatDatetime(try_job_data.start_time),
          'request_time': _FormatDatetime(try_job_data.request_time),
          'try_job_url': try_job_data.try_job_url
      }

      if not try_job_data.end_time and not try_job_data.error:
        try_job_display_data['elapsed_time'] = (
            _FormatTimedelta(datetime.utcnow() - try_job_data.request_time) if
            try_job_data.request_time else None)

        try_job_display_data['status'] = (
            'running' if try_job_data.start_time else 'pending')
        try_jobs_in_progress.append(try_job_display_data)
      elif try_job_data.error:
        try_job_display_data['error'] = try_job_data.error['message']
        # It is possible end_time is not available if the error was timeout.
        try_job_display_data['end_time'] = _FormatDatetime(
            try_job_data.end_time)
        try_jobs_with_error.append(try_job_display_data)
      else:
        try_job_display_data['culprit_found'] = bool(try_job_data.culprits)
        try_job_display_data['end_time'] = (
            _FormatDatetime(try_job_data.end_time))
        successfully_completed_try_jobs.append(try_job_display_data)

    data = {
        'start_date': _FormatDatetime(start_date),
        'end_date': _FormatDatetime(end_date),
        'try_jobs_in_progress': try_jobs_in_progress,
        'try_jobs_with_error': try_jobs_with_error,
        'successfully_completed_try_jobs': successfully_completed_try_jobs
    }

    return {
        'template': 'try_job_dashboard.html',
        'data': data
    }
