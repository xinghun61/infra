# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Make authenticated calls to gitiles."""


import base64
import logging
import httplib
import httplib2
import json
import urlparse
import netrc
import time


LOGGER = logging.getLogger(__name__)


# The default number of retries when a Gitiles error is encountered.
DEFAULT_RETRIES = 10


class GitilesError(Exception):
  pass


def call_gitiles(url, response_format, netrc_path=None, max_attempts=None):
  """Invokes Gitiles API and parses the JSON result.
  
  Given a gitiles URL, makes a ?format=json or ?format=text call and interprets
  the result. The 'json' format is parsed and returned as a python object, while
  'text' calls are automatically base64-decoded.

  url is the gitiles URL to call. It must not contain a query parameter.

  response_format is either 'json' or 'text'. This controls whether JSON or
                  textual output is desired. This usually depends on the query.

  netrc_path is the path to the netrc credentials used for authentication. If
             not specified, no authentication is used.

  max_attempts is the number of attempts to call gitiles before giving up on
              error. If None/zero, DEFAULT_RETRIES will be used.
  """
  assert response_format in ('json', 'text'), (
      'response must be either json or text')
  assert '?' not in url, 'url must not have a query parameter (?)'

  max_attempts = max_attempts or DEFAULT_RETRIES
  http = httplib2.Http()
  headers = {}
  if netrc_path:
    token = get_oauth_token_from_netrc(url, netrc_path)
    headers['Authorization'] = 'OAuth %s' % token
  attempt = 0
  while attempt < max_attempts:
    time.sleep(attempt)
    attempt += 1
    LOGGER.debug('GET %s', url)
    response, content = http.request(
        '%s?format=%s' % (url, response_format),
        'GET',
        headers=headers
    )
    if response.status != httplib.OK:
      LOGGER.warning('GET %s failed with HTTP code %d', url, response.status)
      if response.status < httplib.INTERNAL_SERVER_ERROR:
        break
      if attempt != max_attempts:
        LOGGER.warning('Retrying...')
      continue  # pragma: no cover (actually reached, see https://goo.gl/QA8B2U)
    if response_format == 'json':
      if not content.startswith(')]}\'\n'):
        raise GitilesError('Unexpected gitiles response: %s' % content)
      prefix_removed = content.split('\n', 1)[1]
      return json.loads(prefix_removed)
    elif response_format == 'text':
      return base64.b64decode(content)
    else:
      raise AssertionError()
  raise GitilesError('Failed to fetch %s: %s' % (url, content))


def get_oauth_token_from_netrc(url, netrc_path):
  """Looks up OAuth token for |url| in .netrc file at |netrc_path|."""
  parsed = urlparse.urlparse(url)
  auth = netrc.netrc(netrc_path).authenticators(parsed.hostname)
  if not auth:
    raise GitilesError(
        'netrc file %s is missing an entry for %s' % (
          netrc_path, parsed.hostname))
  return auth[2]


class Repository(object):
  def __init__(self, base_url, netrc_path=None, max_attempts=None):
    self._base_url = self._trim_slashes(base_url)
    self._netrc_path = netrc_path
    self._max_attempts = max_attempts

  @staticmethod
  def _trim_slashes(v):
    return v.strip('/')

  def __call__(self, ref='master', subpath=None):
    url = [self._base_url, '+', ref]
    if subpath:
      url.append(self._trim_slashes(subpath))
    url = '/'.join(url)
    return call_gitiles(
        url,
        'json',
        netrc_path=self._netrc_path,
        max_attempts=self._max_attempts)

  def ref_info(self, ref):
    return self(ref)
