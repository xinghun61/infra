# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from gae_libs.pipeline_wrapper import BasePipeline
from libs import analysis_status
from model.flake.master_flake_analysis import DataPoint
from waterfall import swarming_util


def _GetSwarmingTaskIdForTryJob(report, revision, step_name, test_name):
  """Check json output for each task and return id of the one with test result.
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


def _IsResultValid(result_at_revision, step_name):
  """Checks if the try job result is valid.

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
  assert step_name in result_at_revision
  return result_at_revision[step_name]['valid']


class ProcessFlakeTryJobResultPipeline(BasePipeline):
  """A pipeline for processing a flake try job result."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, revision, commit_position, try_job_result, urlsafe_try_job_key,
          urlsafe_flake_analysis_key):
    """Extracts pass rate information and updates flake analysis.

    Args:
      revision (str): The git hash the try job was run against.
      commit_position (int): The commit position corresponding to |revision|.
      try_job_result (dict): The result dict reported by buildbucket.
          Example:
          {
              'metadata': {},
              'result': {
                  'cafed52c5f3313646b8e04e05601b5cb98f305b3': {
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
              }
          }
      urlsafe_try_job_key (str): The urlsafe key to the corresponding try job
          entity.
      urlsafe_flake_analysis_key (str): The urlsafe key for the master flake
          analysis entity to be updated.
    """
    flake_analysis = ndb.Key(urlsafe=urlsafe_flake_analysis_key).get()
    try_job = ndb.Key(urlsafe=urlsafe_try_job_key).get()
    assert flake_analysis
    assert try_job

    try_job.status = analysis_status.COMPLETED
    try_job.put()

    step_name = flake_analysis.canonical_step_name
    test_name = flake_analysis.test_name
    result = try_job_result['report']['result'][revision]

    if isinstance(result, basestring):
      # Result is a string 'infra failed'. Try job failed.
      return

    if not _IsResultValid(result, step_name):
      try_job.error = {
          'message': 'Try job results are not valid',
          'reason': 'Try job results are not vaild',
      }
      try_job.put()
      return

    pass_fail_counts = result[step_name].get('pass_fail_counts', {})

    if pass_fail_counts:
      test_results = pass_fail_counts[test_name]
      pass_count = test_results['pass_count']
      fail_count = test_results['fail_count']
      tries = pass_count + fail_count
      pass_rate = float(pass_count) / tries
    else:  # Test does not exist.
      pass_rate = -1
      tries = 0

    data_point = DataPoint()
    data_point.commit_position = commit_position
    data_point.git_hash = revision
    data_point.pass_rate = pass_rate
    data_point.try_job_url = try_job.flake_results[-1].get('url')
    data_point.iterations = tries
    data_point.task_id = _GetSwarmingTaskIdForTryJob(
        try_job.flake_results[-1].get('report'), revision, step_name, test_name)
    flake_analysis.data_points.append(data_point)
    flake_analysis.put()
