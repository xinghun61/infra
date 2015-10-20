# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
from collections import defaultdict
import json
import urllib
import zlib

from google.appengine.ext import ndb

from model.wf_step import WfStep


def _SendRequestToServer(url, http_client, auth_token, post_data=None):
  """Sends GET/POST request to arbitrary url and returns response content."""
  headers = {'Authorization': 'Bearer ' + auth_token}
  if post_data:
    post_data = json.dumps(post_data, sort_keys=True, separators=(',', ':'))
    headers['Content-Type'] = 'application/json; charset=UTF-8'
    headers['Content-Length'] = len(post_data)
    status_code, content = http_client.Post(url, post_data, headers=headers)
  else:
    status_code, content = http_client.Get(url, headers=headers)

  if status_code != 200:
    # The retry upon 50x (501 excluded) is automatically handled in the
    # underlying http_client.
    # By default, it retries 5 times with exponential backoff.
    return None
  return content


def _DownloadSwarmingTasksData(
    master_name, builder_name, build_number, http_client, auth_token,
    step_name=None):
  """Downloads tasks data from swarming server."""
  base_url = ('https://chromium-swarm.appspot.com/_ah/api/swarming/v1/tasks/'
              'list?tags=%s&tags=%s&tags=%s') % (
                  urllib.quote('master:%s' % master_name),
                  urllib.quote('buildername:%s' % builder_name),
                  urllib.quote('buildnumber:%d' % build_number))
  if step_name:
    base_url += '&tags=%s' % urllib.quote('stepname:%s' % step_name)


  items = []
  cursor = None

  while True:
    if not cursor:
      url = base_url
    else:
      url = base_url + '&cursor=%s' % urllib.quote(cursor)
    new_data = _SendRequestToServer(url, http_client, auth_token)
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


def GetIsolatedDataForFailedBuild(
    master_name, builder_name, build_number, failed_steps,
    http_client, auth_token):
  """Checks failed step_names in swarming log for the build.

  Searches each failed step_name to identify swarming/non-swarming tests
  and keeps track of isolated data for each failed swarming steps.
  """
  data = _DownloadSwarmingTasksData(
      master_name, builder_name, build_number, http_client, auth_token)
  if not data:
    return False

  step_name_prefix = 'stepname:'
  build_isolated_data = defaultdict(list)
  for item in data:
    if item['failure'] and not item['internal_failure']:
      # Only retrieves test results from tasks which have failures and
      # the failure should not be internal infrastructure failure.
      for tag in item['tags']:  # pragma: no cover
        if tag.startswith(step_name_prefix):
          swarming_step_name = tag[len(step_name_prefix):]
          break
      if swarming_step_name in failed_steps:
        isolated_data = {
            'digest': item['outputs_ref']['isolated'],
            'namespace': item['outputs_ref']['namespace'],
            'isolatedserver': item['outputs_ref']['isolatedserver']
        }
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
    master_name, builder_name, build_number, step_name,
    http_client, auth_token):
  """Returns the isolated data for a specific step."""
  step_isolated_data = []
  data = _DownloadSwarmingTasksData(master_name, builder_name, build_number,
                                    http_client, auth_token, step_name)
  if not data:
    return step_isolated_data

  for item in data:
    if item['failure'] and not item['internal_failure']:
      # Only retrieves test results from tasks which have failures and
      # the failure should not be internal infrastructure failure.
      isolated_data = {
          'digest': item['outputs_ref']['isolated'],
          'namespace': item['outputs_ref']['namespace'],
          'isolatedserver': item['outputs_ref']['isolatedserver']
      }
      step_isolated_data.append(isolated_data)

  return step_isolated_data


def _FetchOutputJsonInfoFromIsolatedServer(
    isolated_data, http_client, auth_token):
  """Sends POST request to isolated server and returns response content.

  This function is used for fetching
    1. hash code for the output.json file,
    2. the redirect url.
  """
  post_data = {
      'digest': isolated_data['digest'],
      'namespace': isolated_data['namespace']
  }
  url = '%s/_ah/api/isolateservice/v2/retrieve' %(
      isolated_data['isolatedserver'])
  content = _SendRequestToServer(url, http_client, auth_token, post_data)
  return content


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


def _DownloadOutputJsonFileFromTheUrlInResponse(
    output_json_content, http_client, auth_token):
  """Downloads output.json file from isolated server."""
  output_json_url = json.loads(output_json_content).get('url')
  get_content = _SendRequestToServer(output_json_url, http_client, auth_token)
  return json.loads(zlib.decompress(get_content)) if get_content else None


def _DownloadTestResults(isolated_data, http_client, auth_token):
  """Downloads the output.json file and returns the json object."""
  # First POST request to get hash for the output.json file.
  content = _FetchOutputJsonInfoFromIsolatedServer(
      isolated_data, http_client, auth_token)
  if not content:
    return None
  output_json_hash = _GetOutputJsonHash(content)
  if not output_json_hash:
    return None

  # Second POST request to get the redirect url for the output.json file.
  data_for_output_json = {
    'digest': output_json_hash,
    'namespace': isolated_data['namespace'],
    'isolatedserver': isolated_data['isolatedserver']
  }
  output_json_content = _FetchOutputJsonInfoFromIsolatedServer(
      data_for_output_json, http_client, auth_token)
  if not output_json_content:
    return None

  # GET Request to get output.json file.
  return _DownloadOutputJsonFileFromTheUrlInResponse(
      output_json_content, http_client, auth_token)


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
    merged_results['per_iteration_data'] =  _MergeListsOfDicts(
            merged_results['per_iteration_data'],
            shard_result.get('per_iteration_data', []))
  merged_results['all_tests'] = sorted(merged_results['all_tests'])
  return merged_results


def RetrieveShardedTestResultsFromIsolatedServer(
    list_isolated_data, http_client, auth_token):
  """Gets test results from isolated server and merge the results."""
  shard_results = []
  for isolated_data in list_isolated_data:
    output_json = _DownloadTestResults(isolated_data, http_client, auth_token)
    if not output_json:
      return None
    shard_results.append(output_json)

  if len(list_isolated_data) == 1:
    return shard_results[0]
  return _MergeSwarmingTestShards(shard_results)
