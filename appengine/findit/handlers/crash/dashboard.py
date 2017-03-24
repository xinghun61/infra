# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import OrderedDict

from datetime import datetime
from datetime import time
from datetime import timedelta
import json

from common.base_handler import BaseHandler, Permission
from gae_libs import dashboard_util
from libs import time_util

_PROPERTY_TO_VALUE_CONVERTER = OrderedDict([
    ('found_suspects', lambda x: x == 'yes'),
    ('has_regression_range', lambda x: x == 'yes'),
    ('suspected_cls_triage_status', int),
    ('regression_range_triage_status', int),
    ('signature', lambda x: x.strip().replace('%20', ' ')),
])

_PAGE_SIZE = 100


class DashBoard(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  @property
  def crash_analysis_cls(self):
    raise NotImplementedError()

  @property
  def client(self):
    raise NotImplementedError()

  def Filter(self, query, start_date=None, end_date=None):
    """Filters crash analysis by both unequal and equal filters."""
    query = self.crash_analysis_cls.query(
        self.crash_analysis_cls.requested_time >= start_date,
        self.crash_analysis_cls.requested_time < end_date)

    for equal_filter, converter in _PROPERTY_TO_VALUE_CONVERTER.iteritems():
      if not self.request.get(equal_filter):
        continue

      query = query.filter(
          getattr(self.crash_analysis_cls, equal_filter) ==
          converter(self.request.get(equal_filter)))

    return query

  def HandleGet(self):
    """Shows crash analysis results in an HTML page."""
    start_date, end_date = dashboard_util.GetStartAndEndDates(
        self.request.get('start_date'), self.request.get('end_date'))

    query = self.Filter(self.crash_analysis_cls.query(), start_date, end_date)

    page_size = self.request.get('n') or _PAGE_SIZE
    # TODO(katesonia): Add pagination here.
    crash_list = query.order(
        -self.crash_analysis_cls.requested_time).fetch(int(page_size))

    crashes = []
    for crash in crash_list:
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
          'key': crash.key.urlsafe()
      }
      crashes.append(display_data)

    data = {
        'start_date': time_util.FormatDatetime(start_date),
        'end_date': time_util.FormatDatetime(end_date),
        'found_suspects': self.request.get('found_suspects', '-1'),
        'has_regression_range': self.request.get('has_regression_range', '-1'),
        'suspected_cls_triage_status': self.request.get(
            'suspected_cls_triage_status', '-1'),
        'regression_range_triage_status': self.request.get(
            'regression_range_triage_status', '-1'),
        'client': self.client,
        'crashes': crashes,
        'signature': self.request.get('signature')
    }

    return {
        'template': 'crash/dashboard.html',
        'data': data
    }
