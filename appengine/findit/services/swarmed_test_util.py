# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions for operating on tests run in swarming."""

import json
import logging

from common.findit_http_client import FinditHttpClient
from infra_api_clients.swarming import swarming_util
from services import isolate
from services import swarming
from services import test_results

_FINDIT_HTTP_CLIENT = FinditHttpClient()


def GetOutputJsonByOutputsRef(outputs_ref, http_client):
  """Downloads failure log from isolated server."""
  isolated_data = swarming_util.GenerateIsolatedData(outputs_ref)
  file_content, error = isolate.DownloadFileFromIsolatedServer(
      isolated_data, http_client, 'output.json')
  return json.loads(file_content) if file_content else None, error


def GetTestResultForSwarmingTask(task_id, http_client):
  """Get isolated output for a swarming task based on it's id."""
  task_result_data, error = swarming_util.GetSwarmingTaskResultById(
      swarming.SwarmingHost(), task_id, http_client)

  if error or not task_result_data:
    return None

  outputs_ref = task_result_data.get('outputs_ref')
  if not outputs_ref:
    return None

  test_result_log, error = GetOutputJsonByOutputsRef(outputs_ref, http_client)

  if error:
    return None
  return test_result_log


def GetTestLocation(task_id, test_name):
  """Gets the filepath and line number of a test from swarming.

  Args:
    task_id (str): The swarming task id to query.
    test_name (str): The name of the test whose location to return.

  Returns:
    (TestLocation): The file path and line number of the test, or None
        if the test location was not be retrieved.

  """
  test_results_log = GetTestResultForSwarmingTask(task_id, _FINDIT_HTTP_CLIENT)
  test_location, error = test_results.GetTestLocation(test_results_log,
                                                      test_name)
  if error:
    logging.error('Failed to get test location for task %s: %s', task_id, error)
    return None
  return test_location


def IsTestEnabled(test_name, task_id):
  """Returns True if the test is enabled, False otherwise."""
  # Get the isolated outputs from the test that was just run.
  test_results_log = GetTestResultForSwarmingTask(task_id, _FINDIT_HTTP_CLIENT)
  return test_results.IsTestEnabled(test_results_log, test_name)


def RetrieveShardedTestResultsFromIsolatedServer(list_isolated_data,
                                                 http_client):
  """Gets test results from isolated server and merge the results."""
  shard_results = []
  for isolated_data in list_isolated_data:
    test_result_log, _ = isolate.DownloadFileFromIsolatedServer(
        isolated_data, http_client, 'output.json')
    if not test_result_log:
      return None
    shard_results.append(json.loads(test_result_log))

  if not shard_results:
    return []

  return test_results.GetMergedTestResults(shard_results)
