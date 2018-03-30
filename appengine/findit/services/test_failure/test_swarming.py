# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from dto import swarming_task_error
from dto.collect_swarming_task_results_outputs import (
    CollectSwarmingTaskResultsOutputs)
from dto.swarming_task_error import SwarmingTaskError
from infra_api_clients.swarming import swarming_util
from libs import analysis_status
from libs import time_util
from model.wf_swarming_task import WfSwarmingTask
from services import constants
from services import monitoring
from services import swarmed_test_util
from services import swarming
from services import test_results
from services.test_failure import test_failure_analysis
from waterfall import waterfall_config


@ndb.transactional
def NeedANewSwarmingTask(master_name, builder_name, build_number, step_name,
                         force):
  """Checks if a WfSwarmingTask for the given params exists, or creates it."""
  swarming_task = WfSwarmingTask.Get(master_name, builder_name, build_number,
                                     step_name)

  if not swarming_task:
    swarming_task = WfSwarmingTask.Create(master_name, builder_name,
                                          build_number, step_name)
    swarming_task.status = analysis_status.PENDING
    swarming_task.put()
    return True, swarming_task.key.urlsafe()

  if force:
    swarming_task.Reset()
    swarming_task.put()
    return True, swarming_task.key.urlsafe()

  # TODO(http://crbug.com/585676): Rerun the Swarming task if it runs into
  # unexpected infra errors.
  return False, swarming_task.key.urlsafe()


def CreateNewSwarmingTaskRequest(runner_id, ref_task_id, ref_request,
                                 master_name, builder_name, build_number,
                                 step_name, tests, iterations):
  new_request = swarming.CreateNewSwarmingTaskRequestTemplate(
      runner_id,
      ref_task_id,
      ref_request,
      master_name,
      builder_name,
      step_name,
      tests,
      iterations,
      use_new_pubsub=True)

  # Add additional tags.
  new_request.tags.append('ref_task_id:%s' % ref_task_id)
  new_request.tags.append('purpose:identify-flake')
  new_request.tags.append('ref_buildnumber:%s' % build_number)
  return new_request


def TriggerSwarmingTask(run_swarming_task_parameters, runner_id):
  """Triggers a swarming rerun for the given tests in a given build."""

  master_name, builder_name, build_number = (
      run_swarming_task_parameters.build_key.GetParts())
  step_name = run_swarming_task_parameters.step_name
  tests = run_swarming_task_parameters.tests

  assert tests, 'No tests to trigger swarming task for.'
  http_client = FinditHttpClient()

  # 1. Retrieve Swarming task parameters from a given Swarming task id.
  ref_task_id, ref_request = swarming.GetReferredSwarmingTaskRequestInfo(
      master_name, builder_name, build_number, step_name, http_client)

  # 2. Update/Overwrite parameters for the re-run.
  iterations_to_rerun = waterfall_config.GetSwarmingSettings().get(
      'iterations_to_rerun')
  new_request = CreateNewSwarmingTaskRequest(
      runner_id, ref_task_id, ref_request, master_name, builder_name,
      build_number, step_name, tests, iterations_to_rerun)

  # 3. Trigger a new Swarming task to re-run the failed tests.
  task_id, _ = swarming_util.TriggerSwarmingTask(swarming.SwarmingHost(),
                                                 new_request, http_client)

  if task_id:  # pragma: no branch.
    # 4. Update swarming task.
    OnSwarmingTaskTriggered(master_name, builder_name, build_number, step_name,
                            tests, task_id, iterations_to_rerun, new_request)

  return task_id


@ndb.transactional
def _UpdateSwarmingTaskEntity(master_name,
                              builder_name,
                              build_number,
                              step_name,
                              status=None,
                              task_id=None,
                              error=None,
                              tests_statuses=None,
                              parameters=None,
                              canonical_step_name=None,
                              created_ts=None,
                              started_ts=None,
                              completed_ts=None):
  task = WfSwarmingTask.Get(master_name, builder_name, build_number, step_name)
  assert task
  task.status = status or task.status
  task.task_id = task_id or task.task_id
  task.error = error.ToSerializable() if error else task.error
  task.tests_statuses = tests_statuses or task.tests_statuses
  task.parameters = task.parameters or {}
  task.parameters.update(parameters or {})
  task.canonical_step_name = canonical_step_name or task.canonical_step_name
  task.created_time = task.created_time or time_util.DatetimeFromString(
      created_ts)
  task.started_time = task.started_time or time_util.DatetimeFromString(
      started_ts)
  task.completed_time = task.completed_time or time_util.DatetimeFromString(
      completed_ts)
  task.put()


