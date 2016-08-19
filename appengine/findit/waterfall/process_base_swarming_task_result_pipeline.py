# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import datetime
import logging
import time

from common.http_client_appengine import HttpClientAppengine as HttpClient
from common.pipeline_wrapper import BasePipeline
from model import analysis_status
from waterfall import swarming_util
from waterfall import waterfall_config


class ProcessBaseSwarmingTaskResultPipeline(BasePipeline):
  """A pipeline for monitoring swarming task and processing task result.

  This pipeline waits for result for a swarming task and processes the result to
  generate a dict for statuses for each test run.
  """

  HTTP_CLIENT = HttpClient()

  def _CheckTestsRunStatuses(self, output_json):
    # Checks result status for each test run and saves the numbers accordingly.
    # Should be overridden by subclass.
    raise NotImplementedError(
        '_CheckTestsRunStatuses should be implemented in the child class')

  def _ConvertDateTime(self, time_string):
    """Convert UTC time string to datetime.datetime."""
    # Match the time conversion with swarming.py which elides the suffix
    # when microseconds are 0.
    if not time_string:
      return None
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
      try:
        return datetime.datetime.strptime(time_string, fmt)
      except ValueError:
        pass
    raise ValueError('Failed to parse %s' % time_string)  # pragma: no cover

  def _GetSwarmingTask(self):
    # Get the appropriate kind of Swarming Task (Wf or Flake).
    # Should be overwritten by subclass.
    raise NotImplementedError(
        '_GetSwarmingTask should be implemented in the child class')

  def _GetArgs(self):
    # Return list of arguments to call _CheckTestsRunStatuses with - output_json
    # Should be overwritten by subclass.
    raise NotImplementedError(
        '_GetArgs should be implemented in the child class')

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number,
          step_name, task_id, *args): # pragma: no cover.
    """
    Args:
      master_name (str): The master name.
      builder_name (str): The builder name.
      build_number (str): The build number.
      step_name (str): The failed test step name.
      task_id (str): Id for the swarming task which is triggered by Findit.

    Returns:
      A dict of lists for reliable/flaky tests.
    """
    call_args = self._GetArgs(master_name, builder_name, build_number,
                              step_name, *args)
    assert task_id
    timeout_hours = waterfall_config.GetSwarmingSettings().get(
        'task_timeout_hours')
    deadline = time.time() + timeout_hours * 60 * 60
    server_query_interval_seconds = waterfall_config.GetSwarmingSettings().get(
        'server_query_interval_seconds')
    task_started = False
    task_completed = False
    tests_statuses = {}
    step_name_no_platform = None

    while not task_completed:
      # Keeps monitoring the swarming task, waits for it to complete.
      data = swarming_util.GetSwarmingTaskResultById(
          task_id, self.HTTP_CLIENT)
      task_state = data['state']
      step_name_no_platform = swarming_util.GetTagValue(
          data.get('tags', {}), 'ref_name')
      if task_state not in swarming_util.STATES_RUNNING:
        task_completed = True
        task = self._GetSwarmingTask(*call_args)
        if task_state == swarming_util.STATE_COMPLETED:
          outputs_ref = data.get('outputs_ref')
          output_json = swarming_util.GetSwarmingTaskFailureLog(
              outputs_ref, self.HTTP_CLIENT)
          tests_statuses = self._CheckTestsRunStatuses(
              output_json, *call_args)
          task.status = analysis_status.COMPLETED
          task.tests_statuses = tests_statuses
        else:
          task.status = analysis_status.ERROR
          logging.error('Swarming task stopped with status: %s' % (
              task_state))
        priority_str = swarming_util.GetTagValue(
            data.get('tags', {}), 'priority')
        if priority_str:
          task.parameters['priority'] = int(priority_str)
        task.put()
      else:  # pragma: no cover
        if task_state == 'RUNNING' and not task_started:
          # swarming task just starts, update status.
          task_started = True
          task = self._GetSwarmingTask(*call_args)
          task.status = analysis_status.RUNNING
          task.put()
        time.sleep(server_query_interval_seconds)
      if time.time() > deadline:
        # Updates status as ERROR.
        task = self._GetSwarmingTask(*call_args)
        task.status = analysis_status.ERROR
        task.put()
        logging.error('Swarming task timed out after %d hours.' % timeout_hours)
        break  # Stops the loop and return.
    # Update swarming task metadate.
    task = self._GetSwarmingTask(*call_args)
    task.created_time = self._ConvertDateTime(data.get('created_ts'))
    task.started_time = self._ConvertDateTime(data.get('started_ts'))
    task.completed_time = self._ConvertDateTime(data.get('completed_ts'))
    task.put()

    return step_name, step_name_no_platform
