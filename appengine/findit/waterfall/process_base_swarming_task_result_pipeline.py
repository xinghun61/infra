# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import datetime
import json
import logging
import time

from google.appengine.api import taskqueue

from common import constants
from common.findit_http_client import FinditHttpClient
from gae_libs import appengine_util
from gae_libs.pipeline_wrapper import BasePipeline
from libs import analysis_status
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.trigger_base_swarming_task_pipeline import NO_TASK
from waterfall.trigger_base_swarming_task_pipeline import NO_TASK_EXCEPTION


class ProcessBaseSwarmingTaskResultPipeline(BasePipeline):
  """A pipeline for monitoring swarming task and processing task result.

  This pipeline waits for result for a swarming task and processes the result to
  generate a dict for statuses for each test run.
  """

  HTTP_CLIENT = FinditHttpClient()
  # Making this pipeline asynchronous by setting this class variable.
  async = True

  def __init__(self, *args, **kwargs):
    super(ProcessBaseSwarmingTaskResultPipeline, self).__init__(*args, **kwargs)
    # This attribute is meant for use by the unittest only.
    self.last_params = {}

  def _CheckTestsRunStatuses(self, output_json, *_):
    """Checks result status for each test run and saves the numbers accordingly.

    Args:
      output_json (dict): A dict of all test results in the swarming task.

    Returns:
      tests_statuses (dict): A dict of different statuses for each test.

    Currently for each test, we are saving number of total runs,
    number of succeeded runs and number of failed runs.
    """
    tests_statuses = defaultdict(lambda: defaultdict(int))
    if output_json:
      for iteration in output_json.get('per_iteration_data'):
        for test_name, tests in iteration.iteritems():
          tests_statuses[test_name]['total_run'] += len(tests)
          for test in tests:
            tests_statuses[test_name][test['status']] += 1

    return tests_statuses

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

  def _ConvertDateTime(self, time_string):
    """Convert UTC time string to datetime.datetime."""
    if not time_string:
      return None
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
      # When microseconds are 0, the '.123456' suffix is elided.
      try:
        return datetime.datetime.strptime(time_string, fmt)
      except ValueError:
        pass
    raise ValueError('Failed to parse %s' % time_string)  # pragma: no cover

  def delay_callback(self, countdown, callback_params, name=None):
    target = appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND)
    try:
      task = self.get_callback_task(
          countdown=countdown,
          target=target,
          params={'callback_params': json.dumps(callback_params)},
          name=name)
      task.add(queue_name=constants.WATERFALL_ANALYSIS_QUEUE)
    except taskqueue.TombstonedTaskError:
      assert name
      logging.warning('A task named %s has already been added to the taskqueue',
                      name)

  def finalized(self, *args, **kwargs):
    try:
      task_id = self.kwargs.get('task_id')
      if not task_id and len(self.args) > 4:
        task_id = self.args[4]
      if task_id and task_id.lower() not in (NO_TASK, NO_TASK_EXCEPTION):
        taskqueue.Queue(
            constants.WATERFALL_ANALYSIS_QUEUE).delete_tasks_by_name(
                [task_id + '_cleanup_task'])
      else:
        logging.error('Did not receive a task_id at construction.')
    except taskqueue.BadTaskStateError, e:  # pragma: no cover
      logging.debug('Could not delete cleanup task: %s', e.message)
    return super(ProcessBaseSwarmingTaskResultPipeline, self).finalized(
        *args, **kwargs)

  def _GetPipelineResult(self, step_name, step_name_no_platform, task):
    # The sub-classes may use properties of the task as part of the result.
    _ = task
    return step_name, step_name_no_platform

  # Arguments number differs from overridden method - pylint: disable=W0221
  def callback(self, *args, **kwargs):
    """Transitional callback.

    This temporary hack should accept callbacks in the old format
    as well as the new one.
    """
    assert not args
    if 'callback_params' in kwargs:
      return self._callback(**kwargs)
    return self._callback(callback_params=kwargs)

  def _callback(self, callback_params, pipeline_id=None):
    """Monitors the swarming task and waits for it to complete."""
    if isinstance(callback_params, basestring):
      callback_params = json.loads(callback_params)
    _ = pipeline_id  # We don't do anything with this id.
    task_id = callback_params['task_id']
    assert task_id

    step_name = callback_params['step_name']
    call_args = callback_params['call_args']
    deadline = callback_params['deadline']
    server_query_interval_seconds = callback_params[
        'server_query_interval_seconds']
    task_started = callback_params['task_started']
    task_completed = callback_params['task_completed']
    step_name_no_platform = callback_params['step_name_no_platform']
    task = self._GetSwarmingTask(*call_args)

    def check_task_completion():
      if task_completed and data is not None:
        task.created_time = (task.created_time or
                             self._ConvertDateTime(data.get('created_ts')))
        task.started_time = (task.started_time or
                             self._ConvertDateTime(data.get('started_ts')))
        task.completed_time = (task.completed_time or
                               self._ConvertDateTime(data.get('completed_ts')))
        task.put()
        pipeline_result = self._GetPipelineResult(step_name,
                                                  step_name_no_platform, task)
        self.complete(pipeline_result)
      elif time.time() > deadline:  # pragma: no cover
        # Timeout.
        # Updates status as ERROR.
        task.status = analysis_status.ERROR
        task.error = {
            'code': swarming_util.TIMED_OUT,
            'message': 'Process swarming task result timed out'
        }
        task.put()
        timeout_hours = waterfall_config.GetSwarmingSettings().get(
            'task_timeout_hours')
        logging.error('Swarming task timed out after %d hours.' % timeout_hours)
        pipeline_result = self._GetPipelineResult(step_name,
                                                  step_name_no_platform, task)
        self.complete(pipeline_result)
      else:
        self.last_params = {
            'task_id': task_id,
            'step_name': step_name,
            'call_args': call_args,
            'deadline': deadline,
            'server_query_interval_seconds': server_query_interval_seconds,
            'task_started': task_started,
            'task_completed': task_completed,
            'step_name_no_platform': step_name_no_platform,
        }
        # Update the stored callback url with possibly modified params.
        new_callback_url = self.get_callback_url(
            callback_params=json.dumps(self.last_params))
        if task.callback_url != new_callback_url:  # pragma: no cover
          task.callback_url = new_callback_url
          task.put()

    data, error = swarming_util.GetSwarmingTaskResultById(
        task_id, self.HTTP_CLIENT)

    if error:
      # An error occurred at some point when trying to retrieve data from
      # the swarming server, even if eventually successful.
      task.error = error
      task.put()

      if not data:
        # Even after retry, no data was received.
        task.status = analysis_status.ERROR
        task.put()
        check_task_completion()
        return

    task_state = data['state']

    step_name_no_platform = (step_name_no_platform or swarming_util.GetTagValue(
        data.get('tags', {}), 'ref_name'))

    if task_state not in swarming_util.STATES_RUNNING:
      task_completed = True

      if task_state == swarming_util.STATE_COMPLETED:
        outputs_ref = data.get('outputs_ref')

        # If swarming task aborted because of errors in request arguments,
        # it's possible that there is no outputs_ref.
        if not outputs_ref:
          logging.error('outputs_ref for task %s is None', task_id)
          task.status = analysis_status.ERROR
          task.error = {
              'code': swarming_util.NO_TASK_OUTPUTS,
              'message': 'outputs_ref is None'
          }
          task.put()
          check_task_completion()
          return

        output_json, error = swarming_util.GetSwarmingTaskFailureLog(
            outputs_ref, self.HTTP_CLIENT)

        if error or not output_json:
          task.status = analysis_status.ERROR
          task.error = error or {
              'code': swarming_util.NO_OUTPUT_JSON,
              'message': 'output_json is None',
          }
          task.put()
          check_task_completion()
          return

        if not output_json.get('per_iteration_data'):
          task.status = analysis_status.ERROR
          task.error = {
              'code': swarming_util.NO_PER_ITERATION_DATA,
              'message': 'per_iteration_data is empty or missing'
          }
          task.put()
          check_task_completion()
          return

        tests_statuses = self._CheckTestsRunStatuses(output_json, *call_args)
        task.status = analysis_status.COMPLETED
        task.tests_statuses = tests_statuses
        task.canonical_step_name = step_name_no_platform
        task.put()
      else:
        # The swarming task did not complete.
        code = swarming_util.STATES_NOT_RUNNING_TO_ERROR_CODES[task_state]
        message = task_state

        task.status = analysis_status.ERROR
        task.error = {'code': code, 'message': message}
        task.put()

        logging.error('Swarming task stopped with status: %s' % task_state)

      tags = data.get('tags', {})
      priority_str = swarming_util.GetTagValue(tags, 'priority')
      if priority_str:
        task.parameters['priority'] = int(priority_str)
      task.put()
    else:  # pragma: no cover
      if task_state == 'RUNNING' and not task_started:
        # swarming task just starts, update status.
        task_started = True
        task.status = analysis_status.RUNNING
        task.put()

    check_task_completion()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self,
          master_name,
          builder_name,
          build_number,
          step_name,
          task_id=None,
          *args):
    """Monitors a swarming task.

    Args:
      master_name (str): The master name.
      builder_name (str): The builder name.
      build_number (str): The build number.
      step_name (str): The failed test step name.
      task_id (str): The task id to query the swarming server on the progresss
        of a swarming task.
    """
    call_args = self._GetArgs(master_name, builder_name, build_number,
                              step_name, *args)
    task = self._GetSwarmingTask(*call_args)

    task_id = task_id or task.task_id

    if not task_id:
      # The swarming task encountered an error when being triggered.
      if not task.error:  # pragma no branch
        task.error = {
            'error': 'Undetected error in swarming task. No task id found!',
            'message': 'Undetected error in swarming task. No task id found!'
        }
        task.put()
      return

    # Check to make this method idempotent.
    if task.callback_url and self.pipeline_id in task.callback_url:
      return

    timeout_hours = waterfall_config.GetSwarmingSettings().get(
        'task_timeout_hours')
    deadline = time.time() + timeout_hours * 60 * 60
    server_query_interval_seconds = waterfall_config.GetSwarmingSettings().get(
        'server_query_interval_seconds')
    task_started = False
    task_completed = False
    step_name_no_platform = None

    if task_id.lower() in (NO_TASK, NO_TASK_EXCEPTION):  # pragma: no branch
      # This situation happens in flake analysis: if the step with flaky test
      # didn't exist in checked build or the build had exception so the step
      # with flaky test didn't run at all, we should skip the build.
      task.task_id = None
      task.status = analysis_status.SKIPPED
      task.has_valid_artifact = task_id != NO_TASK_EXCEPTION
      task.tries = 0
      task.put()

      self.complete(
          self._GetPipelineResult(step_name, step_name_no_platform, task))
      return

    self.last_params = {
        'task_id': task_id,
        'step_name': step_name,
        'call_args': call_args,
        'deadline': deadline,
        'server_query_interval_seconds': server_query_interval_seconds,
        'task_started': task_started,
        'task_completed': task_completed,
        'step_name_no_platform': step_name_no_platform,
    }

    task.callback_url = self.get_callback_url(
        callback_params=json.dumps(self.last_params))
    task.callback_target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    task.put()

    # Guarantee one callback 10 minutes after the deadline to clean up even if
    # Swarming fails to call us back.
    self.delay_callback(
        (timeout_hours * 60 + 10) * 60,
        self.last_params,
        name=task_id + '_cleanup_task')

    # Run immediately in case the task already went from scheduled to started.
    self.callback(callback_params=self.last_params)
