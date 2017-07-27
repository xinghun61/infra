# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides functions to work with AppEngine endpoints"""

import httplib2
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(
  os.path.dirname(os.path.dirname(__file__)), 'third_party'))

import apiclient.discovery
import apiclient.errors
import oauth2client.appengine


AUTH_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'


def _authenticated_http(http, scope):
  credentials = oauth2client.appengine.AppAssertionCredentials(scope=scope)
  return credentials.authorize(http or httplib2.Http())


def build_client(api_name, api_version, discovery_url, http=None,
                 num_tries=5):
  """Creates HTTP endpoints client, retries connection errors.

  All requests to the endpoints will be authenticated with AppEngine app
  crendetials.

  Args:
    api_name: Name of the endpoints API.
    api_version: Version of the endpoints API.
    discovery_url: URL of the discovery endpoint. Should contain {api} and
        {apiVersion} placeholders, e.g. https://your-app.appspot.com/_ah/api/
        discovery/v1/apis/{api}/{apiVersion}/rest.
    http: Optional HTTP object. If not specified httplib2.Http() will be used.
    num_retries: Maximum number of retries to create client.

  Returns:
    Constructed client.
  """
  tries = 0
  while True:
    tries += 1
    try:
      return apiclient.discovery.build(
          api_name, api_version,
          discoveryServiceUrl=discovery_url,
          http=_authenticated_http(http, AUTH_SCOPE))
    except apiclient.errors.HttpError as e:
      if tries == num_tries:
        logging.exception(
            'apiclient.discovery.build() failed for %s too many times.',
            api_name)
        raise e

      delay = 2 ** (tries - 1)
      logging.warn(
          'apiclient.discovery.build() failed for %s: %s', api_name, e)
      logging.warn(
          'Retrying apiclient.discovery.build() in %s seconds.', delay)
      time.sleep(delay)

def retry_request(request, num_tries=5):
  """Retries provided endpoint request up to num_retries times."""
  tries = 0
  while True:
    tries += 1
    try:
      return request.execute()
    except apiclient.errors.HttpError as e:
      # This retries internal server (500, 503) and quota (403) errors.
      # TODO(sergiyb): Figure out if we still need to retry 403 errors. They
      # were used by codesite to fail on quota errors, but it is unclear whether
      # Monorail uses same logic or not.
      if tries == num_tries or e.resp.status not in [403, 500, 503]:
        raise
      time.sleep(2 ** (tries - 1))
