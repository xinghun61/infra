# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import logging
import urllib
import zlib

from common import http_client_util
from waterfall import waterfall_config
from waterfall.swarming_task_request import SwarmingTaskRequest

# Swarming task states.
STATES_RUNNING = ('RUNNING', 'PENDING')
STATE_COMPLETED = 'COMPLETED'
STATES_NOT_RUNNING = ('BOT_DIED', 'CANCELED', 'COMPLETED', 'EXPIRED',
                      'TIMED_OUT')

# TODO(crbug.com/785463): Use enum for error codes.

# Swarming task stopped error codes.
BOT_DIED = 30
CANCELED = 40
EXPIRED = 50
TIMED_OUT = 60

STATES_NOT_RUNNING_TO_ERROR_CODES = {
    'BOT_DIED': BOT_DIED,
    'CANCELED': CANCELED,
    'EXPIRED': EXPIRED,
    'TIMED_OUT': TIMED_OUT,
}

# Outputs_ref is None.
NO_TASK_OUTPUTS = 300

# Unable to retrieve output json.
NO_OUTPUT_JSON = 320

# Other/miscellaneous error codes.
UNKNOWN = 1000

# Swarming URL templates.
BOT_COUNT_URL = 'https://%s/api/swarming/v1/bots/count%s'
NEW_TASK_URL = 'https://%s/api/swarming/v1/tasks/new'
TASK_ID_URL = 'https://%s/api/swarming/v1/task/%s/request'
TASK_RESULT_URL = 'https://%s/api/swarming/v1/task/%s/result'


def SwarmingHost():
  return waterfall_config.GetSwarmingSettings().get('server_host')


def GetSwarmingTaskRequest(task_id, http_client):
  """Returns an instance of SwarmingTaskRequest representing the given task."""
  url = TASK_ID_URL % (SwarmingHost(), task_id)
  content, error = http_client_util.SendRequestToServer(url, http_client)

  # TODO(lijeffrey): Handle/report error in calling functions.
  if not error:
    json_data = json.loads(content)
    return SwarmingTaskRequest.Deserialize(json_data)
  return None


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

  response_data, error = http_client_util.SendRequestToServer(
      NEW_TASK_URL % SwarmingHost(), http_client, post_data=request.Serialize())

  if not error:
    return json.loads(response_data)['task_id'], None

  return None, error


def ListSwarmingTasksDataByTags(master_name,
                                builder_name,
                                build_number,
                                http_client,
                                additional_tag_filters=None):
  """Downloads tasks data from swarming server.

  Args:
    master_name(str): Value of the master tag.
    builder_name(str): Value of the buildername tag.
    build_number(int): Value of the buildnumber tag.
    http_client(RetryHttpClient): The http client to send HTTPs requests.
    additional_tag_filters(dict): More tag filters to be added.

  Returns:
    ([{
      'swarming_task_id': ...,
      'completed_ts': ...,
      'started_ts': ...,
      ...
    }, ...])
  """
  base_url = ('https://%s/api/swarming/v1/tasks/'
              'list?tags=%s&tags=%s&tags=%s') % (
                  waterfall_config.GetSwarmingSettings().get('server_host'),
                  urllib.quote('master:%s' % master_name),
                  urllib.quote('buildername:%s' % builder_name),
                  urllib.quote('buildnumber:%d' % build_number))
  additional_tag_filters = additional_tag_filters or {}
  for tag_name, tag_value in additional_tag_filters.iteritems():
    base_url += '&tags=%s' % urllib.quote('%s:%s' % (tag_name, tag_value))

  items = []
  cursor = None

  while True:
    if not cursor:
      url = base_url
    else:
      url = base_url + '&cursor=%s' % urllib.quote(cursor)
    new_data, _ = http_client_util.SendRequestToServer(
        url, http_client)

    # TODO(lijeffrey): handle error in calling functions.
    if not new_data:
      break

    new_data_json = json.loads(new_data)
    if new_data_json.get('items'):
      items.extend(new_data_json['items'])

    if new_data_json.get('cursor'):
      cursor = new_data_json['cursor']
    else:
      break

  return items


