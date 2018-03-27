# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Client library to interact with swarming API."""

import json
import urllib

from infra_api_clients import http_client_util
from infra_api_clients.swarming.swarming_bot_counts import SwarmingBotCounts
from infra_api_clients.swarming.swarming_task_data import SwarmingTaskData
from infra_api_clients.swarming.swarming_task_request import SwarmingTaskRequest

# Swarming URL templates.
_BOT_COUNT_URL = 'https://%s/api/swarming/v1/bots/count%s'
_NEW_TASK_URL = 'https://%s/api/swarming/v1/tasks/new'
_TASK_ID_URL = 'https://%s/api/swarming/v1/task/%s/request'
_LIST_TASK_URL = 'https://%s/api/swarming/v1/tasks/list%s'
_TASK_RESULT_URL = 'https://%s/api/swarming/v1/task/%s/result'


def GetSwarmingTaskRequest(host, task_id, http_client):
  """Returns request data of the given task."""
  url = _TASK_ID_URL % (host, task_id)
  content, error = http_client_util.SendRequestToServer(url, http_client)

  if not error:
    json_data = json.loads(content)
    return SwarmingTaskRequest.FromSerializable(json_data)
  return None


def TriggerSwarmingTask(host, request, http_client):
  """Triggers a new Swarming task for the given request.

  Args:
    request (SwarmingTaskRequest): A Swarming task request.
    http_client (FinditHttpClient): An http client with automatic retry.
  """

  response_data, error = http_client_util.SendRequestToServer(
      _NEW_TASK_URL % host, http_client, post_data=request.ToSerializable())

  if not error:
    return json.loads(response_data)['task_id'], None

  return None, error


def GetSwarmingTaskResultById(host, task_id, http_client):
  """Gets swarming result, checks state and returns outputs ref if needed."""
  base_url = _TASK_RESULT_URL % (host, task_id)
  json_data = {}

  data, error = http_client_util.SendRequestToServer(base_url, http_client)

  if not error:
    json_data = json.loads(data)

  return json_data, error


# TODO(crbug/820264): Move the logic to retry_http_client.py
def ParametersToQueryString(parameters, field):
  if isinstance(parameters, dict):
    parameters_list = [
        urllib.quote('%s:%s' % (k, v)) for k, v in parameters.iteritems()
    ]
  else:
    parameters_list = parameters
  query_string = ('&%s=' % field).join(parameters_list)
  # Url looks like 'https://chromium-swarm.appspot.com/api/swarming/v1/bots
  # /count?dimensions=os:Windows-7-SP1&dimensions=cpu:x86-64'
  return '?%s=%s' % (field, query_string)


def GetBotCounts(host, dimensions, http_client):
  """Gets number of swarming bots for certain dimensions.

  Args:
    dimensions (dict): A dict of dimensions.
    http_client (HttpClient): The httpclient object with which to make the
      server calls.
  Returns:
    bot_counts(SwarmingBotCounts): Numbers of swarming bots in different states.
  """
  url = _BOT_COUNT_URL % (host,
                          ParametersToQueryString(dimensions, 'dimensions'))

  content, error = http_client_util.SendRequestToServer(url, http_client)
  if error or not content:
    return None

  return SwarmingBotCounts(json.loads(content))


def GenerateIsolatedData(outputs_ref):
  if not outputs_ref:
    return {}
  return {
      'digest': outputs_ref['isolated'],
      'namespace': outputs_ref['namespace'],
      'isolatedserver': outputs_ref['isolatedserver']
  }


def ListTasks(host, tags, http_client):
  """List tasks based on tags.

  Args:
    tags (dict): A dict of tags.
    http_client (HttpClient): The httpclient object with which to make the
      server calls.
  Returns:
    items (list): A list of SwarmingTaskData for all tasks with queried tags.
  """
  base_url = _LIST_TASK_URL % (host, ParametersToQueryString(tags, 'tags'))

  items_json = []
  cursor = None

  while True:
    if not cursor:
      url = base_url
    else:
      url = base_url + '&cursor=%s' % urllib.quote(cursor)
    new_data, _ = http_client_util.SendRequestToServer(url, http_client)

    if not new_data:
      break

    new_data_json = json.loads(new_data)
    if new_data_json.get('items'):
      items_json.extend(new_data_json['items'])

    if new_data_json.get('cursor'):
      cursor = new_data_json['cursor']
    else:
      break

  return [SwarmingTaskData(item) for item in items_json]


def GetTagValue(tags, tag_name):
  """Returns the content for a specific tag."""
  tag_prefix = tag_name + ':'
  content = None
  for tag in tags:
    if tag.startswith(tag_prefix):
      content = tag[len(tag_prefix):]
      break
  return content
