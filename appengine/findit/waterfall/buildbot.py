# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import contextlib
import cStringIO
from datetime import datetime
import gzip
import io
import logging
import json
import os
import re
import sys
import urllib

import cloudstorage as gcs
import google

from waterfall.build_info import BuildInfo

# protobuf and GAE have package name conflict on 'google'.
# Add this to solve the conflict.
third_party = os.path.join(
    os.path.dirname(__file__), os.path.pardir, 'third_party')
sys.path.insert(0, third_party)
google.__path__.append(os.path.join(third_party, 'google'))
from logdog import annotations_pb2

_HOST_NAME_PATTERN = (
    r'https?://(?:build\.chromium\.org/p|uberchromegw\.corp\.google\.com/i)')

_MASTER_URL_PATTERN = re.compile(
    r'^%s/([^/]+)(?:/.*)?$' % _HOST_NAME_PATTERN)

_MILO_MASTER_URL_PATTERN = re.compile(
    r'^https?://luci-milo\.appspot\.com/buildbot/([^/]+)(?:/.*)?$')

_BUILD_URL_PATTERN = re.compile(
    r'^%s/([^/]+)/builders/([^/]+)/builds/([\d]+)(?:/.*)?$' %
    _HOST_NAME_PATTERN)

_MILO_BUILD_URL_PATTERN = re.compile(
    r'^https?://luci-milo\.appspot\.com/buildbot/([^/]+)/([^/]+)/([^/]+)'
    '(?:/.*)?$')

_MILO_ENDPOINT = 'https://luci-milo.appspot.com/prpc/milo.Buildbot'
_MILO_ENDPOINT_BUILD = '%s/GetBuildbotBuildJSON' % _MILO_ENDPOINT
_MILO_ENDPOINT_MASTER = '%s/GetCompressedMasterJSON' % _MILO_ENDPOINT

_STEP_URL_PATTERN = re.compile(
    r'^%s/([^/]+)/builders/([^/]+)/builds/([\d]+)/steps/([^/]+)(/.*)?$' %
    _HOST_NAME_PATTERN)

_COMMIT_POSITION_PATTERN = re.compile(
    r'refs/heads/master@{#(\d+)}$', re.IGNORECASE)

_RESPONSE_PREFIX = ')]}\'\n'

_LOGDOG_ENDPOINT = 'https://luci-logdog.appspot.com/prpc/logdog.Logs'
_LOGDOG_TAIL_ENDPOINT = '%s/Tail' % _LOGDOG_ENDPOINT
_LOGDOG_GET_ENDPOINT = '%s/Get' % _LOGDOG_ENDPOINT
_BASE_LOGDOG_REQUEST_PATH = 'bb/%s/%s/%s/+/%s'


# These values are buildbot constants used for Build and BuildStep.
# This line was copied from buildbot/master/buildbot/status/results.py.
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY, CANCELLED = range(7)


def _DownloadData(url, data, http_client):
  """Downloads data from rpc endpoints like Logdog or Milo."""

  headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }

  status_code, response = http_client.Post(
      url, json.dumps(data), headers=headers)
  if status_code != 200 or not response:
    logging.error('Post request to %s failed' % url)
    return None

  return response


def _GetResultJson(response):
  """Converts response from rpc endpoints to json format."""

  if response.startswith(_RESPONSE_PREFIX):
    # Removes extra _RESPONSE_PREFIX so we can get json data.
    return response[len(_RESPONSE_PREFIX):]
  return response

def DownloadJsonData(url, data, http_client):
  """Downloads data from rpc endpoints and converts response in json format."""
  response = _DownloadData(url, data, http_client)
  return _GetResultJson(response) if response else None

def _ProcessMiloData(response_json, master_name, builder_name, build_number=''):
  if not response_json:
    return None
  try:
    response_data = json.loads(response_json)
  except Exception:  # pragma: no cover
    logging.error('Failed to load json data for %s-%s-%s' % (
        master_name, builder_name, build_number))
    return None
  try:
    decoded_data = base64.b64decode(response_data.get('data'))
  except Exception:  # pragma: no cover
    logging.error('Failed to b64decode data for %s-%s-%s' % (
        master_name, builder_name, build_number))
    return None

  if build_number:
    # Build data is not compressed.
    return decoded_data

  try:
    with io.BytesIO(decoded_data) as compressed_file:
      with gzip.GzipFile(fileobj=compressed_file) as decompressed_file:
        data_json = decompressed_file.read()
  except Exception:  # pragma: no cover
    logging.error('Failed to decompress data for %s-%s-%s' % (
        master_name, builder_name, build_number))
    return None

  return data_json

