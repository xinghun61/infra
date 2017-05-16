# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import copy
from collections import defaultdict
import hashlib
import json
import logging
import time
import urllib
from urlparse import urlparse
import zlib

from google.appengine.api.urlfetch_errors import DeadlineExceededError
from google.appengine.api.urlfetch_errors import DownloadError
from google.appengine.api.urlfetch_errors import ConnectionClosedError
from google.appengine.ext import ndb

from common.waterfall import buildbucket_client
from gae_libs.http import auth_util
from infra_api_clients import logdog_util
from model.wf_try_bot_cache import WfTryBotCache
from model.wf_step import WfStep
from waterfall import monitoring
from waterfall import waterfall_config
from waterfall.swarming_task_request import SwarmingTaskRequest


# Swarming task states.
STATES_RUNNING = ('RUNNING', 'PENDING')
STATE_COMPLETED = 'COMPLETED'
STATES_NOT_RUNNING = (
    'BOT_DIED', 'CANCELED', 'COMPLETED', 'EXPIRED', 'TIMED_OUT')


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


# Urlfetch error codes.
URLFETCH_DOWNLOAD_ERROR = 100
URLFETCH_DEADLINE_EXCEEDED_ERROR = 110
URLFETCH_CONNECTION_CLOSED_ERROR = 120
EXCEEDED_MAX_RETRIES_ERROR = 210


# Outputs_ref is None.
NO_TASK_OUTPUTS = 300


# Other/miscellaneous error codes.
UNKNOWN = 1000


# Swarming task exit codes.
ALL_TESTS_PASSED = 0
SOME_TESTS_FAILED = 1
TASK_FAILED = 2

# Swarming task exit code descriptions.
EXIT_CODE_DESCRIPTIONS = {
    ALL_TESTS_PASSED: 'All tests passed',
    SOME_TESTS_FAILED: 'Some tests failed',
    TASK_FAILED: 'Swarming task failed',
}


def _GetBackoffSeconds(retry_backoff, tries, maximum_retry_interval):
  """Returns how many seconds to wait before next retry.

  Params:
    retry_backoff (int): The base backoff in seconds.
    tries (int): Indicates how many tries have been done.
    maximum_retry_interval (int): The upper limit in seconds of how long to wait
      between retries.
  """
  return min(retry_backoff * (2 ** (tries - 1)), maximum_retry_interval)


def _OnConnectionFailed(url, exception_type):
  host = urlparse(url).hostname
  assert host
  monitoring.outgoing_http_errors.increment(
      {'host': host, 'exception': exception_type})


def _SendRequestToServer(url, http_client, post_data=None):
  """Sends GET/POST request to arbitrary url and returns response content.

  Because the Swarming and Isolated servers that _SendRequestToServer tries to
  contact are prone to outages, exceptions trying to reach them may occur thus
  this method should retry. We want to monitor and document these occurrences
  even if the request eventually succeeds after retrying, with the last error
  encountered being the one that is reported.

  Args:
    url (str): The url to send the request to.
    http_client (HttpClient): The httpclient object with which to make the
      server calls.
    post_data (dict): Data/params to send with the request, if any.

  Returns:
    content (dict), error (dict): The content from the server and the last error
    encountered trying to retrieve it.
  """
  headers = {'Authorization': 'Bearer ' + auth_util.GetAuthToken()}
  swarming_settings = waterfall_config.GetSwarmingSettings()
  should_retry = swarming_settings.get('should_retry_server')
  timeout_seconds = (
      swarming_settings.get('server_retry_timeout_hours') * 60 * 60)
  maximum_retry_interval = swarming_settings.get(
      'maximum_server_contact_retry_interval_seconds')
  deadline = time.time() + timeout_seconds
  retry_backoff = 60
  tries = 1
  error = None

  if post_data:
    post_data = json.dumps(post_data, sort_keys=True, separators=(',', ':'))
    headers['Content-Type'] = 'application/json; charset=UTF-8'
    headers['Content-Length'] = len(post_data)

  while True:
    try:
      if post_data:
        status_code, content = http_client.Post(url, post_data, headers=headers)
      else:
        status_code, content = http_client.Get(url, headers=headers)
    except ConnectionClosedError as e:
      error = {
          'code': URLFETCH_CONNECTION_CLOSED_ERROR,
          'message': e.message
      }
      _OnConnectionFailed(url, 'ConnectionClosedError')
    except DeadlineExceededError as e:
      error = {
          'code': URLFETCH_DEADLINE_EXCEEDED_ERROR,
          'message': e.message
      }
      _OnConnectionFailed(url, 'DeadlineExceededError')
    except DownloadError as e:
      error = {
          'code': URLFETCH_DOWNLOAD_ERROR,
          'message': e.message
      }
      _OnConnectionFailed(url, 'DownloadError')
    except Exception as e:  # pragma: no cover
      logging.error(
          'An unknown exception occurred that need to be monitored: %s',
          e.message)
      error = {
          'code': UNKNOWN,
          'message': e.message
      }
      _OnConnectionFailed(url, 'Unknown Exception')

    if error or status_code != 200:
      # The retry upon 50x (501 excluded) is automatically handled in the
      # underlying http_client.
      # By default, it retries 5 times with exponential backoff.
      error = error or {
          'code': EXCEEDED_MAX_RETRIES_ERROR,
          'message': 'Max retries exceeded trying to reach %s' % url
      }
      logging.error(error['message'])
    else:
      # Even if the call is successful, still return the last error encountered.
      return content, error

    if should_retry and time.time() < deadline:  # pragma: no cover
      # Wait, then retry if applicable.
      wait_time = _GetBackoffSeconds(
          retry_backoff, tries, maximum_retry_interval)
      logging.info('Retrying connection to %s in %d seconds', url, wait_time)
      time.sleep(wait_time)
      tries += 1
    else:
      if should_retry:
        # Indicate in the error that the retry timeout was reached.
        error['retry_timeout'] = True
      break

  logging.error('Failed to get an adequate response from %s. No data could be '
                'retrieved', url)
  return None, error


