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
from waterfall import waterfall_config


def _GenerateSwarmingTasksData(master_name, builder_name, build_number):
  """Collects info for all related swarming tasks.

  Returns: A dict as below:
      {
          'step1': {
              'swarming_tasks': [
                  {
                      'status': 'Completed',
                      'task_id': 'task1',
                      'task_url': (
                          'https://chromium-swarm.appspot.com/user/task/task1')
                  },
                  {
                      'status': 'Completed',
                      'task_id': 'task0',
                      'task_url': (
                          'https://chromium-swarm.appspot.com/user/task/task0')
                  }
              ],
              'tests': {
                  'test1': {
                      'status': 'Completed',
                      'task_id': 'task0',
                      'task_url': (
                          'https://chromium-swarm.appspot.com/user/task/task0')
                  },
                  'test2': {
                      'status': 'Completed',
                      'task_id': 'task1',
                      'task_url': (
                          'https://chromium-swarm.appspot.com/user/task/task1')
                  }
              }
          },
          'step2': {
              'swarming_tasks': [
                  {
                      'status': 'Pending'
                  }
              ],
              'tests': {
                  'test1': {
                      'status': 'Pending'
                  }
              }
          }
      }
  """
  tasks_info = defaultdict(dict)

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis:
    return tasks_info

  failure_result_map = analysis.failure_result_map
  if failure_result_map:
    for step_name, failure in failure_result_map.iteritems():
      if isinstance(failure, dict):
        # Only trigger swarming task for swarming test failures.
        key_test_map = defaultdict(list)
        for test_name, first_failure_key in failure.iteritems():
          key_test_map[first_failure_key].append(test_name)

        tasks_info[step_name]['swarming_tasks'] = []
        tasks_info[step_name]['tests'] = defaultdict(dict)
        step_tasks_info = tasks_info[step_name]['swarming_tasks']
        tests = tasks_info[step_name]['tests']
        for key in key_test_map:
          referred_build_keys = key.split('/')
          task = WfSwarmingTask.Get(*referred_build_keys, step_name=step_name)
          if not task:
            continue
          task_info = {
              'status': wf_analysis_status.SWARMING_STATUS_TO_DESCRIPTION.get(
                  task.status)
          }
          if task.task_id:
            task_info['task_id'] = task.task_id
            task_info['task_url'] = 'https://%s/user/task/%s' % (
                waterfall_config.GetSwarmingSettings()['server_host'],
                task.task_id)

          step_tasks_info.append(task_info)
          for test_name in key_test_map[key]:
            tests[test_name] = task_info

  return tasks_info

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
