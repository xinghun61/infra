# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
from datetime import time
from datetime import timedelta
import json

from common.base_handler import BaseHandler, Permission
from lib import time_util
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


_EQUAL_FILTER_TO_CONVERTER = {
    'found_suspects': lambda x: x == 'yes',
    'has_regression_range': lambda x: x == 'yes',
    'suspected_cls_triage_status': int,
    'regression_range_triage_status': int,
}

_DEFAULT_DISPLAY_COUNT = 500


class FracasDashBoard(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Shows Fracas crash analysis results in an HTML page."""
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
      query = FracasCrashAnalysis.query(
          FracasCrashAnalysis.requested_time >= start_date,
          FracasCrashAnalysis.requested_time < end_date
      )
    else:  # pragma: no cover
      # If no start date specified, then get everything up until end_date.
      start_date = None
      query = FracasCrashAnalysis.query(
          FracasCrashAnalysis.requested_time < end_date
      )

    for equal_filter, converter in _EQUAL_FILTER_TO_CONVERTER.iteritems():
      if not self.request.get(equal_filter):
        continue

      query = query.filter(
          getattr(FracasCrashAnalysis, equal_filter) ==
          converter(self.request.get(equal_filter)))

    if self.request.get('count'):
      count = int(self.request.get('count'))
    else:
      count = _DEFAULT_DISPLAY_COUNT

    # TODO(katesonia): Add pagination here.
    fracas_crash_list = query.order(
        -FracasCrashAnalysis.requested_time).fetch(count)
    fracas_crashes = []

    for crash in fracas_crash_list:
      display_data = {
          'signature': crash.signature,
          'version': crash.crashed_version,
          'channel': crash.channel,
          'platform': crash.platform,
          'regression_range': ('' if not crash.has_regression_range else
                               crash.result['regression_range']),
          'suspected_cls': (crash.result.get('suspected_cls', [])
                            if crash.result else []),
          'suspected_project': (crash.result.get('suspected_project', '')
                                if crash.result else ''),
          'suspected_components': (crash.result.get('suspected_components', [])
                                   if crash.result else []),
          'stack_trace': crash.stack_trace,
          'historical_metadata': json.dumps(crash.historical_metadata),
          'key': crash.key.urlsafe()
      }
      fracas_crashes.append(display_data)

    data = {
        'start_date': time_util.FormatDatetime(start_date),
        'end_date': time_util.FormatDatetime(end_date),
        'found_suspects': self.request.get('found_suspects', '-1'),
        'has_regression_range': self.request.get('has_regression_range', '-1'),
        'suspected_cls_triage_status': self.request.get(
            'suspected_cls_triage_status', '-1'),
        'regression_range_triage_status': self.request.get(
            'regression_range_triage_status', '-1'),
        'fracas_crashes': fracas_crashes
    }

    return {
        'template': 'crash/fracas_dashboard.html',
        'data': data
    }
