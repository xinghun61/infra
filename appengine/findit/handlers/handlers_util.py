# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import copy

from handlers import result_status
from model import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from waterfall import buildbot
from waterfall import waterfall_config


def _GetFailureResultMap(master_name, builder_name, build_number):
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis:
    return None, None

  return analysis.result, analysis.failure_result_map


def _GetAllTestsForASwarmingTask(task_key, step_failure_result_map):
  all_tests = set()
  for test_name, test_task_key in step_failure_result_map.iteritems():
    if task_key == test_task_key:
      all_tests.add(test_name)
  return list(all_tests)


def _GenerateSwarmingTasksData(failure_result_map):
  """Collects info for all related swarming tasks.

  Returns: A dict as below:
      {
          'step1': {
              'swarming_tasks': {
                  'm/b/121': {
                      'task_info': {
                          'status': 'Completed',
                          'task_id': 'task1',
                          'task_url': ('https://chromium-swarm.appspot.com/user'
                                       '/task/task1')
                      },
                      'all_tests': ['test2', 'test3', 'test4'],
                      'reliable_tests': ['test2'],
                      'flaky_tests': ['test3', 'test4']
                  }
              }
          },
          'step2': {
              'swarming_tasks': {
                  'm/b/121': {
                      'task_info': {
                          'status': 'Pending'
                      },
                      'all_tests': ['test1']
                  }
              }
          },
          'step3': {
              'swarming_tasks': {
                  'm/b/121': {
                      'task_info': {
                          'status': 'No swarming rerun found'
                      },
                      'all_tests': ['test1']
                  }
              }
          }
      }
  """

  tasks_info = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

  swarming_server = waterfall_config.GetSwarmingSettings()['server_host']
  for step_name, failure in failure_result_map.iteritems():
    step_tasks_info = tasks_info[step_name]['swarming_tasks']
    if isinstance(failure, dict):
      # Only swarming test failures have swarming re-runs.
      swarming_task_keys = set(failure.values())

      for key in swarming_task_keys:
        task_dict = step_tasks_info[key]
        referred_build_keys = key.split('/')
        task = WfSwarmingTask.Get(*referred_build_keys, step_name=step_name)
        if not task:  # In case task got manually removed from data store.
          task_info = {
              'status': result_status.NO_SWARMING_TASK_FOUND
          }
          task_dict['all_tests'] = _GetAllTestsForASwarmingTask(key, failure)
        else:
          task_info = {
              'status': task.status
          }

          task_dict['all_tests'] = (
              _GetAllTestsForASwarmingTask(key, failure)
              if not (task.parameters and task.parameters.get('tests'))
              else task.parameters['tests'])

          # Get the step name without platform.
          # This value should have been saved in task.parameters;
          # in case of no such value saved, split the step_name.
          task_dict['ref_name'] = (
              step_name.split()[0]
              if not task.parameters or not task.parameters.get('ref_name')
              else task.parameters['ref_name'])

          if task.task_id:  # Swarming rerun has started.
            task_info['task_id'] = task.task_id
            task_info['task_url'] = 'https://%s/user/task/%s' % (
                swarming_server, task.task_id)
          if task.classified_tests:
            # Swarming rerun has completed.
            # Use its result to get reliable and flaky tests.
            # If task has not completed, there will be no try job yet,
            # the result will be grouped in unclassified failures temporarily.
            task_dict['reliable_tests'] = task.classified_tests.get(
                'reliable_tests', [])
            task_dict['flaky_tests'] = task.classified_tests.get(
                'flaky_tests', [])

        task_dict['task_info'] = task_info
    else:
      step_tasks_info[failure] = {
          'task_info': {
              'status': result_status.NON_SWARMING_NO_RERUN
          }
      }

  return tasks_info


def GetSwarmingTaskInfo(master_name, builder_name, build_number):
  _, failure_result_map = _GetFailureResultMap(
      master_name, builder_name, build_number)
  return (
      _GenerateSwarmingTasksData(failure_result_map)
      if failure_result_map else {})


def _GetTryJobBuildNumber(url):
  build_keys = buildbot.ParseBuildUrl(url)
  return build_keys[2]


