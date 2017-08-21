# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import OrderedDict

from analysis.type_enums import CrashClient
from common.model.clusterfuzz_analysis import ClusterfuzzAnalysis
from frontend.handlers.dashboard import DashBoard
from libs.gitiles.gitiles_repository import GitilesRepository
from gae_libs.handlers.base_handler import Permission
from gae_libs.http.http_client_appengine import HttpClientAppengine


def GetCommitsInRegressionRange(regression_range, get_repository):
  repository = get_repository(regression_range['repo_url'])
  return len(repository.GetCommitsBetweenRevisions(
      regression_range['old_revision'],
      regression_range['new_revision']))


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

    get_repository = GitilesRepository.Factory(HttpClientAppengine())
    crashes = []
    for crash in crash_analyses:
      display_data = {
          'signature': crash.signature,
          'testcase_id': crash.testcase_id,
          'version': crash.crashed_version,
          'job_type': crash.job_type,
          'crash_type': crash.crash_type,
          'platform': crash.platform,
          'sanitizer': crash.sanitizer,
          'regression_range': [crash.regression_range['old_revision'],
                               crash.regression_range['new_revision']],
          'commits': GetCommitsInRegressionRange(crash.regression_range,
                                                 get_repository),
          'error_name': crash.error_name or '',
          'suspected_cls': (crash.result.get('suspected_cls', [])
                            if crash.result else []),
          'suspected_project': (crash.result.get('suspected_project', '')
                                if crash.result else ''),
          'suspected_components': (crash.result.get('suspected_components', [])
                                   if crash.result else []),
          'key': crash.key.urlsafe(),
      }
      crashes.append(display_data)

    crashes.sort(key=lambda crash: crash['signature'])
    return crashes