def GenerateIsolatedData(outputs_ref):
  if not outputs_ref:
    return {}
  return {
      'digest': outputs_ref['isolated'],
      'namespace': outputs_ref['namespace'],
      'isolatedserver': outputs_ref['isolatedserver']
  }


def GetSwarmingTaskResultById(task_id, http_client):
  """Gets swarming result, checks state and returns outputs ref if needed."""
  base_url = TASK_RESULT_URL % (SwarmingHost(), task_id)
  json_data = {}

  data, error = http_client_util.SendRequestToServer(
      base_url, http_client)

  if not error:
    json_data = json.loads(data)

  return json_data, error


def GetSwarmingTaskFailureLog(outputs_ref, http_client):
  """Downloads failure log from isolated server."""
  isolated_data = GenerateIsolatedData(outputs_ref)
  return DownloadTestResults(isolated_data, http_client)


def GetTagValue(tags, tag_name):
  """Returns the content for a specific tag."""
  tag_prefix = tag_name + ':'
  content = None
  for tag in tags:
    if tag.startswith(tag_prefix):
      content = tag[len(tag_prefix):]
      break
  return content


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
  data = ListSwarmingTasksDataByTags(master_name, builder_name, build_number,
                                     http_client, {
                                         'stepname': step_name
                                     })
  if not data:
    return step_isolated_data

  for item in data:
    if not item.get('outputs_ref'):
      # Task might time out and no outputs_ref was saved.
      continue

    if only_failure:
      if item['failure'] and not item['internal_failure']:
        # Only retrieves test results from tasks which have failures and
        # the failure should not be internal infrastructure failure.
        isolated_data = GenerateIsolatedData(item['outputs_ref'])
        step_isolated_data.append(isolated_data)
    else:
      isolated_data = GenerateIsolatedData(item['outputs_ref'])
      step_isolated_data.append(isolated_data)

  return step_isolated_data


def GetIsolatedShaForStep(master_name, builder_name, build_number, step_name,
                          http_client):
  """Gets the isolated sha of a master/builder/build/step to send to swarming.

  Args:
    master_name (str): The name of the main waterall master.
    builder_name (str): The name of the main waterfall builder.
    build_number (int): The build number to retrieve the isolated sha of.
    step_name (str): The step name to retrieve the isolated sha of.

  Returns:
    (str): The isolated sha pointing to the compiled binaries at the requested
        configuration.
  """
  data = ListSwarmingTasksDataByTags(master_name, builder_name, build_number,
                                     http_client, {
                                         'stepname': step_name
                                     })
  if not data:
    logging.error('Failed to get swarming task data for %s/%s/%s/%s',
                  master_name, builder_name, build_number, step_name)
    return None

  # Each task should have the same sha, so only need to read from the first one.
  tags = data[0]['tags']
  sha = GetTagValue(tags, 'data')
  if sha:
    return sha

  logging.error('Isolated sha not found for %s/%s/%s/%s', master_name,
                builder_name, build_number, step_name)
  return None


def _FetchOutputJsonInfoFromIsolatedServer(isolated_data, http_client):
  """Sends POST request to isolated server and returns response content.

  This function is used for fetching
    1. hash code for the output.json file,
    2. the redirect url.
  """
  if not isolated_data:
    return None

  post_data = {
      'digest': isolated_data['digest'],
      'namespace': {
          'namespace': isolated_data['namespace']
      }
  }
  url = '%s/api/isolateservice/v1/retrieve' % isolated_data['isolatedserver']

  return http_client_util.SendRequestToServer(
      url, http_client, post_data=post_data)


