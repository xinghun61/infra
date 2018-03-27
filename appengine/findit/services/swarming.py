# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for swarming related logics that only for Findit.
"""

from collections import defaultdict
import copy
import json
import logging

from google.appengine.api import app_identity

from common.waterfall.pubsub_callback import MakeSwarmingPubsubCallback
from gae_libs import token
from infra_api_clients.swarming import swarming_util
from infra_api_clients.swarming.swarming_task_request import SwarmingTaskRequest
from libs import time_util
from libs.list_of_basestring import ListOfBasestring
from waterfall import waterfall_config


def SwarmingHost():
  return waterfall_config.GetSwarmingSettings().get('server_host')


def GetReferredSwarmingTaskRequestInfo(master_name, builder_name, build_number,
                                       step_name, http_client):
  """Gets referred swarming task request.

  Returns:
    (ref_task_id, ref_request): Referred swarming task id and request.
  """
  swarming_task_items = ListSwarmingTasksDataByTags(
      http_client, master_name, builder_name, build_number, step_name)

  if not swarming_task_items:
    raise Exception('Cannot find referred swarming task for %s/%s/%d/%s' %
                    (master_name, builder_name, build_number, step_name))

  ref_task_id = swarming_task_items[0]['task_id']
  ref_request = swarming_util.GetSwarmingTaskRequest(SwarmingHost(),
                                                     ref_task_id, http_client)
  return ref_task_id, ref_request


def _UpdateRequestWithPubSubCallback(request, runner_id, use_new_pubsub):
  if not use_new_pubsub:
    _pubsub_callback = MakeSwarmingPubsubCallback(runner_id)
  else:
    _pubsub_callback = {
        'topic':
            'projects/%s/topics/swarming' % app_identity.get_application_id(),
        'auth_token':
            token.GenerateAuthToken('pubsub', 'swarming', runner_id),
        'user_data':
            json.dumps({
                'runner_id': runner_id
            })
    }
  request.pubsub_topic = _pubsub_callback.get('topic')
  request.pubsub_auth_token = _pubsub_callback.get('auth_token')
  request.pubsub_userdata = _pubsub_callback.get('user_data')


def CreateNewSwarmingTaskRequestTemplate(runner_id,
                                         ref_task_id,
                                         ref_request,
                                         master_name,
                                         builder_name,
                                         step_name,
                                         tests,
                                         iterations,
                                         use_new_pubsub=False):
  """Returns a SwarmingTaskRequest instance to run the given tests only.

  Args:
    ref_task_id (str): Id of the referred swarming task.
    ref_request (SwarmingTaskRequest): Request of the referred swarming task.
    master_name (str): The name of the main waterfall master for a build.
    builder_name (str): The name of the main waterfall builder for a build.
    step_name (str): The name of a failed step in the build.
    tests (list): A list of tests in the step that we want to rerun in task.
    iterations (int): Number of iterations each test should run.
    use_new_pubsub (bool): Set as true to use the new PubSub topic and callback.
  """
  # Make a copy of the referred request and drop or overwrite some fields.
  new_request = copy.deepcopy(ref_request)
  new_request.name = 'findit/ref_task_id/%s/%s' % (
      ref_task_id, time_util.GetUTCNow().strftime('%Y-%m-%d %H:%M:%S %f'))
  new_request.parent_task_id = ''
  new_request.user = ''

  _UpdateRequestWithPubSubCallback(new_request, runner_id, use_new_pubsub)

  # To force a fresh re-run and ignore cached result of any equivalent run.
  new_request.properties.idempotent = False

  # Set the gtest_filter to run the given tests only.
  # Remove existing test filter first.

  new_request.properties.extra_args = ListOfBasestring.FromSerializable([
      a for a in new_request.properties.extra_args
      if (not a.startswith('--gtest_filter') and
          not a.startswith('--test-launcher-filter-file'))
  ])
  new_request.properties.extra_args.append(
      '--gtest_filter=%s' % ':'.join(tests))

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
  new_request.properties.extra_args.append('--gtest_repeat=%s' % iterations)

  ref_os = swarming_util.GetTagValue(ref_request.tags, 'os') or ''
  if ref_os.lower() == 'android':  # Workaround. pragma: no cover.
    new_request.properties.extra_args.append('--num_retries=0')
  else:
    new_request.properties.extra_args.append('--test-launcher-retry-limit=0')

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
  new_request.properties.extra_args.append('--gtest_also_run_disabled_tests')

  # Remove the env setting for sharding.
  sharding_settings = ['GTEST_SHARD_INDEX', 'GTEST_TOTAL_SHARDS']
  new_request.properties.env = [
      e for e in new_request.properties.env if e['key'] not in sharding_settings
  ]

  # Reset tags for searching and monitoring.
  ref_name = swarming_util.GetTagValue(ref_request.tags, 'name')
  new_request.tags = ListOfBasestring()
  new_request.tags.append('ref_master:%s' % master_name)
  new_request.tags.append('ref_buildername:%s' % builder_name)

  new_request.tags.append('ref_stepname:%s' % step_name)
  new_request.tags.append('ref_name:%s' % ref_name)
  new_request.tags.extend(
      ['findit:1', 'project:Chromium', 'purpose:post-commit'])

  # Use a priority much lower than CQ for now (CQ's priority is 30).
  # Later we might use a higher priority -- a lower value here.
  # Note: the smaller value, the higher priority.
  swarming_settings = waterfall_config.GetSwarmingSettings()
  request_expiration_hours = swarming_settings.get('request_expiration_hours')
  new_request.priority = str(
      max(100, swarming_settings.get('default_request_priority')))
  new_request.expiration_secs = str(request_expiration_hours * 60 * 60)

  return new_request


# NOTE: This function will be deprecated soon.
# TODO(crbug/808695): This is just to support the soon to be deprecated
# trigger_base_swarming_task_pipeline. Remove this when the pipeline is removed.
def TriggerSwarmingTask(request, http_client):
  """Triggers a new Swarming task for the given request.

  The Swarming task priority will be overwritten, and extra tags might be added.
  Args:
    request (SwarmingTaskRequest): A Swarming task request.
    http_client (RetryHttpClient): An http client with automatic retry.
  """
  # Use a priority much lower than CQ for now (CQ's priority is 30).
  # Later we might use a higher priority -- a lower value here.
  # Note: the smaller value, the higher priority.
  swarming_settings = waterfall_config.GetSwarmingSettings()
  request_expiration_hours = swarming_settings.get('request_expiration_hours')
  request.priority = str(
      max(100, swarming_settings.get('default_request_priority')))
  request.expiration_secs = str(request_expiration_hours * 60 * 60)

  request.tags.extend(['findit:1', 'project:Chromium', 'purpose:post-commit'])

  return swarming_util.TriggerSwarmingTask(SwarmingHost(), request, http_client)


def ListSwarmingTasksDataByTags(http_client,
                                master_name,
                                builder_name,
                                build_number,
                                step_name=None,
                                additional_tag_filters=None):
  """Downloads tasks data from swarming server.

  Args:
    http_client (RetryHttpClient): The http client to send HTTPs requests.
    master_name (str): Value of the master tag.
    builder_name (str): Value of the buildername tag.
    build_number (int): Value of the buildnumber tag.
    step_name (str): Value of the stepname tag.
    additional_tag_filters (dict): Additional tags.

  Returns:
    (list):  A list of SwarmingTaskData for all tasks with queried tags.
  """
  tag_filters = {
      'master': master_name,
      'buildername': builder_name,
      'buildnumber': build_number
  }
  if step_name:
    tag_filters['stepname'] = step_name

  additional_tag_filters = additional_tag_filters or {}
  tag_filters.update(additional_tag_filters)

  return swarming_util.ListTasks(SwarmingHost(), tag_filters, http_client)


def GetNeededIsolatedDataFromTaskResults(task_results, only_failure):
  needed_isolated_data = defaultdict(list)
  for item in task_results:
    swarming_step_name = item.tags.get('stepname')[
        0] if 'stepname' in item.tags else None

    if not item.outputs_ref or not swarming_step_name:
      # Task might time out and no outputs_ref was saved.
      continue

    if only_failure:
      if item.non_internal_failure:
        isolated_data = swarming_util.GenerateIsolatedData(item.outputs_ref)
        needed_isolated_data[swarming_step_name].append(isolated_data)
    else:
      isolated_data = swarming_util.GenerateIsolatedData(item.outputs_ref)
      needed_isolated_data[swarming_step_name].append(isolated_data)
  return needed_isolated_data


def GetIsolatedDataForStep(master_name,
                           builder_name,
                           build_number,
                           step_name,
                           http_client,
                           only_failure=True):
  """Returns the isolated data for a specific step.

  Args:
    master_name (str): Value of the master tag.
    builder_name (str): Value of the buildername tag.
    build_number (int): Value of the buildnumber tag.
    step_name (str): Value of the stepname tag.
    http_client (RetryHttpClient): The http client to send HTTPs requests.
    only_failure (bool): A flag to determine if only failure info is needed.
  """
  step_isolated_data = []
  items = ListSwarmingTasksDataByTags(http_client, master_name, builder_name,
                                      build_number, step_name)
  if not items:
    return step_isolated_data

  step_isolated_data = GetNeededIsolatedDataFromTaskResults(items, only_failure)
  return step_isolated_data[step_name]


def GetIsolatedDataForFailedStepsInABuild(
    master_name, builder_name, build_number, failed_steps, http_client):
  """Gets the isolated data for failed steps for a build.

  Args:
    master_name (str): The name of the main waterfall master.
    builder_name (str): The name of the main waterfall builder.
    build_number (int): The build number to retrieve the isolated sha of.
    failed_steps (TestFailedSteps): A dict of failed steps.

  Returns:
    build_isolated_data(dict): A dict of isolated data of failed steps in a
      build.
  """
  items = ListSwarmingTasksDataByTags(http_client, master_name, builder_name,
                                      build_number)
  if not items:
    return {}

  isolated_data = GetNeededIsolatedDataFromTaskResults(items, True)
  build_isolated_data = {}
  for step, data in isolated_data.iteritems():
    if step in failed_steps:
      build_isolated_data[step] = data
  return build_isolated_data


def GetIsolatedShaForStep(master_name, builder_name, build_number, step_name,
                          http_client):
  """Gets the isolated sha of a master/builder/build/step.

  Args:
    master_name (str): The name of the main waterall master.
    builder_name (str): The name of the main waterfall builder.
    build_number (int): The build number to retrieve the isolated sha of.
    step_name (str): The step name to retrieve the isolated sha of.

  Returns:
    (str): The isolated sha pointing to the compiled binaries at the requested
        configuration.
  """
  items = ListSwarmingTasksDataByTags(http_client, master_name, builder_name,
                                      build_number, step_name)
  if not items:
    logging.error('Failed to get swarming task data for %s/%s/%s/%s',
                  master_name, builder_name, build_number, step_name)
    return None

  # Each task should have the same sha, so only need to read from the first one.
  if items[0].inputs_ref_sha:
    return items[0].inputs_ref_sha

  logging.error('Isolated sha not found for %s/%s/%s/%s', master_name,
                builder_name, build_number, step_name)
  return None


def CanFindSwarmingTaskFromBuildForAStep(http_client, master_name, builder_name,
                                         build_number, step_name):
  tasks = ListSwarmingTasksDataByTags(http_client, master_name, builder_name,
                                      build_number, step_name)
  return len(tasks) > 0