def GetRecentCompletedBuilds(master_name, builder_name, http_client):
  """Returns a sorted list of recent completed builds for the given builder.

  Sorted by completed time, newer builds at beginning of the returned list.
  """
  data = {
    'name': master_name
  }
  response_json = DownloadJsonData(_MILO_ENDPOINT_MASTER, data, http_client)
  master_data_json = _ProcessMiloData(response_json, master_name, builder_name)
  if not master_data_json:
    return []

  master_data = json.loads(master_data_json)
  meta_data = master_data.get('builders', {}).get(builder_name, {})
  cached_builds = meta_data.get('cachedBuilds', [])
  current_builds = meta_data.get('currentBuilds', [])
  return sorted(set(cached_builds) - set(current_builds), reverse=True)


def GetMasterNameFromUrl(url):
  """Parses the given url and returns the master name."""
  if not url:
    return None

  match = _MASTER_URL_PATTERN.match(url) or _MILO_MASTER_URL_PATTERN.match(url)
  if not match:
    return None
  return match.group(1)


def ParseBuildUrl(url):
  """Parses the given build url.

  Return:
    (master_name, builder_name, build_number)
  """
  if not url:
    return None

  match = _BUILD_URL_PATTERN.match(url) or _MILO_BUILD_URL_PATTERN.match(url)
  if not match:
    return None

  master_name, builder_name, build_number = match.groups()
  builder_name = urllib.unquote(builder_name)
  return master_name, builder_name, int(build_number)


def ParseStepUrl(url):
  """Parses the given step url.

  Return:
    (master_name, builder_name, build_number, step_name)
  """
  if not url:
    return None

  match = _STEP_URL_PATTERN.match(url)
  if not match:
    return None

  master_name, builder_name, build_number, step_name, _ = match.groups()
  builder_name = urllib.unquote(builder_name)
  return master_name, builder_name, int(build_number), step_name


def CreateArchivedBuildUrl(master_name, builder_name, build_number):
  """Creates the url for the given build from archived build info."""
  builder_name = urllib.quote(builder_name)
  return ('https://chrome-build-extract.appspot.com/p/%s/builders/%s/builds/%s'
          '?json=1' % (master_name, builder_name, build_number))


def CreateBuildUrl(master_name, builder_name, build_number):
  """Creates the url for the given build."""
  builder_name = urllib.quote(builder_name)
  return 'https://luci-milo.appspot.com/buildbot/%s/%s/%s' % (
      master_name, builder_name, build_number)


def CreateGtestResultPath(master_name, builder_name, build_number, step_name):
  return ('/chrome-gtest-results/buildbot/%s/%s/%s/%s.json.gz') % (
      master_name, builder_name, build_number, step_name)


def GetBuildDataFromBuildMaster(
      master_name, builder_name, build_number, http_client):
  """Returns the json-format data of the build."""
  data = {
      'master': master_name,
      'builder': builder_name,
      'buildNum': build_number
  }
  response_json = DownloadJsonData(_MILO_ENDPOINT_BUILD, data, http_client)
  return _ProcessMiloData(
      response_json, master_name, builder_name, str(build_number))


def GetBuildDataFromArchive(master_name,
                            builder_name, build_number, http_client):
  """Returns the json-format data of the build from build archive."""
  status_code, data = http_client.Get(
      CreateArchivedBuildUrl(master_name, builder_name, build_number))
  if status_code != 200:
    return None
  else:
    return data


def GetGtestResultLog(
    master_name, builder_name, build_number, step_name):  # pragma: no cover
  """Returns the content of the gtest json results for the gtest-based step."""
  try:
    archived_log_path = CreateGtestResultPath(
        master_name, builder_name, build_number, step_name)
    with contextlib.closing(gcs.open(archived_log_path)) as gtest_result_file:
      with gzip.GzipFile(fileobj=gtest_result_file) as unzipped_gtest_file:
        return unzipped_gtest_file.read()
  except gcs.NotFoundError:
    return None


def GetStepResult(step_data_json):
  """Returns the result of a step."""
  result = step_data_json.get('results')
  if result is None and step_data_json.get('isFinished'):
    # Without parameter filter=0 in the http request to the buildbot json api,
    # the value of the result of a passed step won't be present.
    return SUCCESS

  while isinstance(result, list):
    result = result[0]
  return result


def GetBuildProperty(properties, property_name):
  """Returns the property value from the given build properties."""
  for item in properties:
    if item[0] == property_name:
      return item[1]
  return None


def GetBuildStartTime(build_data_json):
  times = build_data_json.get('times')
  if not times:
    return None
  return datetime.utcfromtimestamp(times[0])


def GetBuildEndTime(build_data_json):
  times = build_data_json.get('times')
  if not times or len(times) < 2 or not times[1]:
    return None
  return datetime.utcfromtimestamp(times[1])


def GetBuildResult(build_data_json):
  return build_data_json.get('results')


def _GetCommitPosition(commit_position_line):
  if commit_position_line:
    match = _COMMIT_POSITION_PATTERN.match(commit_position_line)
    if match:
      return int(match.group(1))
  return None


