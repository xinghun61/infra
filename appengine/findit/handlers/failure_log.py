# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json

from base_handler import BaseHandler
from base_handler import Permission
from model.wf_step import WfStep
from waterfall import buildbot


class FailureLog(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def _GetFormattedJsonLogIfSwarming(self, step):
    if not step.isolated or step.log_data == 'flaky':
      return step.log_data

    json_log = json.loads(step.log_data)

    json_test_logs = {}
    for test_name, test_log_encoded in json_log.iteritems():
      json_test_logs[test_name] = base64.b64decode(test_log_encoded)
    # Replaces the '\n's which are introduced by json.dumps.
    return json.dumps(json_test_logs, indent=4).replace(r'\n', '\n        ')

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

    failure_log = self._GetFormattedJsonLogIfSwarming(step)

    data = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'step_name': step_name,
        'step_logs': failure_log,
    }
    return {'template': 'failure_log.html', 'data': data}
