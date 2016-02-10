# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from datetime import datetime
import time

from google.appengine.ext import ndb

from common.http_client_appengine import HttpClientAppengine as HttpClient
from model import wf_analysis_status
from model.wf_swarming_task import WfSwarmingTask
from pipeline_wrapper import BasePipeline
from waterfall import swarming_util
from waterfall.swarming_task_request import SwarmingTaskRequest


def _GetSwarmingTaskName(ref_task_id):  # pragma: no cover.
  """Returns a unique task name.

  Have this separate function in order to mock for testing purpose.
  """
  return 'findit/deflake/ref_task_id/%s/%s' % (
      ref_task_id, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S %f'))


def _CreateNewSwarmingTaskRequest(
    ref_task_id, ref_request, master_name, builder_name, build_number,
    step_name, tests):
  """Returns a SwarmingTaskRequest instance to run the given tests only."""
  # Make a copy of the referred request and drop or overwrite some fields.
  new_request = copy.deepcopy(ref_request)
  new_request.name = _GetSwarmingTaskName(ref_task_id)
  new_request.parent_task_id = ''
  new_request.user = ''

  # To force a fresh re-run and ignore cached result of any equivalent run.
  new_request.idempotent = False

  # Set the gtest_filter to run the given tests only.
  new_request.extra_args = [
      a for a in new_request.extra_args if not a.startswith('--gtest_filter')
  ]
  new_request.extra_args.append('--gtest_filter=%s' % ':'.join(tests))

  # Remove the env setting for sharding.
  sharding_settings = ['GTEST_SHARD_INDEX', 'GTEST_TOTAL_SHARDS']
  new_request.env = [
      e for e in new_request.env if e['key'] not in sharding_settings
  ]

  # Reset tags for searching and monitoring.
  new_request.tags = []
  new_request.tags.append('purpose:deflake')
  new_request.tags.append('ref_master:%s' % master_name)
  new_request.tags.append('ref_buildername:%s' % builder_name)
  new_request.tags.append('ref_buildnumber:%s' % build_number)
  new_request.tags.append('ref_stepname:%s' % step_name)
  new_request.tags.append('ref_task_id:%s' % ref_task_id)

  return new_request


@ndb.transactional
def _NeedANewSwarmingTask(master_name, builder_name, build_number, step_name):
  swarming_task = WfSwarmingTask.Get(
      master_name, builder_name, build_number, step_name)

  if not swarming_task:
    swarming_task = WfSwarmingTask.Create(
      master_name, builder_name, build_number, step_name)
    swarming_task.status = wf_analysis_status.PENDING
    swarming_task.put()
    return True
  else:
    # TODO(http://crbug.com/585676): Rerun the Swarming task if it runs into
    # unexpected infra errors.
    return False


def _GetSwarmingTaskId(master_name, builder_name, build_number, step_name):
  deadline = time.time() + 5 * 60  # Wait for 5 minutes.
  while time.time() < deadline:
    swarming_task = WfSwarmingTask.Get(
        master_name, builder_name, build_number, step_name)

    if not swarming_task:  # pragma: no cover. Pipeline will retry.
      raise Exception('Swarming task was deleted unexpectedly!!!')

    if swarming_task.task_id:
      return swarming_task.task_id

    time.sleep(10)  # Wait for the existing pipeline to start the Swarming task.

  raise Exception('Time out!')  # pragma: no cover. Pipeline will retry.


class TriggerSwarmingTaskPipeline(BasePipeline):
  """A pipeline to trigger a Swarming task to re-run selected tests of a step.

  This pipeline only supports test steps that run on Swarming and support the
  gtest filter.
  """

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, step_name, tests):
    """Triggers a new Swarming task to run the given tests.

    Args:
      master_name (str): The master name.
      builder_name (str): The builder name.
      build_number (str): The build number.
      step_name (str): The failed test step name.
      tests (list): A list of test cases, eg: ['suite1.test1', 'suite2.test2'].

    Returns:
      task_id (str): The new Swarming task that re-run the given tests.
    """
    # Check if a new Swarming Task is really needed.
    if not _NeedANewSwarmingTask(
        master_name, builder_name, build_number, step_name):
      return _GetSwarmingTaskId(
          master_name, builder_name, build_number, step_name)

    assert tests

    http_client = HttpClient()

    # 0. Retrieve existing Swarming task ids for the given step.
    swarming_task_items = swarming_util.DownloadSwarmingTasksData(
        master_name, builder_name, build_number, http_client, step_name)
    assert len(swarming_task_items) > 0, 'No Swarming task was run.'
    ref_task_id = swarming_task_items[0]['task_id']

    # 1. Retrieve Swarming task parameters from a given Swarming task id.
    ref_request = swarming_util.GetSwarmingTaskRequest(
        ref_task_id, http_client)

    # 2. Update/Overwrite parameters for the re-run.
    new_request = _CreateNewSwarmingTaskRequest(
        ref_task_id, ref_request, master_name, builder_name, build_number,
        step_name, tests)

    # 3. Trigger a new Swarming task to re-run the failed tests.
    task_id = swarming_util.TriggerSwarmingTask(new_request, http_client)

    # Save the task id.
    swarming_task = WfSwarmingTask.Get(
        master_name, builder_name, build_number, step_name)
    swarming_task.task_id = task_id
    swarming_task.put()

    return task_id
