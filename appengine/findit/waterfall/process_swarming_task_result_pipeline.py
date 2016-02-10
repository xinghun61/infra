# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import time

from common.http_client_appengine import HttpClientAppengine as HttpClient
from model import wf_analysis_status
from model.wf_swarming_task import WfSwarmingTask
from pipeline_wrapper import BasePipeline
from pipeline_wrapper import pipeline
from waterfall import swarming_util


def _CheckTestsRunStatuses(output_json):
  """Checks result status for each test run and saves the numbers accordingly.

  Args:
    output_json (dict): A dict of all test results in the swarming task.

  Returns:
    tests_statuses (dict): A dict of different statuses for each test.

  Currently for each test, we are saving number of total runs,
  number of succeeded runs and number of failed runs.
  """
  tests_statuses = collections.defaultdict(lambda: collections.defaultdict(int))
  if output_json:
    for iteration in output_json.get('per_iteration_data'):
      for test_name, tests in iteration.iteritems():
        tests_statuses[test_name]['total_run'] += len(tests)
        for test in tests:
          tests_statuses[test_name][test['status']] += 1

  return tests_statuses


class ProcessSwarmingTaskResultPipeline(BasePipeline):
  """A pipeline for monitoring swarming task and processing task result.

  This pipeline waits for result for a swarming task and processes the result to
  generate a dict for statuses for each test run.
  """

  HTTP_CLIENT = HttpClient()
  # TODO(chanli): move these settings to findit config.
  SWARMING_QUERY_INTERVAL_SECONDS = 60
  TIMEOUT_HOURS = 23

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, step_name, task_id):
    """
    Args:
      master_name (str): The master name.
      builder_name (str): The builder name.
      build_number (str): The build number.
      step_name (str): The failed test step name.
      task_id (str): Id for the swarming task which is triggered by Findit.

    Returns:
      A dict of different statuses for each test.
    """

    assert task_id

    deadline = time.time() + self.TIMEOUT_HOURS * 60 * 60
    task_started = False
    task_completed = False
    tests_statuses = {}

    while not task_completed:
      # Keeps monitoring the swarming task, waits for it to complete.
      task_state, outputs_ref = swarming_util.GetSwarmingTaskResultById(
          task_id, self.HTTP_CLIENT)
      if task_state not in swarming_util.STATES_RUNNING:
        task_completed = True
        task = WfSwarmingTask.Get(
            master_name, builder_name, build_number, step_name)
        if task_state == swarming_util.STATE_COMPLETED:
          output_json = swarming_util.GetSwarmingTaskFailureLog(
              outputs_ref, self.HTTP_CLIENT)
          tests_statuses = _CheckTestsRunStatuses(output_json)

          task.status = wf_analysis_status.ANALYZED
          task.tests_statuses = tests_statuses
        else:
          task.status = wf_analysis_status.ERROR
          logging.error('Swarming task stopped with status: %s' % (
              task_state))
        task.put()
      else:  # pragma: no cover
        if task_state == 'RUNNING' and not task_started:
          # swarming task just starts, update status.
          task_started = True
          task = WfSwarmingTask.Get(
              master_name, builder_name, build_number, step_name)
          task.status = wf_analysis_status.ANALYZING
          task.put()

        time.sleep(self.SWARMING_QUERY_INTERVAL_SECONDS)

      if time.time() > deadline:  # pragma: no cover
        # Explicitly abort the whole pipeline.
        raise pipeline.Abort('Swarming pipeline timed out after %d hours.' % (
            self.TIMEOUT_HOURS))

    return tests_statuses
