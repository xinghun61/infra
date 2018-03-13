# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from infra_api_clients.swarming import swarming_util as i_swarming_util
from services import isolate
from services import swarming


def GetSwarmingTaskFailureLog(outputs_ref, http_client):
  """Downloads failure log from isolated server."""
  isolated_data = i_swarming_util.GenerateIsolatedData(outputs_ref)
  file_content, error = isolate.DownloadFileFromIsolatedServer(
      isolated_data, http_client, 'output.json')
  return json.loads(file_content) if file_content else None, error


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
