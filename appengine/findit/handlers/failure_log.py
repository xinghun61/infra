# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from base_handler import BaseHandler
from base_handler import Permission
from waterfall import buildbot
from waterfall import masters
from model.wf_step import WfStep


class FailureLog(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandleGet(self):
    """Fetch the log of a failed step as a JSON result."""
    url = self.request.get('url', '')
    step_info = buildbot.ParseStepUrl(url)
    if not step_info:
      return BaseHandler.CreateError(
          'Url "%s" is not pointing to a step.' % url, 501)
    master_name, builder_name, build_number, step_name = step_info

    step = WfStep.Get(master_name, builder_name, build_number,
                      step_name)
    
    if not step:
      return BaseHandler.CreateError('No failure log available.', 404)  
    data = {
          'master_name': master_name,
          'builder_name': builder_name,
          'build_number': build_number,
          'step_name': step_name,         
          'step_logs': step.log_data,
    }
    return {'template': 'failure_log.html', 'data': data}