def OnSwarmingTaskTriggered(master_name, builder_name, build_number, step_name,
                            tests, task_id, iterations_to_rerun, new_request):
  canonical_step_name = swarming_util.GetTagValue(new_request.tags, 'ref_name')
  parameters = {
      'tests': tests,
      'iterations_to_rerun': iterations_to_rerun,
      'ref_name': canonical_step_name,
      'priority': new_request.priority
  }
  _UpdateSwarmingTaskEntity(
      master_name,
      builder_name,
      build_number,
      step_name,
      task_id=task_id,
      parameters=parameters,
      canonical_step_name=canonical_step_name)
  monitoring.OnSwarmingTaskStatusChange('trigger', 'identify-flake')


def OnSwarmingTaskTimeout(run_swarming_task_params, task_id):
  master_name, builder_name, build_number = (
      run_swarming_task_params.build_key.GetParts())
  step_name = run_swarming_task_params.step_name

  error = SwarmingTaskError.GenerateError(swarming_task_error.RUNNER_TIMEOUT)

  data, output_json, _ = swarmed_test_util.GetSwarmingTaskDataAndResult(task_id)
  if output_json and test_results.IsTestResultsValid(output_json):
    tests_statuses = test_results.GetTestsRunStatuses(output_json)
    _UpdateSwarmingTaskEntity(
        master_name,
        builder_name,
        build_number,
        step_name,
        status=analysis_status.COMPLETED,
        error=error,
        tests_statuses=tests_statuses,
        created_ts=data.get('created_ts'),
        started_ts=data.get('started_ts'),
        completed_ts=data.get('completed_ts'))
  else:
    _UpdateSwarmingTaskEntity(
        master_name,
        builder_name,
        build_number,
        step_name,
        status=analysis_status.ERROR,
        error=error)


def OnSwarmingTaskError(master_name,
                        builder_name,
                        build_number,
                        step_name,
                        error,
                        should_complete_pipeline=True):
  logging.error('Error %s when processing a swarming task %s/%s/%d/%s',
                error.message, master_name, builder_name, build_number,
                step_name)

  if should_complete_pipeline:
    _UpdateSwarmingTaskEntity(
        master_name,
        builder_name,
        build_number,
        step_name,
        status=analysis_status.ERROR,
        error=error)
    return False
  else:
    _UpdateSwarmingTaskEntity(
        master_name, builder_name, build_number, step_name, error=error)
    return


def OnSwarmingTaskCompleted(master_name, builder_name, build_number, step_name,
                            data, output_json):
  tests_statuses = test_results.GetTestsRunStatuses(output_json)
  _UpdateSwarmingTaskEntity(
      master_name,
      builder_name,
      build_number,
      step_name,
      status=analysis_status.COMPLETED,
      tests_statuses=tests_statuses,
      created_ts=data.get('created_ts'),
      started_ts=data.get('started_ts'),
      completed_ts=data.get('completed_ts'))
  return True


def OnSwarmingTaskStateChanged(run_swarming_task_parameters, task_id):
  master_name, builder_name, build_number = (
      run_swarming_task_parameters.build_key.GetParts())
  step_name = run_swarming_task_parameters.step_name

  data, output_json, error = (
      swarmed_test_util.GetSwarmingTaskDataAndResult(task_id))

  if not data or not data.get('state'):
    # Error when get task state.
    OnSwarmingTaskError(master_name, builder_name, build_number, step_name,
                        error, False)
    return None

  task_state = data['state']
  if (task_state == constants.STATE_COMPLETED and output_json and
      test_results.IsTestResultsValid(output_json)):
    return OnSwarmingTaskCompleted(master_name, builder_name, build_number,
                                   step_name, data, output_json)
  elif task_state in constants.STATE_NOT_STOP:
    if task_state == constants.STATE_RUNNING:  # pragma: no branch
      _UpdateSwarmingTaskEntity(
          master_name,
          builder_name,
          build_number,
          step_name,
          status=analysis_status.RUNNING)
    return None
  else:
    # Swarming task finished with error.
    return OnSwarmingTaskError(master_name, builder_name, build_number,
                               step_name, error)


