# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides API wrapper for FindIt"""

import httplib2

from endpoints_client import endpoints


DISCOVERY_URL = ('https://findit-for-me%s.appspot.com/_ah/api/discovery/v1/'
                 'apis/{api}/{apiVersion}/rest')


class FindItAPI(object):
  """A wrapper around the FindIt api."""
  def __init__(self, use_staging=False):
    if use_staging:
      discovery_url = DISCOVERY_URL % '-staging'
    else:
      discovery_url = DISCOVERY_URL % ''

    self.client = endpoints.build_client(
        'findit', 'v1', discovery_url, http=httplib2.Http(timeout=60))

  def flake(self, name, is_step, issue_id, build_steps):
    """Analyze a flake on Commit Queue

    Sends a request to Findit to analyze a flake on commit queue. The flake
    can analyze a step or a test.

    Args:
      name: string name of the test or step to be analyzed
      is_step: if analyzing a step, this is set to True. Set to False otherwise.
      bug_id: the integer bug id associated with this test if any
      build_steps: A list of dictionaries where each dictionay contains
        the 'master_name', 'builder_name', 'build_number', and 'step_name' fields
        for each individual test run to analyze.
    """
    body = {}
    body['name'] = name
    body['is_step'] = is_step
    body['bug_id'] = issue_id
    body['build_steps'] = build_steps
    endpoints.retry_request(self.client.flake(body=body))

  def triggerFlakeSwarmingTask(
      self, master_name, builder_name, build_number, step_name, test_name,
      total_reruns=100):
    """Trigger a flake swarming rerun task with Findit

    Sends a request to Findit to schedule a test to be rerun. The response is
    is a dictionary. If the task has been scheduled and is waiting to run, the
    response contains 'queued' set to true. If the task is running, the response
    contains 'running' set to true. If the task has been completed, it contains
    other information: 'task_id' - the swarming task id of the triggered task,
    'completed', 'timeout_seconds', 'triggering_source' - what caused the rerun
    to be triggered, 'total_reruns', and 'fail_count' and 'pass_count' - number
    of times the test has failed and passed respectivly.
    """
    body = {}
    body['master_name'] = master_name
    body['builder_name'] = builder_name
    body['build_number'] = build_number
    body['step_name'] = step_name
    body['test_name'] = test_name
    body['total_reruns'] = total_reruns
    return endpoints.retry_request(self.client.flakeswarmingtask(body=body))

  def checkFlakeSwarmingTask(
      self, master_name, builder_name, build_number, step_name, test_name,
      total_reruns=100):
    """Check the status of a flake swarming rerun task

    Sends a request to Findit to retrieve the data of a scheduled task, whether
    it was scheduled externally via the API or through Findit. This will not
    trigger a new task but will return the data of the task if avaliable or report
    that the task is queued, running, failed, or supported, where supported indicates
    that the task has not been scheduled but it can be.
    """
    body = {}
    body['master_name'] = master_name
    body['builder_name'] = builder_name
    body['build_number'] = build_number
    body['step_name'] = step_name
    body['test_name'] = test_name
    body['total_reruns'] = total_reruns
    return endpoints.retry_request(self.client.flakeswarmingtaskdata(body=body))
