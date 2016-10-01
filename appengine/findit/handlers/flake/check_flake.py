# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import users

from common import constants
from common.base_handler import BaseHandler
from common.base_handler import Permission
from model.analysis_status import STATUS_TO_DESCRIPTION
from waterfall.flake.initialize_flake_pipeline import ScheduleAnalysisIfNeeded


class CheckFlake(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    # Get input parameters.
    # pylint: disable=W0612
    master_name = self.request.get('master_name').strip()
    builder_name = self.request.get('builder_name').strip()
    build_number = int(self.request.get('build_number').strip())
    step_name = self.request.get('step_name').strip()
    test_name = self.request.get('test_name').strip()
    force = (users.is_current_user_admin() and
             self.request.get('force') == '1')
    allow_new_analysis = self.IsCorpUserOrAdmin()

    master_flake_analysis = ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, step_name, test_name,
        allow_new_analysis, force=force,
        queue_name=constants.WATERFALL_ANALYSIS_QUEUE)

    if not master_flake_analysis:  # pragma: no cover.
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
        'analysis_status': STATUS_TO_DESCRIPTION.get(
            master_flake_analysis.status),
        'suspected_flake_build_number': (
            master_flake_analysis.suspected_flake_build_number),
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'step_name': step_name,
        'test_name': test_name,
    }

    build_numbers = []
    pass_rates = []
    coordinates = []

    for data_point in master_flake_analysis.data_points:
      coordinates.append((data_point.build_number, data_point.pass_rate))

    # Order by build number from earliest to latest.
    coordinates.sort(key=lambda x: x[0])

    data['pass_rates'] = coordinates

    return {
        'template': 'flake/result.html',
        'data': data
    }
