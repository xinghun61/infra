# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from base_handler import BaseHandler
from base_handler import Permission
from model import wf_analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from waterfall import buildbot


SWARMING_BASE_URL = 'https://chromium-swarm.appspot.com/user/task'


def _GenerateSwarmingTasksData(master_name, builder_name, build_number):
  task_info = defaultdict(dict)

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis:
    return task_info

  failure_result_map = analysis.failure_result_map
  if failure_result_map:
    for step_name, failure in failure_result_map.iteritems():
      if isinstance(failure, dict):
        task = WfSwarmingTask.Get(
            master_name, builder_name, build_number, step_name)
        if task:
          task_info[step_name]['status'] = (
              wf_analysis_status.SWARMING_STATUS_TO_DESCRIPTION.get(
                  task.status))
          if task.task_id:
            task_info[step_name]['task_id'] = task.task_id
            task_info[step_name]['task_url'] = '%s/%s' % (
                SWARMING_BASE_URL, task.task_id)
  return task_info

class SwarmingTask(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Get the information about swarming tasks for failed steps."""
    url = self.request.get('url').strip()
    build_keys = buildbot.ParseBuildUrl(url)

    if not build_keys:  # pragma: no cover
      return {'data': {}}

    data = _GenerateSwarmingTasksData(*build_keys)
    return {'data': data}

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