def GetSwarmingTaskRequest(task_id, http_client):
  """Returns an instance of SwarmingTaskRequest representing the given task."""
  swarming_server_host = waterfall_config.GetSwarmingSettings().get(
      'server_host')
  url = ('https://%s/_ah/api/swarming/v1/task/%s/request') % (
      swarming_server_host, task_id)
  content, error = _SendRequestToServer(url, http_client)

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

  url = 'https://%s/_ah/api/swarming/v1/tasks/new' % swarming_settings.get(
      'server_host')
  response_data, error = _SendRequestToServer(
      url, http_client, request.Serialize())

  if not error:
    return json.loads(response_data)['task_id'], None

  return None, error


def ListSwarmingTasksDataByTags(
    master_name, builder_name, build_number, http_client,
    additional_tag_filters=None):
  """Downloads tasks data from swarming server.

  Args:
    master_name(str): Value of the master tag.
    builder_name(str): Value of the buildername tag.
    build_number(int): Value of the buildnumber tag.
    http_client(RetryHttpClient): The http client to send HTTPs requests.
    additional_tag_filters(dict): More tag filters to be added.
  """
  base_url = ('https://%s/_ah/api/swarming/v1/tasks/'
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
    new_data, _ = _SendRequestToServer(url, http_client)

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


def _GenerateIsolatedData(outputs_ref):
  if not outputs_ref:
    return {}
  return {
      'digest': outputs_ref['isolated'],
      'namespace': outputs_ref['namespace'],
      'isolatedserver': outputs_ref['isolatedserver']
  }


def GetSwarmingTaskResultById(task_id, http_client):
  """Gets swarming result, checks state and returns outputs ref if needed."""
  base_url = ('https://%s/_ah/api/swarming/v1/task/%s/result') % (
      waterfall_config.GetSwarmingSettings().get('server_host'), task_id)
  json_data = {}

  data, error = _SendRequestToServer(base_url, http_client)

  if not error:
    json_data = json.loads(data)

  return json_data, error


def GetSwarmingTaskFailureLog(outputs_ref, http_client):
  """Downloads failure log from isolated server."""
  isolated_data = _GenerateIsolatedData(outputs_ref)
  return _DownloadTestResults(isolated_data, http_client)


def GetTagValue(tags, tag_name):
  """Returns the content for a specific tag."""
  tag_prefix = tag_name + ':'
  content = None
  for tag in tags:
    if tag.startswith(tag_prefix):
      content = tag[len(tag_prefix):]
      break
  return content


def GetIsolatedDataForFailedBuild(
    master_name, builder_name, build_number, failed_steps, http_client):
  """Checks failed step_names in swarming log for the build.

  Searches each failed step_name to identify swarming/non-swarming tests
  and keeps track of isolated data for each failed swarming steps.
  """
  data = ListSwarmingTasksDataByTags(
      master_name, builder_name, build_number, http_client)
  if not data:
    return False

  tag_name = 'stepname'
  build_isolated_data = defaultdict(list)
  for item in data:
    if item['failure'] and not item['internal_failure']:
      # Only retrieves test results from tasks which have failures and
      # the failure should not be internal infrastructure failure.
      swarming_step_name = GetTagValue(item['tags'], tag_name)
      if swarming_step_name in failed_steps and item.get('outputs_ref'):
        isolated_data = _GenerateIsolatedData(item['outputs_ref'])
        build_isolated_data[swarming_step_name].append(isolated_data)

  new_steps = []
  for step_name in build_isolated_data:
    failed_steps[step_name]['list_isolated_data'] = (
        build_isolated_data[step_name])

    # Create WfStep object for all the failed steps.
    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.isolated = True
    new_steps.append(step)

  ndb.put_multi(new_steps)
  return True


def GetIsolatedDataForStep(
    master_name, builder_name, build_number, step_name, http_client,
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
                                     http_client, {'stepname': step_name})
  if not data:
    return step_isolated_data

  for item in data:
    if only_failure:
      if item['failure'] and not item['internal_failure']:
        # Only retrieves test results from tasks which have failures and
        # the failure should not be internal infrastructure failure.
        isolated_data = _GenerateIsolatedData(item['outputs_ref'])
        step_isolated_data.append(isolated_data)
    else:
      isolated_data = _GenerateIsolatedData(item['outputs_ref'])
      step_isolated_data.append(isolated_data)

  return step_isolated_data


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
  url = '%s/_ah/api/isolateservice/v1/retrieve' % (
      isolated_data['isolatedserver'])

  return _SendRequestToServer(url, http_client, post_data)


def _GetOutputJsonHash(content):
  """Gets hash for output.json.

  Parses response content of the request using hash for .isolated file and
  returns the hash for output.json file.

  Args:
    content (string): Content returned by the POST request to isolated server
        for hash to output.json.
  """
  content_json = json.loads(content)
  content_string = zlib.decompress(base64.b64decode(content_json['content']))
  json_result = json.loads(content_string)
  return json_result.get('files', {}).get('output.json', {}).get('h')


def _RetrieveOutputJsonFile(output_json_content, http_client):
  """Downloads output.json file from isolated server or process it directly.

  If there is a url provided, send get request to that url to download log;
  else the log would be in content so use it directly.
  """
  json_content = json.loads(output_json_content)
  output_json_url = json_content.get('url')
  if output_json_url:
    get_content, _ = _SendRequestToServer(output_json_url, http_client)
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


def _DownloadTestResults(isolated_data, http_client):
  """Downloads the output.json file and returns the json object."""
  # First POST request to get hash for the output.json file.
  content, error = _FetchOutputJsonInfoFromIsolatedServer(
      isolated_data, http_client)
  if error:
    return None, error

  output_json_hash = _GetOutputJsonHash(content)
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
  return _RetrieveOutputJsonFile(output_json_content, http_client), None


def _MergeListsOfDicts(merged, shard):
  output = []
  for i in xrange(max(len(merged), len(shard))):
    merged_dict = merged[i] if i < len(merged) else {}
    shard_dict = shard[i] if i < len(shard) else {}
    output_dict = merged_dict.copy()
    output_dict.update(shard_dict)
    output.append(output_dict)
  return output


def _MergeSwarmingTestShards(shard_results):
  """Merges the shards into one.

  Args:
    shard_results (list): A list of dicts with individual shard results.

  Returns:
    A dict with the following form:
    {
      'all_tests':[
        'AllForms/FormStructureBrowserTest.DataDrivenHeuristics/0',
        'AllForms/FormStructureBrowserTest.DataDrivenHeuristics/1',
        'AllForms/FormStructureBrowserTest.DataDrivenHeuristics/10',
        ...
      ]
      'per_iteration_data':[
        {
          'AllForms/FormStructureBrowserTest.DataDrivenHeuristics/109': [
            {
              'elapsed_time_ms': 4719,
              'losless_snippet': true,
              'output_snippet': '[ RUN      ] run outputs\\n',
              'output_snippet_base64': 'WyBSVU4gICAgICBdIEFsbEZvcm1zL0Zvcm1T'
              'status': 'SUCCESS'
            }
          ],
        },
        ...
      ]
    }
  """
  merged_results = {
      'all_tests': set(),
      'per_iteration_data': []
  }
  for shard_result in shard_results:
    merged_results['all_tests'].update(shard_result.get('all_tests', []))
    merged_results['per_iteration_data'] = _MergeListsOfDicts(
        merged_results['per_iteration_data'],
        shard_result.get('per_iteration_data', []))
  merged_results['all_tests'] = sorted(merged_results['all_tests'])
  return merged_results


def RetrieveShardedTestResultsFromIsolatedServer(
    list_isolated_data, http_client):
  """Gets test results from isolated server and merge the results."""
  shard_results = []
  for isolated_data in list_isolated_data:
    output_json, _ = _DownloadTestResults(isolated_data, http_client)
    if not output_json:
      # TODO(lijeffrey): Report/handle error returned from _DownloadTestResults.
      return None
    shard_results.append(output_json)

  if len(list_isolated_data) == 1:
    return shard_results[0]
  return _MergeSwarmingTestShards(shard_results)


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

  swarming_server_host = waterfall_config.GetSwarmingSettings().get(
      'server_host')
  url = 'https://%s/_ah/api/swarming/v1/bots/count' % swarming_server_host

  dimension_list = ['%s:%s' % (k, v) for k, v in dimensions.iteritems()]
  dimension_url = '&dimensions='.join(dimension_list)
  # Url looks like 'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/bots
  # /count?dimensions=os:Windows-7-SP1&dimensions=cpu:x86-64'
  url = '%s?dimensions=%s' % (url, dimension_url)

  content, error = _SendRequestToServer(url, http_client)
  if error or not content:
    return {}

  content_data = json.loads(content)

  bot_counts = {
      k: int(content_data.get(k, 0)) for k in
      ('busy', 'count', 'dead', 'quarantined')
  }
  bot_counts['available'] = (bot_counts['count'] - bot_counts['busy'] -
                             bot_counts['dead'] - bot_counts['quarantined'])

  return bot_counts

def GetStepLog(try_job_id, full_step_name, http_client,
               log_type='stdout'):
  """Returns specific log of the specified step."""

  error, build = buildbucket_client.GetTryJobs([try_job_id])[0]
  if error:
    logging.exception('Error retrieving buildbucket build id: %s' %
                      try_job_id)
    return None

  # 1. Get log.
  data = logdog_util.GetStepLogForBuild(build.response, full_step_name,
                                        log_type, http_client)

  if log_type.lower() == 'step_metadata':  # pragma: no branch
    return json.loads(data) if data else None

  return data


def UpdateAnalysisResult(analysis_result, flaky_failures):
  """Updates WfAnalysis' result and result_analysis on flaky failures.

  If found flaky tests from swarming reruns, or flaky tests or compile from
  try jobs, updates WfAnalysis.
  """
  all_flaked = True
  for failure in analysis_result.get('failures', {}):
    step_name = failure.get('step_name')
    if step_name in flaky_failures:
      failure['flaky'] = True
      for test in failure.get('tests', []):
        if test.get('test_name') in flaky_failures[step_name]:
          test['flaky'] = True
        else:
          all_flaked = False
          failure['flaky'] = False
    else:
      # Checks all other steps to see if all failed steps/ tests are flaky.
      if not failure.get('flaky'):
        all_flaked = False

  return all_flaked


def GetCacheName(master, builder):
  hash_part = hashlib.sha256('%s:%s' % (master, builder)).hexdigest()
  return 'builder_' + hash_part


def GetBot(build):
  """Parses the swarming bot from the buildbucket response"""
  assert build
  if build.response:
    details = json.loads(
        build.response.get('result_details_json', '{}'))
    if details:
      return details.get('swarming', {}).get('task_result', {}).get('bot_id')
  return None


def GetBuilderCacheName(build):
  """Gets the named cache's name from the buildbucket response"""
  assert build
  parameters = json.loads(build.response.get('parameters_json', '{}'))
  if parameters:
    swarming_params = parameters.get('swarming', {}).get(
        'override_builder_cfg', {})
    for cache in swarming_params.get('caches', []):
      if cache.get('path') == 'builder':
        return cache.get('name')
  return None


def AssignWarmCacheHost(tryjob, cache_name, http_client):
  """Choose a host that already posesses the named cache requested.

  This applies if the job is being triggered on a swarming-backed builder and
  a cache name is specified.

  The strategy to select a host that has the cache is to try them in the order
  of how recently they used the cache and see if they are available.
  """
  if not tryjob.is_swarmbucket_build:
    return
  recent_bots = WfTryBotCache.Get(cache_name).recent_bots
  # TODO(robertocn): Optimize this selection strategy.
  for bot_id in recent_bots:
    request_dimensions = copy.deepcopy(tryjob.dimensions)
    request_dimensions['id'] = bot_id
    counts = GetSwarmingBotCounts(request_dimensions, http_client)
    if counts['available']:
      tryjob.dimensions = request_dimensions
      return
