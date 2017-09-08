# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import logging
import time

from common.waterfall.pubsub_callback import MakeSwarmingPubsubCallback
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.pipeline_wrapper import BasePipeline
from libs import analysis_status
from libs import time_util
from model.flake.flake_swarming_task import FlakeSwarmingTask
from waterfall import buildbot
from waterfall import swarming_util
from waterfall import waterfall_config

NO_TASK = 'no_task'
NO_TASK_EXCEPTION = 'no_task - exception'


class TriggerBaseSwarmingTaskPipeline(BasePipeline):  # pragma: no cover.
  """A pipeline to trigger a Swarming task to re-run selected tests of a step.

  This pipeline only supports test steps that run on Swarming and support the
  gtest filter.
  """

  def _GetSwarmingTaskName(self, ref_task_id):  # pragma: no cover.
    return 'findit/ref_task_id/%s/%s' % (
        ref_task_id, time_util.GetUTCNow().strftime('%Y-%m-%d %H:%M:%S %f'))

  def _CreateNewSwarmingTaskRequest(self,
                                    ref_task_id,
                                    ref_request,
                                    master_name,
                                    builder_name,
                                    build_number,
                                    step_name,
                                    tests,
                                    iterations,
                                    hard_timeout_seconds=None):
    """Returns a SwarmingTaskRequest instance to run the given tests only."""
    # Make a copy of the referred request and drop or overwrite some fields.
    new_request = copy.deepcopy(ref_request)
    new_request.name = self._GetSwarmingTaskName(ref_task_id)
    new_request.parent_task_id = ''
    new_request.user = ''

    if hard_timeout_seconds:
      new_request.execution_timeout_secs = hard_timeout_seconds

    _pubsub_callback = MakeSwarmingPubsubCallback(self.pipeline_id)
    new_request.pubsub_topic = _pubsub_callback.get('topic')
    new_request.pubsub_auth_token = _pubsub_callback.get('auth_token')
    new_request.pubsub_userdata = _pubsub_callback.get('user_data')

    # To force a fresh re-run and ignore cached result of any equivalent run.
    new_request.idempotent = False

    # Set the gtest_filter to run the given tests only.
    # Remove existing test filter first.
    new_request.extra_args = [
        a for a in new_request.extra_args
        if (not a.startswith('--gtest_filter') and
            not a.startswith('--test-launcher-filter-file'))
    ]
    new_request.extra_args.append('--gtest_filter=%s' % ':'.join(tests))

    # On Android, --gtest_repeat is only supported for gtest, but not for other
    # test types. E.g. instrumentation tests currently support it via
    # --test-repeat.
    #
    # Here we blindly treat all tests on Android as gtest, and let other test
    # types fail out, because it is hard to distinguish them programmatically
    # while the majority is gtest.
    #
    # https://crbug.com/669632 tracks the effort to unify the command switches
    # of the Android test runner that are used here.
    new_request.extra_args.append('--gtest_repeat=%s' % iterations)

    ref_os = swarming_util.GetTagValue(ref_request.tags, 'os') or ''
    if ref_os.lower() == 'android':  # Workaround. pragma: no cover.
      new_request.extra_args.append('--num_retries=0')
    else:
      new_request.extra_args.append('--test-launcher-retry-limit=0')

    # Also rerun disabled tests. Scenario: the test was disabled before Findit
    # runs any analysis. One possible case:
    #   1. A gtest became flaky on CQ, but Findit was not automatically
    #      triggered to run any analysis because:
    #      * the test is not flaky enough
    #      * chromium-try-flakes has filed/updated too many bugs
    #   2. The test got disabled, but no culprit was identified.
    #   3. Some developer starts the investigation and requests Findit to
    #      analyze the flaky test.
    #   4. Findit picks the latest Waterfall build of the matching configuration
    #      for the CQ build in which the flaky test is found.
    #   5. In the picked Waterfall build, the test is already disabled.
    #
    # Note: test runner on Android ignores this flag because it is not supported
    # yet even though it exists.
    new_request.extra_args.append('--gtest_also_run_disabled_tests')

    # Remove the env setting for sharding.
    sharding_settings = ['GTEST_SHARD_INDEX', 'GTEST_TOTAL_SHARDS']
    new_request.env = [
        e for e in new_request.env if e['key'] not in sharding_settings
    ]

    # Reset tags for searching and monitoring.
    ref_name = swarming_util.GetTagValue(ref_request.tags, 'name')
    new_request.tags = []
    new_request.tags.append('ref_master:%s' % master_name)
    new_request.tags.append('ref_buildername:%s' % builder_name)
    new_request.tags.append('ref_buildnumber:%s' % build_number)
    new_request.tags.append('ref_stepname:%s' % step_name)
    new_request.tags.append('ref_task_id:%s' % ref_task_id)
    new_request.tags.append('ref_name:%s' % ref_name)

    # Add additional tags.
    for tag in self._GetAdditionalTags():
      new_request.tags.append(tag)

    return new_request

  def _GetAdditionalTags(self):
    """Returns additional tags for the Swarming task."""
    return []

  def _GetArgs(self, master_name, builder_name, build_number, step_name, tests):
    # Returns an array you can pass into _GetSwarmingTask, _CreateSwarmingTask,
    # _NeedANewSwarmingTask as the arguments.

    # Should be overwritten in child method.
    raise NotImplementedError('_GetArgs should be implemented in child class')

  def _GetSwarmingTask(self):
    # Get the appropriate kind of Swarming Task (Wf or Flake).

    # Should be overwritten in child method.
    raise NotImplementedError(
        '_GetSwarmingTask should be implemented in child class')

  def _CreateSwarmingTask(self):
    # Create the appropriate kind of Swarming Task (Wf or Flake)

    # Should be overwritten in child method.
    raise NotImplementedError(
        '_CreateSwarmingTask should be implemented in child class')

  def _OnTaskTriggered(self):
    """A hook function called after the Swarming task is actually triggered."""
    pass

  def _NeedANewSwarmingTask(self, *args, **kwargs):
    swarming_task = self._GetSwarmingTask(*args)
    iterations_to_rerun = kwargs.get('iterations_to_rerun') if kwargs else None
    force = kwargs.get('force') if kwargs else False
    if not swarming_task:
      swarming_task = self._CreateSwarmingTask(*args)
      swarming_task.status = analysis_status.PENDING
      swarming_task.put()
      return True
    else:
      if isinstance(swarming_task, FlakeSwarmingTask) and swarming_task.queued:
        # The task has been created but has not yet been executed for cases it
        # was triggered through Findit API.
        return True

      if (force or (swarming_task.parameters and iterations_to_rerun and
                    swarming_task.parameters.get('iterations_to_rerun') !=
                    iterations_to_rerun)):
        # Triggering a new swarming task on the same build for flaky analysis.
        # Resets the existing swarming task.
        swarming_task.Reset()
        swarming_task.put()
        return True

      # TODO(http://crbug.com/585676): Rerun the Swarming task if it runs into
      # unexpected infra errors.
      return False

  def _GetSwarmingTaskId(self, *args):
    swarming_settings = waterfall_config.GetSwarmingSettings()
    wait_seconds = swarming_settings.get('get_swarming_task_id_wait_seconds')
    timeout_seconds = swarming_settings.get(
        'get_swarming_task_id_timeout_seconds')
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
      swarming_task = self._GetSwarmingTask(*args)

      if not swarming_task:  # pragma: no cover. Pipeline will retry.
        raise Exception('Swarming task was deleted unexpectedly!')

      if swarming_task.task_id:
        return swarming_task.task_id

      # Wait for the existing pipeline to start the Swarming task.
      time.sleep(wait_seconds)

    raise Exception('Time out!')  # pragma: no cover. Pipeline will retry.

  def _GetIterationsToRerun(self):
    # How many times we want to run the swarming rerun
    # By default, it's what's in wf_config
    raise NotImplementedError(
        '_GetIterationsToRerun should be implemented in child class')

  def GetBuildDataFromMilo(self, master_name, builder_name, build_number,
                           http_client):
    """Checks if the build had exception, if so don't run the step."""
    json_data = buildbot.GetBuildDataFromMilo(master_name, builder_name,
                                              build_number, http_client)
    if not json_data:
      logging.error('Failed to get build data for %s, %s, %s' %
                    (master_name, builder_name, build_number))
      return False

    try:
      build_data = json.loads(json_data)
    except ValueError:
      logging.error('Failed to decode build data for %s, %s, %s' %
                    (master_name, builder_name, build_number))
      return False

    build_result = buildbot.GetBuildResult(build_data)

    return build_result == buildbot.EXCEPTION

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self,
          master_name,
          builder_name,
          build_number,
          step_name,
          tests,
          iterations_to_rerun=None,
          hard_timeout_seconds=None,
          force=False):
    """Triggers a new Swarming task to run the given tests.

    Args:
      master_name (str): The master name.
      builder_name (str): The builder name.
      build_number (str): The build number.
      step_name (str): The failed test step name.
      tests (list): A list of test cases, eg: ['suite1.test1', 'suite2.testw2']
      iterations_to_rerun (int): Number of iterations to run a test.
      hard_timeout_seconds (int): How many seconds the overall task has to run.
      force (bool): If this is a forced rerun from scratch. A rerun by an admin
          will trigger this.

    Returns:
      task_id (str): The new Swarming task that re-run the given tests.
    """
    call_args = self._GetArgs(master_name, builder_name, build_number,
                              step_name, tests)
    # Check if a new Swarming Task is really needed.
    if not self._NeedANewSwarmingTask(
        *call_args, iterations_to_rerun=iterations_to_rerun, force=force):
      return self._GetSwarmingTaskId(*call_args)
    assert tests
    http_client = HttpClientAppengine()

    # 0. Retrieve existing Swarming task ids for the given step.
    swarming_task_items = swarming_util.ListSwarmingTasksDataByTags(
        master_name, builder_name, build_number, http_client,
        {'stepname': step_name})
    if len(swarming_task_items) < 1:
      if self.GetBuildDataFromMilo(master_name, builder_name, build_number,
                                   http_client):
        return NO_TASK_EXCEPTION
      return NO_TASK

    ref_task_id = swarming_task_items[0]['task_id']

    # 1. Retrieve Swarming task parameters from a given Swarming task id.
    ref_request = swarming_util.GetSwarmingTaskRequest(ref_task_id, http_client)

    # 2. Update/Overwrite parameters for the re-run.
    iterations_to_rerun = iterations_to_rerun or self._GetIterationsToRerun()

    new_request = self._CreateNewSwarmingTaskRequest(
        ref_task_id,
        ref_request,
        master_name,
        builder_name,
        build_number,
        step_name,
        tests,
        iterations_to_rerun,
        hard_timeout_seconds=hard_timeout_seconds)

    # 3. Trigger a new Swarming task to re-run the failed tests.
    task_id, error = swarming_util.TriggerSwarmingTask(new_request, http_client)

    # Update swarming task info.
    swarming_task = self._GetSwarmingTask(*call_args)

    if isinstance(swarming_task, FlakeSwarmingTask):
      swarming_task.queued = False

    swarming_task.task_id = task_id
    swarming_task.timeout_seconds = hard_timeout_seconds
    swarming_task.parameters['tests'] = tests
    swarming_task.parameters['iterations_to_rerun'] = iterations_to_rerun
    swarming_task.parameters['ref_name'] = swarming_util.GetTagValue(
        new_request.tags, 'ref_name')

    if error:
      swarming_task.error = error
    else:
      logging.info('A Swarming task was triggered:%s', task_id)

    swarming_task.put()

    # Call the hook function after the task is triggered.
    self._OnTaskTriggered()

    return task_id or NO_TASK_EXCEPTION