def GetStepsToCollectSwarmingTaskResults(collect_consistent_failure_inputs):
  """Gets steps that Findit needs to wait swarming tasks to complete and collect
    results for.

  Args:
    collect_consistent_failure_inputs (CollectSwarmingTaskResultsInputs): Key to
    a build and if the build has completed.

  Returns:
    steps (list): A list of step names that Findit needs to wait swarming tasks
      to complete and collect results for. It will be empty if build has not
      completed yet or there's no first time failures in the build.
  """
  build_completed = collect_consistent_failure_inputs.build_completed
  if not build_completed:
    # Build has not completed, bail out.
    return []

  master_name, builder_name, build_number = (
      collect_consistent_failure_inputs.build_key.GetParts())
  return test_failure_analysis.GetFirstTimeFailedSteps(
      master_name, builder_name, build_number)


def GetConsistentFailuresWhenAllTasksComplete(collect_consistent_failure_inputs,
                                              first_failed_steps):
  """Get consistent failures from swarming reruns in a build when all of them
    complete.

  This functions tries to collect swarming task results if all tasks complete.
  Otherwise it will give up what it has collected and return None.

  Args:
    collect_consistent_failure_inputs (CollectSwarmingTaskResultsInputs): Key to
      a build and if the build has completed.
    first_failed_steps (list): A list of step_names that Findit needs to wait
      swarming tasks to complete and collect results for.

  Returns:
    (CollectSwarmingTaskResultsOutputs): Consistently failed tests.
      - It will be None if any task is still running.
      - It will be empty if
        - build has not completed,
        - no first time failure in build,
        - no consistent test failures in build.
  """

  master_name, builder_name, build_number = (
      collect_consistent_failure_inputs.build_key.GetParts())
  consistent_failures = {}

  for step_name in first_failed_steps:
    task = WfSwarmingTask.Get(master_name, builder_name, build_number,
                              step_name)
    assert task, 'Cannot get WfSwarmingTask entity %s/%s/%d/%s.' % (
        master_name, builder_name, build_number, step_name)
    if task.status in [analysis_status.PENDING, analysis_status.RUNNING]:
      # Task doesn't complete, don't return any information about consistent
      # failures.
      return None

    if task.status == analysis_status.ERROR:
      logging.warning('Swarming task %s/%s/%s/%s completed with error %s.' %
                      (master_name, builder_name, build_number, step_name,
                       (task.error or {}).get('message', 'Unknown error.')))
      continue

    if not task.classified_tests:  # Task completed without results.
      logging.warning('No result for swarming task %s/%s/%s/%s' %
                      (master_name, builder_name, build_number, step_name))
      continue

    if not task.reliable_tests:  # No consistent test failures.
      continue

    consistent_failures[task.canonical_step_name or
                        step_name] = task.reliable_tests

  return (CollectSwarmingTaskResultsOutputs.FromSerializable({
      'consistent_failures': consistent_failures
  }) if consistent_failures else
          CollectSwarmingTaskResultsOutputs.FromSerializable({}))


def GetFirstTimeTestFailuresToRunSwarmingTasks(run_swarming_tasks_input):
  """Gets all first time failed steps and tests in build to run swarming tasks.
  """
  master_name, builder_name, build_number = (
      run_swarming_tasks_input.build_key.GetParts())
  failure_info = run_swarming_tasks_input.heuristic_result.failure_info
  force = run_swarming_tasks_input.force

  if (not failure_info or not failure_info.failed_steps or
      not failure_info.failure_type == failure_type.TEST):
    return {}

  # Gets all the first time failures in the build.
  test_first_failures = test_failure_analysis.GetsFirstFailureAtTestLevel(
      master_name, builder_name, build_number, failure_info, force)

  # Gets the first time failures that have not run swarming tasks.
  new_test_first_failures = {}
  for step_name, tests in test_first_failures.iteritems():
    if NeedANewSwarmingTask(master_name, builder_name, build_number, step_name,
                            force):
      new_test_first_failures[step_name] = tests
  return new_test_first_failures
