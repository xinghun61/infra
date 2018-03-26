# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from dto import swarming_task_error
from dto.swarming_task_error import SwarmingTaskError
from infra_api_clients.isolate import isolate_util


def GetIsolatedOuptputFileToHashMap(digest, name_space, isolated_server,
                                    http_client):
  """Gets the mapping of all files and their hashes and other info.

  Args:
    digest(str): Hash to file for retrieve request.
    name_space(str): Name space info for retrieve request.
    isolated_server(str): Host to isolate server.
    http_client(RetryHttpClient): Http client to send the request.

  Returns:
    (dict): Mapping from file names to hashes.
  """
  content, error = isolate_util.FetchFileFromIsolatedServer(
      digest, name_space, isolated_server, http_client)
  if not content:
    return None, error

  file_hash_mapping = {}
  content_json = json.loads(content)
  if not content_json.get('files'):
    return None, SwarmingTaskError.GenerateError(
        swarming_task_error.NO_ISOLATED_FILES)
  for file_name, info in content_json['files'].iteritems():
    file_hash_mapping[file_name] = info.get('h')
  return file_hash_mapping, None


def DownloadFileFromIsolatedServer(isolate_output_ref, http_client, file_name):
  """Downloads file and returns the json object.

  The basic steps to get test results are:
  1. Use isolate_output_ref to get hash to file,
  2. Use hash from step 1 to get the file.

  Args:
    isolate_output_ref(dict): Outputs ref to get mapping from files to hashes.
    http_client(FinditHttoClient): Http client to send requests.
    file_name(str): name of the file to get from isolate.
  """
  # First POST request to get hash for the file.
  file_hash_mapping, error = GetIsolatedOuptputFileToHashMap(
      isolate_output_ref['digest'], isolate_output_ref['namespace'],
      isolate_output_ref['isolatedserver'], http_client)
  file_hash = file_hash_mapping.get(file_name) if file_hash_mapping else None
  if not file_hash:
    return None, error

  # Second POST request to get the redirect url for the file.
  return isolate_util.FetchFileFromIsolatedServer(
      file_hash, isolate_output_ref['namespace'],
      isolate_output_ref['isolatedserver'], http_client)
