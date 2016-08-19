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
  PERMISSION_LEVEL = Permission.CORP_USER

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

    master_flake_analysis = ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, step_name,
        test_name, force=force, queue_name=constants.WATERFALL_ANALYSIS_QUEUE)
    data = {
        'success_rates': [],
        'analysis_status': STATUS_TO_DESCRIPTION.get(
            master_flake_analysis.status),
        'suspected_flake_build_number':(
            master_flake_analysis.suspected_flake_build_number)
    }
    zipped = zip(master_flake_analysis.build_numbers,
                 master_flake_analysis.success_rates)
    zipped.sort(key = lambda x: x[0])
    for (build_number, success_rate) in zipped:
      data['success_rates'].append([build_number, success_rate])
    return {
        'template': 'flake/result.html',
        'data': data
    }
