# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from infra_api_clients.swarming import swarming_util
from libs import analysis_status
from model.wf_swarming_task import WfSwarmingTask
from services import monitoring
from services import swarmed_test_util
from services import swarming
from waterfall import waterfall_config


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
def OnSwarmingTaskTriggered(master_name, builder_name, build_number, step_name,
                            tests, task_id, iterations_to_rerun, new_request):
  swarming_task = WfSwarmingTask.Get(
      master_name, builder_name, build_number, step_name)
  assert swarming_task
  swarming_task.task_id = task_id
  swarming_task.parameters['tests'] = tests
  swarming_task.parameters['iterations_to_rerun'] = iterations_to_rerun
  swarming_task.parameters['ref_name'] = swarming_util.GetTagValue(
      new_request.tags, 'ref_name')
  swarming_task.parameters['priority'] = new_request.priority
  swarming_task.put()
  monitoring.OnSwarmingTaskStatusChange('trigger', 'identify-flake')
