# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common import exceptions
from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from libs import time_util
from libs.test_results import test_results_util
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.flake.master_flake_analysis import DataPoint
from services import swarmed_test_util
from services import try_job as try_job_service
from waterfall import waterfall_config
from waterfall.flake import flake_constants

_DEFAULT_ITERATIONS_TO_RERUN = 100


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
    test_pass_fail_counts = pass_fail_counts[test_name]
    pass_count = test_pass_fail_counts['pass_count']
    fail_count = test_pass_fail_counts['fail_count']
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
    output_json = swarmed_test_util.GetTestResultForSwarmingTask(
        task_id, http_client)
    test_results = test_results_util.GetTestResultObject(output_json)
    if output_json and test_results and test_results.IsTestResultUseful():
      return task_id

  return None


def IsTryJobResultAtRevisionValid(result, revision):
  """Determines whether a try job's results are sufficient to be used.

  Args:
    result (dict): A dict expected to be in the format
        {
            'report': {
                'result': {
                    'revision': (dict)
                }
            }
        }
    revision (str): The revision to ensure is in the result dict.
  """
  return result and revision in result.get('report', {}).get('result', {})


def IsTryJobResultAtRevisionValidForStep(result_at_revision, step_name):
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
  if not result_at_revision or step_name not in result_at_revision:
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
  assert IsTryJobResultAtRevisionValidForStep(result_at_revision, step_name)

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


def GetBuildProperties(master_name,
                       builder_name,
                       canonical_step_name,
                       test_name,
                       git_hash,
                       iterations_to_rerun,
                       skip_tests=False):
  # TODO(crbug.com/786518): Remove iterations_to_rerun and skip_tests.
  iterations = iterations_to_rerun or _DEFAULT_ITERATIONS_TO_RERUN

  return {
      'recipe': 'findit/chromium/flake',
      'skip_tests': skip_tests,
      'target_mastername': master_name,
      'target_testername': builder_name,
      'test_revision': git_hash,
      'test_repeat_count': iterations,
      'tests': {
          canonical_step_name: [test_name]
      },
  }


@ndb.transactional
def CreateTryJobData(build_id, try_job_key, urlsafe_analysis_key, runner_id):
  """Creates a FlakeTryJobData entity.

  Args:
    build_id (str): The try job id that is to be used as the key to this entity.
    try_job_key (str): The urlsafe key to the FlakeTryJob entity corresponding
        to this FlakeTryJobData entity.
    urlsafe_analysis_key (str): The key to the flake analysis requesting the
        try job.
    runner_id (str): The id of the pipeline that handles the callback of this
        try job's completion.
  """
  try_job_data = FlakeTryJobData.Create(build_id)
  try_job_data.created_time = time_util.GetUTCNow()
  try_job_data.try_job_key = try_job_key
  try_job_data.analysis_key = ndb.Key(urlsafe=urlsafe_analysis_key)
  try_job_data.runner_id = runner_id
  try_job_data.put()


def UpdateTryJob(master_name, builder_name, canonical_step_name, test_name,
                 git_hash, build_id):
  try_job = (
      FlakeTryJob.Get(master_name, builder_name, canonical_step_name, test_name,
                      git_hash) or
      FlakeTryJob.Create(master_name, builder_name, canonical_step_name,
                         test_name, git_hash))
  try_job.flake_results.append({'try_job_id': build_id})
  try_job.try_job_ids.append(build_id)
  try_job.put()
  return try_job


@ndb.transactional
def GetTryJob(master_name, builder_name, step_name, test_name, revision):
  """Ensures a FlakeTryJob exists for the configuration and returns it."""
  # TODO(crbug.com/796431): Replace FlakeTryJob with a new try job entity
  # independent of test_name.
  try_job = FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                            revision)
  if not try_job:
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

  return try_job


def ScheduleFlakeTryJob(parameters, runner_id):
  """Schedules a flake try job to compile and isolate."""
  analysis = ndb.Key(urlsafe=parameters.analysis_urlsafe_key).get()
  assert analysis

  master_name = analysis.master_name
  builder_name = analysis.builder_name
  step_name = analysis.canonical_step_name
  test_name = analysis.test_name

  # TODO(crbug.com/786518): Remove iterations_to_rerun and skip_tests.
  properties = GetBuildProperties(
      master_name,
      builder_name,
      step_name,
      test_name,
      parameters.revision,
      0,
      skip_tests=True)

  tryserver_mastername, tryserver_buildername = (
      waterfall_config.GetFlakeTrybot(master_name, builder_name))

  build_id, error = try_job_service.TriggerTryJob(
      master_name, builder_name, tryserver_mastername, tryserver_buildername,
      properties, {},
      failure_type.GetDescriptionForFailureType(
          failure_type.FLAKY_TEST), parameters.flake_cache_name,
      parameters.dimensions.ToSerializable(), runner_id)

  if error:
    raise exceptions.RetryException(error.message, error.reason)

  try_job = UpdateTryJob(master_name, builder_name, step_name, test_name,
                         parameters.revision, build_id)

  # Create a corresponding FlakeTryJobData entity to capture as much metadata as
  # early as possible.
  CreateTryJobData(build_id, try_job.key, parameters.analysis_urlsafe_key,
                   runner_id)

  return build_id
