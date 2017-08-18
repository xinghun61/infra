# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import OrderedDict

from analysis.type_enums import CrashClient
from common.model.clusterfuzz_analysis import ClusterfuzzAnalysis
from frontend.handlers.dashboard import DashBoard
from gae_libs.handlers.base_handler import Permission


class ClusterfuzzDashBoard(DashBoard):
  PERMISSION_LEVEL = Permission.ADMIN

  @property
  def crash_analysis_cls(self):
    return ClusterfuzzAnalysis

  @property
  def client(self):
    return CrashClient.CLUSTERFUZZ

  @property
  def template(self):
    return 'clusterfuzz_dashboard.html'

  @property
  def property_to_value_converter(self):
    return OrderedDict([
        ('found_suspects', lambda x: x == 'yes'),
        ('has_regression_range', lambda x: x == 'yes'),
        ('suspected_cls_triage_status', int),
        ('regression_range_triage_status', int),
        ('testcase_id', lambda x: x),])

  def CrashDataToDisplay(self, crash_analyses):
    """Gets the crash data to display."""
    if not crash_analyses:
      return []

    crashes = []
    for crash in crash_analyses:
      display_data = {
          'signature': crash.signature,
          'testcase_id': crash.testcase_id,
          'version': crash.crashed_version,
          'job_type': crash.job_type,
          'platform': crash.platform,
          'regression_range': crash.regression_range,
          'suspected_cls': (crash.result.get('suspected_cls', [])
                            if crash.result else []),
          'suspected_project': (crash.result.get('suspected_project', '')
                                if crash.result else ''),
          'suspected_components': (crash.result.get('suspected_components', [])
                                   if crash.result else []),
          'key': crash.key.urlsafe()
      }
      crashes.append(display_data)

    crashes.sort(key=lambda crash: crash['signature'])
    return crashes
