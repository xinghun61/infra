# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides API wrapper for FindIt"""

import httplib2

from endpoints import endpoints

from google.appengine.api import app_identity


DISCOVERY_URL = ('https://findit-for-me%s.appspot.com/_ah/api/discovery/v1/'
                 'apis/{api}/{apiVersion}/rest')


class FindItAPI(object):
  """A wrapper around the FindIt api."""
  def __init__(self):
    app_id = app_identity.get_application_id()
    if app_id.endswith('-staging'):
      discovery_url = DISCOVERY_URL % '-staging'
    else:
      discovery_url = DISCOVERY_URL % ''

    self.client = endpoints.build_client(
        'findit', 'v1', discovery_url, http=httplib2.Http(timeout=60))

  def flake(self, flake, flaky_runs):
    body = {}
    body['name'] = flake.name
    body['is_step'] = flake.is_step
    body['bug_id'] = flake.issue_id
    body['build_steps'] = []
    for flaky_run in flaky_runs:
      failure_run = flaky_run.failure_run.get()
      patchset_build_run = flaky_run.failure_run.parent().get()
      for occurrence in flaky_run.flakes:
        body['build_steps'].append({
          'master_name': patchset_build_run.master,
          'builder_name': patchset_build_run.builder,
          'build_number': failure_run.buildnumber,
          'step_name': occurrence.name
        })
    endpoints.retry_request(self.client.flake(body=body))
