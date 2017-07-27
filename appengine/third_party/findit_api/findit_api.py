# Copyright 2016 The Chromium Authors. All rights reserved.
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
