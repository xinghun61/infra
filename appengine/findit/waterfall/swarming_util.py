# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import logging
import zlib

from infra_api_clients import http_client_util
from infra_api_clients.swarming import swarming_util as i_swarming_util
from services import swarming


def GetSwarmingTaskFailureLog(outputs_ref, http_client):
  """Downloads failure log from isolated server."""
  isolated_data = i_swarming_util.GenerateIsolatedData(outputs_ref)
  return DownloadTestResults(isolated_data, http_client)


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
  json_data, error = i_swarming_util.GetSwarmingTaskResultById(
      swarming.SwarmingHost(), task_id, http_client)

  if error or not json_data:
    return None

  outputs_ref = json_data.get('outputs_ref')
  if not outputs_ref:
    return None

  output_json, error = GetSwarmingTaskFailureLog(outputs_ref, http_client)

  if error:
    return None
  return output_json