def _OrganizeTryJobResultByCulprits(try_job_culprits):
  """Re-organize try job culprits by revision.

  Args:
    try_job_culprits (dict): A dict of culprits for one step organized by test:
        {
            'tests': {
                'a_test1': {
                    'revision': 'rev1',
                    'commit_position': '1',
                    'review_url': 'url_1'
                },
                'a_test2': {
                    'revision': 'rev1',
                    'commit_position': '1',
                    'review_url': 'url_1'
                }
            }
        }
  Returns:
    A dict of culprits for one step organized by revison:
        {
            'rev1': {
                'revision': 'rev1',
                'commit_position': '1',
                'review_url': 'url_1',
                'tests': ['a_test1', 'a_test2']
            }
        }
  """
  if not try_job_culprits or not try_job_culprits.get('tests'):
    return {}

  organized_culprits = {}
  for test_name, culprit in try_job_culprits['tests'].iteritems():
    revision = culprit['revision']
    if organized_culprits.get(revision):
      organized_culprits[revision]['failed_tests'].append(test_name)
    else:
      organized_culprits[revision] = culprit
      organized_culprits[revision]['failed_tests'] = [test_name]

  return organized_culprits


def _GetCulpritInfoForTryJobResultForTest(try_job_key, culprits_info):
  referred_build_keys = try_job_key.split('/')
  try_job = WfTryJob.Get(*referred_build_keys)
  if not try_job or try_job.compile_results:
    return

  try_job_result = try_job.test_results[-1] if try_job.test_results else None

  for step_try_jobs in culprits_info.values():
    # If try job found different culprits for each test, split tests by culprit.
    additional_tests_culprit_info = []
    for try_job_info in step_try_jobs['try_jobs']:
      if (try_job_key != try_job_info['try_job_key']
          or try_job_info.get('status')):
        # Conditions that try_job_info has status are:
        # If there is no swarming task, there won't be try job;
        # If the swarming task is not completed yet, there won't be try job yet;
        # If there are flaky tests found, those tests will be marked as flaky,
        # and no try job for them will be triggered.
        continue

      try_job_info['status'] = try_job.status
      if try_job_result:
        # Needs to use ref_name to match step_name in try job.
        ref_name = try_job_info['ref_name']
        # Saves try job information.
        if try_job_result.get('url'):  # pragma: no cover
          try_job_info['try_job_url'] = try_job_result['url']
          try_job_info['try_job_build_number'] = (
              _GetTryJobBuildNumber(try_job_result['url']))

        if (try_job_result.get('culprit') and
            try_job_result['culprit'].get(ref_name)):
          # Saves try job culprits information.

          # Uses culprits to group tests.
          culprit_tests_map = _OrganizeTryJobResultByCulprits(
              try_job_result['culprit'][ref_name])
          unrgouped_tests = try_job_info['tests']
          list_of_culprits = []
          for culprit_info in culprit_tests_map.values():
            failed_tests = culprit_info['failed_tests']
            list_of_culprits.append(culprit_info)
            # Gets tests that haven't been grouped.
            unrgouped_tests = list(
                set(unrgouped_tests) ^ set(failed_tests))
            if not unrgouped_tests:
              # All tests have been grouped.
              break

          index_start = 1
          if unrgouped_tests:
            # There are tests don't have try job culprits.
            # Group these tests together.
            # Save them in current try_job_info.
            try_job_info['tests'] = unrgouped_tests
            try_job_info['culprit'] = {}
            # Saves all the tests that have culprits later.
            index_start = 0
          else:
            # Saves the first culprit in current try_job_info.
            # Saves all the other culprits later.
            try_job_info['culprit'] = {
                'revision': list_of_culprits[0]['revision'],
                'commit_position': list_of_culprits[0]['commit_position'],
                'review_url': list_of_culprits[0]['review_url']
            }
            try_job_info['tests'] = list_of_culprits[0]['failed_tests']

          for n in xrange(index_start, len(list_of_culprits)):
            # Appends the rest of test groups to step_try_jobs['try_jobs'].
            iterate_culprit = list_of_culprits[n]
            tmp_try_job_info = copy.deepcopy(try_job_info)
            tmp_try_job_info['culprit'] = {
                'revision': iterate_culprit['revision'],
                'commit_position': iterate_culprit['commit_position'],
                'review_url': iterate_culprit['review_url']
            }
            tmp_try_job_info['tests'] = iterate_culprit['failed_tests']
            additional_tests_culprit_info.append(tmp_try_job_info)

    if additional_tests_culprit_info:
      step_try_jobs['try_jobs'].extend(additional_tests_culprit_info)


