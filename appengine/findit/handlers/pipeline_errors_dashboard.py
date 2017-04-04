# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import time
from datetime import timedelta

from google.appengine.ext import ndb

from common.waterfall import failure_type
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model.wf_analysis import WfAnalysis


_COUNT = 500


def _GetStartEndDates(start, end, midnight_today):
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


def _Serialize(analysis):
  return {
      'master_name': analysis.master_name,
      'builder_name': analysis.builder_name,
      'build_number': analysis.build_number,
      'analysis_type': failure_type.GetDescriptionForFailureType(
          analysis.failure_type),
      'build_start_time': time_util.FormatDatetime(analysis.build_start_time),
  }


class PipelineErrorsDashboard(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Lists WfAnalysis entities detected to have been aborted."""
    midnight_today = datetime.combine(time_util.GetUTCNow(), time.min)
    start = self.request.get('start_date')
    end = self.request.get('end_date')

    start_date, end_date = _GetStartEndDates(start, end, midnight_today)

    analyses = WfAnalysis.query(
        ndb.AND(
            WfAnalysis.build_start_time >= start_date,
            WfAnalysis.build_start_time < end_date,
            WfAnalysis.aborted == True)).order(
                -WfAnalysis.build_start_time).fetch(_COUNT)

    analyses_data = []

    for analysis in analyses:
      analyses_data.append(_Serialize(analysis))

    data = {
        'start_date': time_util.FormatDatetime(start_date),
        'end_date': time_util.FormatDatetime(end_date),
        'analyses': analyses_data,
    }

    return {
        'template': 'pipeline_errors_dashboard.html',
        'data': data
    }
