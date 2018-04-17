# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions for operating on test results from swarming."""

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from dto import swarming_task_error
from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from dto.swarming_task_error import SwarmingTaskError
from infra_api_clients.swarming import swarming_util
from libs import time_util
from libs.test_results import test_results_util
from services import constants
from services import monitoring
from services import swarmed_test_util
from services import swarming

_FINDIT_HTTP_CLIENT = FinditHttpClient()


def _GetPassFailForTestStatuses(test_statuses):
  """Gets the total number of passes and fails for the given tests.

  PRE_ test runs count for the fails only whereas regular test runs count for
  both pass and fail.

  Args:
    test_statuses (dict): Mapping of test_name to total_run, SUCCESS. This
      Dict should only contain one test and it's PRE_ test. Ex:
      {
        '...PRE_test': {'total_run': 100, 'SUCCESS': 100},
        '...test': {'total_run: 100, 'SUCCESS': 50}
      }

  Returns:
    (int, int) Pass, fail counts.
  """
  # Note that the arguements should only contain information about one test.
  p = 0
  f = 0

  for test_name, iteration_info in test_statuses.iteritems():
    total_runs = iteration_info.get('total_run', 0)
    passes = iteration_info.get('SUCCESS', 0)
    assert total_runs >= passes

    # For PRE_ runs, only count the failures.
    if 'PRE_' in test_name:
      f += total_runs - passes
    else:
      p += passes
      f += total_runs - passes

  return p, f


def _ParseFlakeSwarmingTaskOutput(task_data, output_json, error):
  """Returns swarming task results as a FlakeswarmingTaskOutput object."""
  assert task_data

  if output_json:
    # Use whatever's available in output_json.
    test_statuses = test_results_util.GetTestResultObject(
        output_json).GetTestsRunStatuses()
    test_name = next(
        (test for test in test_statuses.keys() if 'PRE_' not in test), None)

    # Get the pass/fail numbers from test results
    passes, fails = _GetPassFailForTestStatuses(test_statuses)
    tries = passes + fails
    successes = passes

    if tries == 0 and test_name is not None and test_results_util.GetTestResultObject(
        output_json).DoesTestExist(test_name):
      # The test exists, but something went wrong prevnting even a single test
      # from being processed which counts as an error.
      error = error or SwarmingTaskError.GenerateError(
          code=swarming_task_error.UNKNOWN)
      tries = None
      successes = None

    return FlakeSwarmingTaskOutput(
        completed_time=time_util.DatetimeFromString(task_data['completed_ts']),
        error=error,
        iterations=tries,
        pass_count=successes,
        started_time=time_util.DatetimeFromString(task_data['started_ts']),
        task_id=task_data['task_id'])
  else:
    return FlakeSwarmingTaskOutput(
        completed_time=time_util.DatetimeFromString(task_data['completed_ts']),
        error=error or
        SwarmingTaskError.GenerateError(code=swarming_task_error.UNKNOWN),
        iterations=None,
        pass_count=None,
        started_time=time_util.DatetimeFromString(task_data['started_ts']),
        task_id=task_data['task_id'])


def OnSwarmingTaskTimeout(task_id):
  """To be called when waiting for a swarming task times out."""
  timeout_error = SwarmingTaskError.GenerateError(
      swarming_task_error.RUNNER_TIMEOUT)
  task_data, output_json, error = (
      swarmed_test_util.GetSwarmingTaskDataAndResult(task_id))

  if not task_data:
    return OnSwarmingTaskError(task_id, error or timeout_error)

  # Attempt to salvage whatever is available, but still report an error.
  return _ParseFlakeSwarmingTaskOutput(task_data, output_json, error or
                                       timeout_error)


def OnSwarmingTaskError(task_id, error):
  """Returns a FlakeSwarmingTaskOutput object representing a failed task."""
  return FlakeSwarmingTaskOutput(
      completed_time=None,
      error=error or
      SwarmingTaskError.GenerateError(code=swarming_task_error.UNKNOWN),
      iterations=None,
      pass_count=None,
      started_time=None,
      task_id=task_id)


def OnSwarmingTaskStateChanged(task_id):
  """To be called when a swarming task's status changes."""
  task_data, output_json, error = (
      swarmed_test_util.GetSwarmingTaskDataAndResult(task_id))

  if not task_data or not task_data.get('state'):
    # Something went wrong trying to get task data or state.
    return OnSwarmingTaskError(task_id, error)

  if task_data['state'] in constants.STATE_NOT_STOP:
    # The task is in progress. No results to return yet.
    return None

  # The task is completed e.g. task_state == constants.STATE_COMPLETED. Even
  # if there is an error, attempt to salvage any usable information, but
  # still report the error.
  return _ParseFlakeSwarmingTaskOutput(task_data, output_json, error)


def CreateNewSwarmingTaskRequest(
    runner_id, ref_task_id, ref_request, master_name, builder_name, step_name,
    test_name, isolate_sha, iterations, timeout_seconds):
  """Creates a SwarmingTaskRequest to trigger against specified parameters."""
  # Create swarming task request template.
  new_request = swarming.CreateNewSwarmingTaskRequestTemplate(
      runner_id,
      ref_task_id,
      ref_request,
      master_name,
      builder_name,
      step_name, [test_name],
      iterations,
      use_new_pubsub=True)

  # Point the inputs to the specified binaries.
  new_request.properties.inputs_ref.isolated = isolate_sha

  # Specify the amount of time the task is expected to complete in.
  new_request.properties.execution_timeout_secs = str(timeout_seconds)

  # Add additional tags.
  new_request.tags.append('purpose:identify-regression-range')

  return new_request


def TriggerSwarmingTask(analysis_urlsafe_key, isolate_sha, iterations,
                        timeout_seconds, runner_id):
  """Triggers a flake swarming rerun of a test against a given isolate sha."""
  analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
  assert analysis

  master_name = analysis.master_name
  builder_name = analysis.builder_name
  reference_build_number = analysis.build_number
  step_name = analysis.step_name
  test_name = analysis.test_name

  # 1. Retrieve the reference swarming task with matching configuration of the
  # build that flakiness was first identified in.
  ref_task_id, ref_request = swarming.GetReferredSwarmingTaskRequestInfo(
      master_name, builder_name, reference_build_number, step_name,
      _FINDIT_HTTP_CLIENT)

  # 2. Create a swarming task request from the reference request with desired
  # fields updated.
  new_request = CreateNewSwarmingTaskRequest(
      runner_id, ref_task_id, ref_request, master_name, builder_name, step_name,
      test_name, isolate_sha, iterations, timeout_seconds)

  # 3. Trigger a new swarming task.
  task_id, _ = swarming_util.TriggerSwarmingTask(
      swarming.SwarmingHost(), new_request, _FINDIT_HTTP_CLIENT)

  # Monitoring.
  monitoring.OnSwarmingTaskStatusChange('trigger', 'identify-regression-range')

  return task_id
