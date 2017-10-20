# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.findit_http_client import FinditHttpClient
from model.flake.flake_try_job_data import FlakeTryJobData
from model.flake.master_flake_analysis import DataPoint
from waterfall import swarming_util
from waterfall.flake import flake_constants


def _GetPassRateAndTries(pass_fail_counts, test_name):
  """Gets the pass rate and tries of a try job's result.

  Args:
    test_name (str): The name of the test to determine the pass rate of.
    pass_fail_counts (dict): A dict in the format:
        {
            test_name: {
                'pass_count': (int),
                'fail_count': (int),
            }
        }

  Returns:
    ((float), (int)): The pass rate (float) and total number of tries (int).
  """
  if pass_fail_counts:
    test_results = pass_fail_counts[test_name]
    pass_count = test_results['pass_count']
    fail_count = test_results['fail_count']
    tries = pass_count + fail_count
    pass_rate = float(pass_count) / tries
  else:
    pass_rate = flake_constants.PASS_RATE_TEST_NOT_FOUND
    tries = 0

  return pass_rate, tries


def GetSwarmingTaskIdForTryJob(report, revision, step_name, test_name):
  """Check json output for each task and return id of the one with test result.

  Args:
    report (dict): A dict in the format:
        {
            'result': {
                revision: {
                    step_name: {
                        'valid': (bool),
                        'step_metadata': (dict),
                        'pass_fail_counts': {
                            test_name: {
                                'pass_count': (int),
                                'fail_count': (int),
                            }
                        }
                    }
                }
            }
        }
      revision (str): The git hash the try job ran.
      step_name (str): The name of the step the flaky test was found on.
      test_name (str): The name of the flaky test.

  Returns:
    The swarming task id (str) that the try job ran to determine the pass rate,
    or None if not found.
  """
  if not report:
    return None

  http_client = FinditHttpClient()

  step_result = report.get('result', {}).get(revision, {}).get(step_name, {})
  pass_fail_counts = step_result.get('pass_fail_counts', {}).get(test_name)
  task_ids = step_result.get('step_metadata', {}).get('swarm_task_ids', [])

  if len(task_ids) == 1:
    return task_ids[0]

  if not pass_fail_counts:  # Test doesn't exist.
    return task_ids[0] if task_ids else None

  for task_id in task_ids:
    output_json = swarming_util.GetIsolatedOutputForTask(task_id, http_client)
    if output_json:
      for data in output_json.get('per_iteration_data', []):
        # If this task doesn't have result, per_iteration_data will look like
        # [{}, {}, ...]
        if data:
          return task_id

  return None


def IsTryJobResultValid(result_at_revision, step_name):
  """Checks if a flake try job result is valid.

  Args:
    result_at_revision (dict): The result of running at a revision. For example,
      {
         'browser_tests': {
              'status': 'failed',
              'failures': ['TabCaptureApiTest.FullscreenEvents'],
              'valid': True,
              'pass_fail_counts': {
                  'TabCaptureApiTest.FullscreenEvents': {
                      'pass_count': 28,
                      'fail_count': 72
                  }
              },
              'step_metadata': {
                  'task_ids': [],
                  ...
              }
          }
      }
    step_name (str): The name of the step, assumed to be in result_at_revision.

  Returns:
    Whether the results are valid based on the 'valid' field.
  """
  # step_name is assumed to be in result_at_revision for valid use of this
  # function.
  if step_name not in result_at_revision:
    return False

  return result_at_revision[step_name]['valid']


def UpdateAnalysisDataPointsWithTryJobResult(analysis, try_job, commit_position,
                                             revision):
  """Updates an analysis with a try job's results.

    The try job's results are assumed to be valid.

  Args:
    analysis (MasterFlakeAnalysis): The main analysis to update.
    try_job (FlakeTryJob): The completed flake try job entity to update the
        analysis's data points with.
    commit_position (int): The commit position of the data point to create.
    revision (str): The git hash of the data point to create.
  """
  if analysis.FindMatchingDataPointWithCommitPosition(commit_position):
    # Data point is already there.
    return

  assert len(try_job.try_job_ids) == len(try_job.flake_results)

  try_job_id = try_job.try_job_ids[-1]
  assert try_job_id

  try_job_data = FlakeTryJobData.Get(try_job_id)
  assert try_job_data

  step_name = analysis.canonical_step_name
  test_name = analysis.test_name
  try_job_result = try_job.flake_results[-1]
  assert try_job_result

  result_at_revision = try_job_result['report']['result'][revision]
  assert IsTryJobResultValid(result_at_revision, step_name)

  pass_fail_counts = result_at_revision[step_name].get('pass_fail_counts', {})
  pass_rate, tries = _GetPassRateAndTries(pass_fail_counts, test_name)

  task_id = GetSwarmingTaskIdForTryJob(
      try_job_result.get('report'), revision, step_name, test_name)

  assert task_id

  data_point = DataPoint.Create(
      commit_position=commit_position,
      git_hash=revision,
      pass_rate=pass_rate,
      try_job_url=try_job_result.get('url'),
      iterations=tries,
      elapsed_seconds=int(
          (try_job_data.end_time - try_job_data.start_time).total_seconds()),
      task_ids=[task_id])

  analysis.data_points.append(data_point)
  analysis.put()