def ExtractBuildInfo(master_name, builder_name, build_number, build_data):
  """Extracts and returns build information as an instance of BuildInfo."""
  build_info = BuildInfo(master_name, builder_name, build_number)
  data_json = json.loads(build_data)
  chromium_revision = GetBuildProperty(
      data_json.get('properties', []), 'got_revision')
  commit_position_line = GetBuildProperty(
      data_json.get('properties', []), 'got_revision_cp')

  build_info.build_start_time = GetBuildStartTime(data_json)
  build_info.build_end_time = GetBuildEndTime(data_json)
  build_info.chromium_revision = chromium_revision
  build_info.commit_position = _GetCommitPosition(commit_position_line)
  build_info.completed = data_json.get('currentStep') is None
  build_info.result = GetBuildResult(data_json)

  changes = data_json.get('sourceStamp', {}).get('changes', [])
  for change in changes:
    if change['revision'] not in build_info.blame_list:
      build_info.blame_list.append(change['revision'])

  # Step categories:
  # 1. A step is passed if it is in SUCCESS or WARNINGS status.
  # 2. A step is failed if it is in FAILED status.
  # 3. A step is not passed if it is not in SUCCESS or WARNINGS status. This
  #    category includes steps in statuses: FAILED, SKIPPED, EXCEPTION, RETRY,
  #    CANCELLED, etc.
  steps = data_json.get('steps', [])
  for step_data in steps:
    step_name = step_data['name']

    if not step_data.get('isFinished', False):
      # Skip steps that haven't started yet or are still running.
      continue

    step_result = GetStepResult(step_data)
    if step_result not in (SUCCESS, WARNINGS):
      build_info.not_passed_steps.append(step_name)

    step_logs = step_data.get('logs')
    if step_logs and 'preamble' == step_logs[0][0]:
      # Skip a annotating step like "steps" or "slave_steps", which wraps other
      # steps. A failed annotated step like "content_browsertests" will make
      # the annotating step like "steps" fail too. Such annotating steps have a
      # log with name "preamble".
      continue

    if step_result in (SUCCESS, WARNINGS):
      build_info.passed_steps.append(step_name)
    elif step_result == FAILURE:
      build_info.failed_steps.append(step_name)

  return build_info


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


def _GetAnnotationsProto(master_name, builder_name, build_number, http_client):
  """Gets annotations message for the build."""

  base_error_log = 'Error when load annotations protobuf: %s'

  path = _BASE_LOGDOG_REQUEST_PATH % (
      master_name, _ProcessStringForLogDog(builder_name), build_number,
      'annotations')

  data = {
      'project': 'chromium',
      'path': path
  }

  response_json = DownloadJsonData(_LOGDOG_TAIL_ENDPOINT, data, http_client)
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
  logs = json.loads(response_json).get('logs')
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


def _GetLogFromLogDog(
      master_name, builder_name, build_number, logdog_stream, http_client):
  """Gets log from LogDog."""

  path = _BASE_LOGDOG_REQUEST_PATH % (
      master_name, _ProcessStringForLogDog(builder_name), build_number,
      logdog_stream)

  data = {
      'project': 'chromium',
      'path': path
  }

  base_error_log = 'Error when fetch log: %s'

  response_json = DownloadJsonData(
      _LOGDOG_GET_ENDPOINT, data, http_client)
  if not response_json:
    logging.error(base_error_log % 'cannot get json log.')
    return None

  # Gets data for log. Data format as below:
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
  logs = json.loads(response_json).get('logs')
  if not logs or not isinstance(logs, list):
    logging.error(base_error_log % 'Wrong format - "logs"')
    return None

  sio = cStringIO.StringIO()
  for log in logs:
    for line in log.get('text', {}).get('lines', []):
      sio.write('%s\n' % line.get('value', '').encode('utf-8'))
  data = sio.getvalue()
  sio.close()

  return data


def _ProcessAnnotationsToGetStream(step_name, step, log_type='stdout'):
  for substep in step.substep:
    if substep.step.name != step_name:
      continue

    if log_type.lower() == 'stdout':
      # Gets stdout_stream.
      return substep.step.stdout_stream.name

    if log_type.lower() == 'step_metadata':  # pragma: no branch
      # Gets stream for step_metadata.
      for link in substep.step.other_links:
        if link.label.lower() == 'step_metadata':
          return link.logdog_stream.name

  return None


def GetStepLog(master_name, builder_name, build_number,
               full_step_name, http_client, log_type='stdout'):
  """Returns sepcific log of the specified step."""

  # 1. Get annotations proto for the build.
  step = _GetAnnotationsProto(
      master_name, builder_name, build_number, http_client)
  if not step:
    return None

  # 2. Find the log stream info for this step's stdout log.
  logdog_stream = _ProcessAnnotationsToGetStream(full_step_name, step, log_type)

  # 3. Get the stdout log.
  if not logdog_stream:
    return None

  data = _GetLogFromLogDog(
      master_name, builder_name, build_number, logdog_stream, http_client)

  if log_type == 'step_metadata':
    return json.loads(data)

  return data