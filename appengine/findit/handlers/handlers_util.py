# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import copy

from model import wf_analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from waterfall import buildbot
from waterfall import waterfall_config


FLAKY = 'Flaky'


def GenerateSwarmingTasksData(master_name, builder_name, build_number):
  """Collects info for all related swarming tasks.

  Returns: A dict as below:
      {
          'step1': {
              'swarming_tasks': [
                  {
                      'status': 'Completed',
                      'task_id': 'task1',
                      'task_url': (
                          'https://chromium-swarm.appspot.com/user/task/task1'),
                      'tests': ['test2']
                  },
                  {
                      'status': 'Completed',
                      'task_id': 'task0',
                      'task_url': (
                          'https://chromium-swarm.appspot.com/user/task/task0'),
                      'tests': ['test1']
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
        for key, test_names in key_test_map.iteritems():
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

          for test_name in test_names:
            tests[test_name] = copy.deepcopy(task_info)

          task_info['tests'] = test_names
          step_tasks_info.append(task_info)

  return tasks_info


def _GetTryJobBuildNumber(url):
  build_keys = buildbot.ParseBuildUrl(url)
  return build_keys[2]


def _GetCulpritInfoForTryJobResult(try_job_key, culprits_info):
  referred_build_keys = try_job_key.split('/')
  try_job = WfTryJob.Get(*referred_build_keys)
  if not try_job:
    return

  if try_job.compile_results:
    try_job_result = try_job.compile_results[-1]
  elif try_job.test_results:
    try_job_result = try_job.test_results[-1]
  else:
    try_job_result = None

  additional_tests_culprit_info = {}
  for culprit_info in culprits_info.values():
    if culprit_info['try_job_key'] != try_job_key:
      continue

    # Only include try job result for reliable tests.
    # Flaky tests have been marked as 'Flaky'.
    culprit_info['status'] = (
        wf_analysis_status.TRY_JOB_STATUS_TO_DESCRIPTION[try_job.status]
        if not culprit_info.get('status') else culprit_info['status'])

    if try_job_result and culprit_info['status'] != FLAKY:
      if try_job_result.get('url'):
        culprit_info['try_job_url'] = try_job_result['url']
        culprit_info['try_job_build_number'] = (
            _GetTryJobBuildNumber(try_job_result['url']))
      if try_job_result.get('culprit'):
        try_job_culprits = try_job_result['culprit']
        step = culprit_info['step']
        test = culprit_info['test']

        if test == 'N/A':  # Only step level.
          if try_job_culprits.get(step, {}).get('tests'):
            # try job results has specified tests.
            step_culprits = try_job_culprits[step]['tests']
            for test_name, try_job_culprit in step_culprits.iteritems():
              additional_test_key = '%s-%s' % (step, test_name)
              additional_tests_culprit_info[additional_test_key] = {
                  'step': step,
                  'test': test_name,
                  'try_job_key': try_job_key,
                  'status': culprit_info['status'],
                  'try_job_url': culprit_info['try_job_url'],
                  'try_job_build_number': culprit_info['try_job_build_number'],
                  'revision': try_job_culprit.get('revision'),
                  'commit_position': try_job_culprit.get('commit_position'),
                  'review_url': try_job_culprit.get('review_url')
              }
            continue
          else:
            # For historical culprit found by try job for compile,
            # step name is not recorded.
            culprit = try_job_culprits.get(step) or try_job_culprits
        elif test in try_job_culprits.get(step, {}).get('tests'):
          culprit = try_job_culprits[step]['tests'][test]
        else:   # pragma: no cover
          continue  # No culprit for test found.

        culprit_info['revision'] = culprit.get('revision')
        culprit_info['commit_position'] = culprit.get('commit_position')
        culprit_info['review_url'] = culprit.get('review_url')

  if additional_tests_culprit_info:
    for key, test_culprit_info in additional_tests_culprit_info.iteritems():
      culprits_info.pop(test_culprit_info['step'], None)
      culprits_info[key] = test_culprit_info


def _UpdateFlakiness(step_name, failure_key_set, culprits_info):
  for failure_key in failure_key_set:
    build_keys = failure_key.split('/')
    task = WfSwarmingTask.Get(*build_keys, step_name=step_name)
    if not task:
      continue
    classified_tests = task.classified_tests
    for culprit_info in culprits_info.values():
      if (culprit_info['try_job_key'] == failure_key and
          culprit_info['test'] in classified_tests.get('flaky_tests', [])):
        culprit_info['status'] = FLAKY


def GetAllTryJobResults(master_name, builder_name, build_number):
  culprits_info = {}
  try_job_keys = set()

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis:
    return culprits_info

  failure_result_map = analysis.failure_result_map
  if failure_result_map:
    # failure_result_map uses step_names as keys and saves referred try_job_keys
    # If non-swarming, step_name and referred_try_job_key match directly as:
    # step_name: try_job_key
    # If swarming, add one more layer of tests, so the format would be:
    # step_name: {
    #     test_name1: try_job_key1,
    #     test_name2: try_job_key2,
    #     ...
    # }
    for step_name, step_failure_result_map in failure_result_map.iteritems():
      if isinstance(step_failure_result_map, dict):
        step_refering_keys = set()
        for failed_test, try_job_key in step_failure_result_map.iteritems():
          step_test_key = '%s-%s' % (step_name, failed_test)
          culprits_info[step_test_key] = {
              'step': step_name,
              'test': failed_test,
              'try_job_key': try_job_key
          }
          step_refering_keys.add(try_job_key)

        _UpdateFlakiness(step_name, step_refering_keys, culprits_info)
        try_job_keys.update(step_refering_keys)
      else:
        culprits_info[step_name] = {
            'step': step_name,
            'test': 'N/A',
            'try_job_key': step_failure_result_map
        }
        try_job_keys.add(step_failure_result_map)

    for try_job_key in try_job_keys:
      _GetCulpritInfoForTryJobResult(try_job_key, culprits_info)

  return culprits_info
