# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import cStringIO
import json
import logging
import os
import sys

import google

from gae_libs.http.http_client_appengine import HttpClientAppengine
from waterfall import buildbot
from waterfall import swarming_util

# protobuf and GAE have package name conflict on 'google'.
# Add this to solve the conflict.
third_party = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')
sys.path.insert(0, third_party)
google.__path__.append(os.path.join(third_party, 'google'))
from logdog import annotations_pb2


_LOGDOG_ENDPOINT = 'https://luci-logdog.appspot.com/prpc/logdog.Logs/'
_LOGDOG_TAIL_ENDPOINT = '%s/Tail' % _LOGDOG_ENDPOINT
_LOGDOG_GET_ENDPOINT = '%s/Get' % _LOGDOG_ENDPOINT
_BASE_LOGDOG_REQUEST_PATH = 'bb/%s/%s/%s/+/%s'
_LOGDOG_RESPONSE_PREFIX = ')]}\'\n'


def _ProcessStringForLogDog(base_string):
  """Processes base string and replaces all special characters to '_'.

  Special characters are non alphanumeric nor ':_-.'.
  Reference: https://chromium.googlesource.com/chromium/tools/build/+/refs/
      heads/master/scripts/slave/logdog_bootstrap.py#349
  """
  new_string_list = []
  for c in base_string:
    if not c.isalnum() and not c in ':_-.':
      new_string_list.append('_')
    else:
      new_string_list.append(c)
  return ''.join(new_string_list)


def _GetResponseFromLogDog(url, path, http_client):
  """Gets response from Logdog.

  There are 2 types of requests:
    Tail for getting annotations proto.
    Get for getting desired log.
  """
  data = {
      'project': 'chromium',
      'path': path
  }
  data_json = json.dumps(data)

  headers = {
      'Content-Type': 'application/json',
      'Accept':'application/json'
  }
  status_code, response = http_client.Post(url, data_json, headers=headers)
  if status_code != 200 or not response:
    logging.error('Post request to LogDog failed')
    return None

  return response


def _GetResultJson(response):
  """Converts response from LogDog to json format."""
  try:
    # Removes extra _LOGDOG_RESPONSE_PREFIX so we can get json data.
    if response.startswith(_LOGDOG_RESPONSE_PREFIX):
      return json.loads(response[len(_LOGDOG_RESPONSE_PREFIX):])
    return json.loads(response)
  except Exception:
    logging.error("Could not load response from LogDog as json.")
    return None


def _GetAnnotationsProto(cq_build_step, http_client):
  """Gets annotations message for the build."""

  master_name = cq_build_step.master_name
  builder_name = cq_build_step.builder_name
  build_number = cq_build_step.build_number

  base_error_log = 'Error when load annotations protobuf: %s'

  path = _BASE_LOGDOG_REQUEST_PATH % (
      master_name, _ProcessStringForLogDog(builder_name), build_number,
      'annotations')
  response = _GetResponseFromLogDog(_LOGDOG_TAIL_ENDPOINT, path, http_client)
  if not response:
    return None

  response_json = _GetResultJson(response)
  if not response_json:
    return None

  # Gets data for proto. Data format as below:
  # {
  #    'logs': [
  #        {
  #            'datagram': {
  #                'data': (base64 encoded data)
  #            }
  #        }
  #     ]
  # }
  logs = response_json.get('logs')
  if not logs or not isinstance(logs, list):
    logging.error(base_error_log % 'Wrong format - "logs"')
    return None

  annotations_b64 = logs[-1].get('datagram', {}).get('data')
  if not annotations_b64:
    logging.error(base_error_log % 'Wrong format - "data"')
    return None

  # Gets proto.
  try:
    annotations = base64.b64decode(annotations_b64)
    step = annotations_pb2.Step()
    step.ParseFromString(annotations)
    return step
  except Exception:
    logging.error(base_error_log % 'could not get annotations.')
    return None


def _GetStepMetadataFromLogDog(cq_build_step, logdog_stream, http_client):
  """Gets step_metadata from LogDog in json format."""

  master_name = cq_build_step.master_name
  builder_name = cq_build_step.builder_name
  build_number = cq_build_step.build_number

  path = _BASE_LOGDOG_REQUEST_PATH % (
      master_name, _ProcessStringForLogDog(builder_name), build_number,
      logdog_stream)
  response = _GetResponseFromLogDog(_LOGDOG_GET_ENDPOINT, path, http_client)

  base_error_log = 'Error when fetch step_metadata log: %s'

  response_json = _GetResultJson(response)
  if not response_json:
    logging.error(base_error_log % 'cannot get json log.')
    return None

  # Gets data for step_metadata log. Data format as below:
  # {
  #    'logs': [
  #        {
  #            'text': {
  #                'lines': [
  #                   {
  #                       'value': 'line'
  #                   }
  #                ]
  #            }
  #        }
  #     ]
  # }
  logs = response_json.get('logs')
  if not logs or not isinstance(logs, list):
    logging.error(base_error_log % 'Wrong format - "logs"')
    return None

  sio = cStringIO.StringIO()
  for log in logs:
    for line in log.get('text', {}).get('lines', []):
      sio.write(line.get('value', ''))
  step_metadata = sio.getvalue()
  sio.close()

  try:
    return json.loads(step_metadata)
  except Exception:
    logging.error(base_error_log % 'step_metadata is broken.')
    return None


