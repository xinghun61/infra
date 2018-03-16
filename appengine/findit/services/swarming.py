# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for swarming related logics that only for Findit.
"""

from collections import defaultdict
import logging

from infra_api_clients.swarming import swarming_util
from infra_api_clients.swarming.swarming_task_request import SwarmingTaskRequest
from waterfall import waterfall_config


def SwarmingHost():
  return waterfall_config.GetSwarmingSettings().get('server_host')


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
  request.priority = max(100, swarming_settings.get('default_request_priority'))
  request.expiration_secs = request_expiration_hours * 60 * 60

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
    http_client(RetryHttpClient): The http client to send HTTPs requests.
    master_name(str): Value of the master tag.
    builder_name(str): Value of the buildername tag.
    build_number(int): Value of the buildnumber tag.
    step_name(str): Valie of the stepname tag.
    additional_tag_filters(dict): Additional tags.

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
    master_name(str): Value of the master tag.
    builder_name(str): Value of the buildername tag.
    build_number(int): Value of the buildnumber tag.
    step_name(str): Value of the stepname tag.
    http_client(RetryHttpClient): The http client to send HTTPs requests.
    only_failure(bool): A flag to determine if only failure info is needed.
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
    master_name (str): The name of the main waterall master.
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