def _ProcessRetrievedContent(output_json_content, http_client):
  """Downloads output.json file from isolated server or process it directly.

  If there is a url provided, send get request to that url to download log;
  else the log would be in content so use it directly.
  """
  json_content = json.loads(output_json_content)
  output_json_url = json_content.get('url')
  if output_json_url:
    get_content, _ = http_client_util.SendRequestToServer(
        output_json_url, http_client)
    # TODO(lijeffrey): handle error in calling function.
  elif json_content.get('content'):
    get_content = base64.b64decode(json_content['content'])
  else:  # pragma: no cover
    get_content = None  # Just for precausion.
  try:
    return json.loads(zlib.decompress(get_content)) if get_content else None
  except ValueError:  # pragma: no cover
    logging.info(
        'swarming result is invalid: %s' % zlib.decompress(get_content))
    return None


def DownloadTestResults(isolated_data, http_client):
  """Downloads the output.json file and returns the json object.

  The basic steps to get test results are:
  1. Use isolated_data to get hash to output.json,
  2. Use hash from step 1 to get test results.

  But in each step, if the returned content is too big, we may not directly get
  the content, instead we get a url and we need to send an extra request to the
  url. This is handled in _ProcessRetrievedContent.
  """
  # First POST request to get hash for the output.json file.
  content, error = _FetchOutputJsonInfoFromIsolatedServer(
      isolated_data, http_client)
  if error:
    return None, error

  processed_content = _ProcessRetrievedContent(content, http_client)
  output_json_hash = processed_content.get('files', {}).get(
      'output.json', {}).get('h') if processed_content else None
  if not output_json_hash:
    return None, None

  # Second POST request to get the redirect url for the output.json file.
  data_for_output_json = {
      'digest': output_json_hash,
      'namespace': isolated_data['namespace'],
      'isolatedserver': isolated_data['isolatedserver']
  }

  output_json_content, error = _FetchOutputJsonInfoFromIsolatedServer(
      data_for_output_json, http_client)
  if error:
    return None, error
  # GET Request to get output.json file.
  return _ProcessRetrievedContent(output_json_content, http_client), None


def GetIsolatedOutputForTask(task_id, http_client):
  """Get isolated output for a swarming task based on it's id."""
  json_data, error = GetSwarmingTaskResultById(task_id, http_client)

  if error or not json_data:
    return None

  outputs_ref = json_data.get('outputs_ref')
  if not outputs_ref:
    return None

  output_json, error = GetSwarmingTaskFailureLog(outputs_ref, http_client)

  if error:
    return None
  return output_json


def DimensionsToQueryString(dimensions):
  if isinstance(dimensions, dict):
    dimension_list = ['%s:%s' % (k, v) for k, v in dimensions.iteritems()]
  else:
    dimension_list = dimensions
  dimension_qs = '&dimensions='.join(dimension_list)
  # Url looks like 'https://chromium-swarm.appspot.com/api/swarming/v1/bots
  # /count?dimensions=os:Windows-7-SP1&dimensions=cpu:x86-64'
  return '?dimensions=%s' % dimension_qs


def GetSwarmingBotCounts(dimensions, http_client):
  """Gets number of swarming bots for certain dimensions.

  Args:
    dimensions (dict): A dict of dimensions.
    http_client (HttpClient): The httpclient object with which to make the
      server calls.
  Returns:
    bot_counts (dict): Dict of numbers of available swarming bots.
  """
  if not dimensions:
    return {}

  url = BOT_COUNT_URL % (SwarmingHost(), DimensionsToQueryString(dimensions))

  content, error = http_client_util.SendRequestToServer(
      url, http_client)
  if error or not content:
    return {}

  content_data = json.loads(content)

  bot_counts = {
      k: int(content_data.get(k, 0))
      for k in ('busy', 'count', 'dead', 'quarantined')
  }
  bot_counts['available'] = (
      bot_counts['count'] - bot_counts['busy'] - bot_counts['dead'] -
      bot_counts['quarantined'])

  return bot_counts