def _ProcessAnnotationsToGetStream(cq_build_step, step):
  for substep in step.substep:
    if substep.step.name != cq_build_step.step_name:
      continue

    for link in substep.step.other_links:
      if link.label.lower() == 'step_metadata':
        return link.logdog_stream.name

  return None


def _GetStepMetadata(cq_build_step, http_client):
  """Returns the step metadata."""
  # 1. Get annotations proto for the build.
  step = _GetAnnotationsProto(cq_build_step, http_client)
  if not step:
    return None

  # 2. Find the log stream info for this step's step_metadata.
  logdog_stream = _ProcessAnnotationsToGetStream(cq_build_step, step)

  # 3. Get the step_metadata.
  if not logdog_stream:
    return None

  return _GetStepMetadataFromLogDog(cq_build_step, logdog_stream, http_client)


def _GetMatchingWaterfallBuildStep(cq_build_step, http_client):
  """Returns the matching Waterfall build step of the given CQ one.

  Args:
    cq_build_step (BuildStep): A build step on Commit Queue.
    http_client (RetryHttpClient): A http client to send http requests.

  Returns:
      (master_name, builder_name, build_number, step_name, step_metadata)
    or
      None
  """
  no_matching_result = (None, None, None, None, None)

  # 0. Get step_metadata.
  step_metadata = _GetStepMetadata(cq_build_step, http_client)
  if not step_metadata:
    logging.error('Couldn\'t get step_metadata')
    return no_matching_result

  # 1. Map a cq trybot to the matching waterfall buildbot:
  # get master_name and builder_name.
  wf_master_name = step_metadata.get('waterfall_mastername')
  wf_builder_name = step_metadata.get('waterfall_buildername')
  if not wf_master_name or not wf_builder_name:
    # Either waterfall_mastername or waterfall_buildername doesn't exist.
    logging.info('%s/%s has no matching Waterfall buildbot',
                  cq_build_step.master_name, cq_build_step.builder_name)
    return no_matching_result  # No matching Waterfall buildbot.

  # 2. Get "name" of the CQ trybot step.

  # Name of the step in the tags of a Swarming task.
  # Can't use step name, as cq one is with "(with patch)" while waterfall one
  # without.
  name = step_metadata.get('canonical_step_name')
  # The OS in which the test runs on. The same test binary might run on two
  # different OS platforms.
  os_name = step_metadata.get('dimensions', {}).get('os')
  if not name or not os_name:
    logging.error('Couldn\'t find name/os')
    return no_matching_result  # No name of the step.

  # TODO: cache and throttle QPS to the same master.
  # 3. Retrieve latest completed build cycle on the buildbot.
  builds = buildbot.GetRecentCompletedBuilds(
      wf_master_name, wf_builder_name, http_client)
  if not builds:
    logging.error('Couldn\'t find latest builds.')
    return no_matching_result  # No name of the step.

  # 4. Check whether there is matching step.
  tasks = swarming_util.ListSwarmingTasksDataByTags(
      wf_master_name, wf_builder_name, builds[0], http_client,
      {'name': name, 'os': os_name})
  if tasks:  # One matching buildbot is found.
    wf_step_name = swarming_util.GetTagValue(
        tasks[0].get('tags', []), 'stepname')
    logging.info(
        '%s/%s/%s is mapped to %s/%s/%s',
        cq_build_step.master_name, cq_build_step.builder_name,
        cq_build_step.step_name, wf_master_name, wf_builder_name,
        wf_step_name)
    return (wf_master_name, wf_builder_name, builds[0], wf_step_name,
            step_metadata)

  return no_matching_result


def FindMatchingWaterfallStep(build_step, test_name):
  """Finds the matching Waterfall step and checks whether it is supported.

  Only Swarmed and gtest-based steps are supported at the moment.

  Args:
    build_step (BuildStep): A build step on Waterfall or Commit Queue. It
        will be updated with the matching Waterfall step and whether it is
        Swarmed and supported.
    test_name (str): The name of the test.
  """

  build_step.swarmed = False
  build_step.supported = False

  wf_master_name = None
  wf_builder_name = None
  wf_build_number = None
  wf_step_name = None

  http_client = HttpClientAppengine()

  wf_master_name, wf_builder_name, wf_build_number, wf_step_name, metadata = (
      _GetMatchingWaterfallBuildStep(build_step, http_client))

  build_step.wf_master_name = wf_master_name
  build_step.wf_builder_name = wf_builder_name
  build_step.wf_build_number = wf_build_number
  build_step.wf_step_name = wf_step_name

  if not build_step.has_matching_waterfall_step:
    return

  # Query Swarming for isolated data.
  build_step.swarmed = True if metadata.get('swarm_task_ids') else False

  if build_step.swarmed:
    # Retrieve a sample output from Isolate.
    task_id = metadata['swarm_task_ids'][0]
    output = swarming_util.GetIsolatedOutputForTask(task_id, http_client)
    if output:
      # Guess from the format.
      build_step.supported = (
          isinstance(output, dict) and
          isinstance(output.get('all_tests'), list) and
          test_name in output.get('all_tests', []) and
          isinstance(output.get('per_iteration_data'), list) and
          all(isinstance(i, dict) for i in output.get('per_iteration_data'))
      )
