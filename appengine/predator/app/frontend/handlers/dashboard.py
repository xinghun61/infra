# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import OrderedDict

from datetime import datetime
from datetime import time
from datetime import timedelta
import json

from gae_libs import dashboard_util
from gae_libs.handlers.base_handler import BaseHandler, Permission
from libs import time_util


_PAGE_SIZE = 100


class DashBoard(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  @property
  def crash_analysis_cls(self):
    raise NotImplementedError()

  @property
  def client(self):
    raise NotImplementedError()

  @property
  def template(self):
    return 'dashboard.html'

  @property
  def property_to_value_converter(self):
    return OrderedDict([
        ('found_suspects', lambda x: x == 'yes'),
        ('has_regression_range', lambda x: x == 'yes'),
        ('suspected_cls_triage_status', int),
        ('regression_range_triage_status', int),
        ('signature', lambda x: x.strip().replace('%20', ' ')),])

  def Filter(self, start_date=None, end_date=None):
    """Filters crash analysis by both unequal and equal filters."""
    query = self.crash_analysis_cls.query(
        self.crash_analysis_cls.requested_time >= start_date,
        self.crash_analysis_cls.requested_time < end_date)

    for equal_filter, converter in self.property_to_value_converter.iteritems():
      if not self.request.get(equal_filter):
        continue

      query = query.filter(
          getattr(self.crash_analysis_cls, equal_filter) ==
          converter(self.request.get(equal_filter)))

    return query

  def CrashDataToDisplay(self, crash_analyses):
    """Gets the crash data to display."""
    if not crash_analyses:
      return []

    crashes = []
    for crash in crash_analyses:
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

    return crashes

  def HandleGet(self):
    """Shows crash analysis results in an HTML page."""
    start_date, end_date = dashboard_util.GetStartAndEndDates(
        self.request.get('start_date'), self.request.get('end_date'))

    query = self.Filter(start_date, end_date)

    try:
      page_size = int(self.request.get('n'))
    except (ValueError, TypeError):
      page_size = _PAGE_SIZE

    # TODO(katesonia): Add pagination here.
    crash_analyses = query.order(
        -self.crash_analysis_cls.requested_time).fetch(page_size)

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
        'crashes': self.CrashDataToDisplay(crash_analyses),
        'signature': self.request.get('signature')
    }

    return {
        'template': self.template,
        'data': data
    }
