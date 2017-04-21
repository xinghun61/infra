# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for interacting with LUCI's LogDog service."""

import base64
import cStringIO
import logging
import json
import os
import sys

from common import rpc_util

import google
# protobuf and GAE have package name conflict on 'google'.
# Add this to solve the conflict.
third_party = os.path.join(
    os.path.dirname(__file__), os.path.pardir, 'third_party')
sys.path.insert(0, third_party)
google.__path__.insert(0, os.path.join(third_party, 'google'))
from logdog import annotations_pb2


_BUILDBOT_LOGDOG_REQUEST_PATH = 'bb/%s/%s/%s/+/%s'
_SWARMING_LOGDOG_REQUEST_PATH = 'swarm/chromium-swarm.appspot.com/%s/+/%s'
_LOGDOG_ENDPOINT = 'https://luci-logdog.appspot.com/prpc/logdog.Logs'
_LOGDOG_TAIL_ENDPOINT = '%s/Tail' % _LOGDOG_ENDPOINT
_LOGDOG_GET_ENDPOINT = '%s/Get' % _LOGDOG_ENDPOINT


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

def _GetLogForPath(path, http_client):
  base_error_log = 'Error when fetch log: %s'
  data = {
      'project': 'chromium',
      'path': path
  }

  response_json = rpc_util.DownloadJsonData(
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


def _GetAnnotationsProtoForPath(path, http_client):
  base_error_log = 'Error when load annotations protobuf: %s'

  data = {
      'project': 'chromium',
      'path': path
  }

  response_json = rpc_util.DownloadJsonData(_LOGDOG_TAIL_ENDPOINT, data,
                                            http_client)
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


def GetAnnotationsProtoForBuild(master_name, builder_name, build_number,
                                http_client):
  """Gets annotations message for a buildbot build."""

  path = _BUILDBOT_LOGDOG_REQUEST_PATH % (
      master_name, _ProcessStringForLogDog(builder_name), build_number,
      'recipes/annotations')
  return _GetAnnotationsProtoForPath(path, http_client)


def GetAnnotationsProtoForSwarmedBuild(task_id, http_client):
  """Gets annotations message for a swarmed build."""
  path = _SWARMING_LOGDOG_REQUEST_PATH % (
      task_id, 'annotations')
  return _GetAnnotationsProtoForPath(path, http_client)


def GetStreamForStep(step_name, data, log_type='stdout'):
  for substep in data.substep:
    if substep.step.name != step_name:
      continue

    if log_type.lower() == 'stdout':
      # Gets stdout_stream.
      return substep.step.stdout_stream.name

    # Gets stream for step_metadata.
    for link in substep.step.other_links:
      if link.label.lower() == log_type:
        return link.logdog_stream.name

  return None


def GetLogForBuild(
      master_name, builder_name, build_number, logdog_stream, http_client):
  """Gets log from LogDog."""

  path = _BUILDBOT_LOGDOG_REQUEST_PATH % (
      master_name, _ProcessStringForLogDog(builder_name), build_number,
      logdog_stream)

  return _GetLogForPath(path, http_client)


def GetLogForSwarmedBuild(task_id, logdog_stream, http_client):
  """Gets log from LogDog."""

  path = _SWARMING_LOGDOG_REQUEST_PATH % (
      task_id, logdog_stream)
  return _GetLogForPath(path, http_client)
