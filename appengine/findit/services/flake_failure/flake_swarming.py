# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions for operating on swarming reruns for flaky tests.
"""

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from dto import swarming_task_error
from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from dto.swarming_task_error import SwarmingTaskError
from infra_api_clients.swarming import swarming_util
from libs import time_util
from services import constants
from services import monitoring
from services import swarmed_test_util
from services import swarming
from services.flake_failure import flake_test_results

_FINDIT_HTTP_CLIENT = FinditHttpClient()


def _ParseFlakeSwarmingTaskOutput(task_data, output_json, error, parameters):
  """Returns swarming task results as a FlakeswarmingTaskOutput object."""
  assert task_data

  iterations = parameters.iterations

  if output_json:
    # Gets the total numbers of runs and number of successful runs from
    # test results
    tries, successes = flake_test_results.GetCountsFromSwarmingRerun(
        output_json)

    if tries is None or successes is None:
      # Something went wrong preventing even a single test from being processed
      # which counts as an error.
      error = error or SwarmingTaskError.GenerateError(
          code=swarming_task_error.UNKNOWN)
      tries = None
      successes = None
    elif (tries == 1 and task_data['state'] == constants.STATE_COMPLETED and
          not task_data.get('failure') and not task_data.get('infra_failure')):
      # webkit_layout_tests special case: test results will be combined into
      # one if all results are the same.
      # Use iterations instead assuming the test repeated that many times.
      # Currently only do this if task completes successfully.
      tries = iterations
      successes = iterations * successes

    return FlakeSwarmingTaskOutput(
        completed_time=time_util.DatetimeFromString(
            task_data.get('completed_ts')),
        error=error,
        iterations=tries,
        pass_count=successes,
        started_time=time_util.DatetimeFromString(task_data.get('started_ts')),
        task_id=task_data['task_id'])
  else:
    return FlakeSwarmingTaskOutput(
        completed_time=time_util.DatetimeFromString(
            task_data.get('completed_ts')),
        error=error or
        SwarmingTaskError.GenerateError(code=swarming_task_error.UNKNOWN),
        iterations=None,
        pass_count=None,
        started_time=time_util.DatetimeFromString(task_data.get('started_ts')),
        task_id=task_data['task_id'])


def OnSwarmingTaskTimeout(parameters, task_id):
  """To be called when waiting for a swarming task times out."""
  timeout_error = SwarmingTaskError.GenerateError(
      swarming_task_error.RUNNER_TIMEOUT)

  if not task_id:
    # The pipeline timedout without successfully triggering a task.
    return OnSwarmingTaskError(None, timeout_error)

  task_data, output_json, error = (
      swarmed_test_util.GetSwarmingTaskDataAndResult(task_id))

  if not task_data or not task_data.get('state'):
    return OnSwarmingTaskError(task_id, error or timeout_error)

  # Attempt to salvage whatever is available, but still report an error.
  return _ParseFlakeSwarmingTaskOutput(task_data, output_json, error or
                                       timeout_error, parameters)


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


def OnSwarmingTaskStateChanged(parameters, task_id):
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
  return _ParseFlakeSwarmingTaskOutput(task_data, output_json, error,
                                       parameters)


def CreateNewSwarmingTaskRequest(
    runner_id, ref_task_id, ref_request, master_name, builder_name, step_name,
    test_name, isolate_sha, iterations, timeout_seconds):
  """Creates a SwarmingTaskRequest to trigger against specified parameters."""
  # Create swarming task request template.
  new_request = swarming.CreateNewSwarmingTaskRequestTemplate(
      runner_id, ref_task_id, ref_request, master_name, builder_name, step_name,
      [test_name], iterations)

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