def _UpdateTryJobInfoBasedOnSwarming(step_tasks_info, try_jobs):
  """
  Args:
    step_tasks_info (dict): A dict of swarming task info for this step.
        It is the result from _GenerateSwarmingTasksData.
    try_jobs (list): A list to save try job data for the step, format as below:
        [
          {
              'try_job_key': 'm/b/120'
          },
          {
              'try_job_key': 'm/b/121'
          },
          ...
        ]
  """
  additional_flakiness_list = []
  for try_job in try_jobs:
    try_job_key = try_job['try_job_key']
    task = step_tasks_info.get('swarming_tasks', {}).get(try_job_key)

    if task['task_info']['status'] != analysis_status.COMPLETED:
      # There is someting wrong with swarming task or it's not done yet,
      # no try job yet or ever.
      try_job['status'] = result_status.NO_TRY_JOB_REASON_MAP[
          task['task_info']['status']]
      try_job['tests'] = task.get('all_tests', [])
    else:
      # Swarming task is completed, group tests according to task result.
      try_job['ref_name'] = task['ref_name']
      if task.get('reliable_tests'):
        try_job['tests'] = task['reliable_tests']
        if task.get('flaky_tests'):
          # Split this try job into two groups: flaky group and reliable group.
          flaky_try_job = copy.deepcopy(try_job)
          flaky_try_job['status'] = result_status.FLAKY
          flaky_try_job['tests'] = task['flaky_tests']
          flaky_try_job['task_id'] = task['task_info']['task_id']
          flaky_try_job['task_url'] = task['task_info']['task_url']
          additional_flakiness_list.append(flaky_try_job)
      elif task.get('flaky_tests'):  # pragma: no cover
        # All Flaky.
        try_job['status'] = result_status.FLAKY
        try_job['tests'] = task['flaky_tests']

    if task['task_info'].get('task_id'):
      try_job['task_id'] = task['task_info']['task_id']
      try_job['task_url'] = task['task_info']['task_url']

  try_jobs.extend(additional_flakiness_list)


def _GetAllTryJobResultsForTest(failure_result_map, tasks_info):
  culprits_info = defaultdict(lambda: defaultdict(list))
  if not tasks_info:
    return culprits_info

  try_job_keys = set()
  for step_name, step_failure_result_map in failure_result_map.iteritems():
    try_jobs = culprits_info[step_name]['try_jobs']

    if isinstance(step_failure_result_map, dict):
      step_try_job_keys = set()
      for try_job_key in step_failure_result_map.values():
        if try_job_key not in step_try_job_keys:
          try_job_dict = {
              'try_job_key': try_job_key
          }
          try_jobs.append(try_job_dict)
          step_try_job_keys.add(try_job_key)
      try_job_keys.update(step_try_job_keys)
    else:
      # Try job should only be triggered for swarming tests, because we cannot
      # identify flaky tests for non-swarming tests.
      try_job_dict = {
          'try_job_key': step_failure_result_map
      }
      try_jobs.append(try_job_dict)

    _UpdateTryJobInfoBasedOnSwarming(tasks_info[step_name], try_jobs)

  for try_job_key in try_job_keys:
    _GetCulpritInfoForTryJobResultForTest(try_job_key, culprits_info)

  return culprits_info


def _GetTryJobResultForCompile(failure_result_map):
  try_job_key = failure_result_map['compile']
  referred_build_keys = try_job_key.split('/')
  culprit_info = defaultdict(lambda: defaultdict(list))

  try_job = WfTryJob.Get(*referred_build_keys)
  if not try_job or try_job.test_results:
    return culprit_info

  try_job_result = (
      try_job.compile_results[-1] if try_job.compile_results else None)

  compile_try_job = {
      'try_job_key': try_job_key,
      'status': try_job.status
  }

  if try_job_result:
    if try_job_result.get('url'):
      compile_try_job['try_job_url'] = try_job_result['url']
      compile_try_job['try_job_build_number'] = (
          _GetTryJobBuildNumber(try_job_result['url']))
    if try_job_result.get('culprit', {}).get('compile'):
      compile_try_job['culprit'] = try_job_result['culprit']['compile']

  culprit_info['compile']['try_jobs'].append(compile_try_job)
  return culprit_info


def GetAllTryJobResults(master_name, builder_name, build_number):
  culprits_info = {}
  is_test_failure = True

  analysis_result, failure_result_map = _GetFailureResultMap(
      master_name, builder_name, build_number)

  if failure_result_map:
    for step_name in failure_result_map:
      if step_name.lower() == 'compile':
        is_test_failure = False
        break
    if is_test_failure:
      tasks_info = _GenerateSwarmingTasksData(failure_result_map)
      culprits_info = _GetAllTryJobResultsForTest(
          failure_result_map, tasks_info)
    else:
      culprits_info = _GetTryJobResultForCompile(failure_result_map)
  elif analysis_result:
    for failure in analysis_result['failures']:
      step_name = failure['step_name']
      tests = []
      for test in failure.get('tests', []):
        tests.append(test['test_name'])

      culprits_info[step_name] = {
          'try_jobs': [
              {
                  'status': result_status.NO_FAILURE_RESULT_MAP,
                  'tests': tests
              }
          ]
      }
  return culprits_info
