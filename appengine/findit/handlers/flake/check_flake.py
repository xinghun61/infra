# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import users

from common import auth_util
from common import constants
from common import time_util
from common.base_handler import BaseHandler
from common.base_handler import Permission
from model import analysis_status
from waterfall.flake import initialize_flake_pipeline


class CheckFlake(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    master_name = self.request.get('master_name').strip()
    builder_name = self.request.get('builder_name').strip()
    build_number = int(self.request.get('build_number', '0').strip())
    step_name = self.request.get('step_name').strip()
    test_name = self.request.get('test_name').strip()

    if not (master_name and builder_name and build_number and
            step_name and test_name):  # pragma: no cover.
      return self.CreateError(
          'Invalid value of master/builder/build_number/step/test', 400)

    force = (auth_util.IsCurrentUserAdmin() and
             self.request.get('force') == '1')
    allow_new_analysis = self.IsCorpUserOrAdmin()

    analysis = initialize_flake_pipeline.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, step_name, test_name,
        allow_new_analysis, force=force, manually_triggered=True,
        queue_name=constants.WATERFALL_ANALYSIS_QUEUE)

    if not analysis:  # pragma: no cover.
      return {
          'template': 'error.html',
          'data': {
              'error_message':
                  ('You could schedule an analysis for flaky test only after '
                   'you login with google.com account.'),
              'login_url': self.GetLoginUrl(),
          },
          'return_code': 401,
      }

    data = {
        'pass_rates': [],
        'analysis_status': analysis.status_description,
        'suspected_flake_build_number': (
            analysis.suspected_flake_build_number),
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'step_name': step_name,
        'test_name': test_name,
        'request_time': time_util.FormatDatetime(
            analysis.request_time),
        'task_number': len(analysis.data_points),
        'error': analysis.error_message,
        'iterations_to_rerun': analysis.iterations_to_rerun,
    }

    data['pending_time'] = time_util.FormatDuration(
        analysis.request_time,
        analysis.start_time or time_util.GetUTCNow())
    if analysis.status != analysis_status.PENDING:
      data['duration'] = time_util.FormatDuration(
          analysis.start_time,
          analysis.end_time or time_util.GetUTCNow())

    coordinates = []
    for data_point in analysis.data_points:
      coordinates.append([data_point.build_number, data_point.pass_rate])

    # Order by build number from earliest to latest.
    coordinates.sort(key=lambda x: x[0])

    data['pass_rates'] = coordinates
    return {
        'template': 'flake/result.html',
        'data': data
    }
