# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Yet another wrapper around Gerrit REST API."""

import base64
import json
import logging
import netrc
import os
import requests
import requests_cache
import stat
import sys
import time


LOGGER = logging.getLogger(__name__)


class GerritException(Exception):
  """Base class for exceptions raised by this module."""


class NetrcException(GerritException):
  """Netrc file is missing or incorrect."""


class UnexpectedResponseException(GerritException):
  """Gerrit returned something unexpected."""

  def __init__(self, http_code, body):
    super(UnexpectedResponseException, self).__init__()
    self.http_code = http_code
    self.body = body

  def __str__(self):
    return 'Unexpected response (HTTP %d): %s' % (self.http_code, self.body)


class Gerrit(object):  # pragma: no cover
  """Wrapper around single Gerrit host."""

  def __init__(self, host, netrc_path=None, throttle_delay_sec=0):
    auth = _load_netrc(netrc_path).authenticators(host)
    if not auth:
      raise GerritException('No record for %s in .netrc' % host)
    self._auth_header = 'Basic %s' % (
        base64.b64encode('%s:%s' % (auth[0], auth[2])))
    self._url_base = 'https://%s/a' % host
    self._throttle = throttle_delay_sec
    self._last_call_ts = None

  def _request(self, method, url, params=None, body=None):
    """Sends HTTP request to Gerrit.

    Args:
      method: HTTP method (e.g 'GET', 'POST', ...).
      url: URL of the endpoint, relative to host (e.g. '/accounts/self').
      params: dict with query parameters.
      body: optional request body, will be serialized to JSON.

    Returns:
      Tuple (response code, deserialized JSON response).
    """
    if not url.startswith('/'):
      raise ValueError('URL should start with /: %s' % url)
    full_url = '%s%s' % (self._url_base, url)

    # Wait to avoid Gerrit quota, don't wait if a response is in the cache.
    if self._throttle and not _is_response_cached(method, full_url):
      now = time.time()
      if self._last_call_ts and now - self._last_call_ts < self._throttle:
        time.sleep(self._throttle - (now - self._last_call_ts))
      self._last_call_ts = time.time()

    headers = {'Authorization': self._auth_header}
    if body is not None:
      headers['Content-Type'] = 'application/json;charset=UTF-8'

    LOGGER.debug('%s %s', method, full_url)
    response = requests.request(
        method=method,
        url=full_url,
        params=params,
        data=json.dumps(body) if body is not None else None,
        headers=headers)

    # Gerrit prepends )]}' to response.
    prefix = ')]}\'\n'
    body = response.text
    if body and body.startswith(prefix):
      body = json.loads(body[len(prefix):])

    return response.status_code, body

  def get_account(self, account_id):
    """Returns a dict describing a Gerrit account or None if no such account.

    Args:
      account_id: email, numeric account id, or 'self'.

    Returns:
      None if no such account, AccountInfo dict otherwise.
    """
    assert '/' not in account_id
    code, body = self._request('GET', '/accounts/%s' % account_id)
    if code == 200:
      return body
    if code == 404:
      return None
    raise UnexpectedResponseException(code, body)

  def add_group_members(self, group, members):
    """Adds a bunch of members to a group.

    Args:
      group: name of a group to add members to.
      members: iterable with emails of accounts to add to the group.

    Returns:
      None

    Raises:
      UnexpectedResponseException if call failed.
    """
    if '/' in group:
      raise ValueError('Invalid group name: %s' % group)
    code, body = self._request(
        method='POST',
        url='/groups/%s/members.add' % group,
        body={'members': list(members)})
    if code != 200:
      raise UnexpectedResponseException(code, body)


def _load_netrc(path=None):  # pragma: no cover
  """Loads netrc file with gerrit credentials.

  Args:
    path: path to .netrc or None to use default path.

  Returns:
    netrc.netrc instance.

  Raises:
    NetrcException.
  """
  if not path:
    # HOME might not be set on Windows.
    if 'HOME' not in os.environ:
      raise NetrcException('HOME environment variable is not set')
    path = os.path.join(
        os.environ['HOME'],
        '_netrc' if sys.platform.startswith('win') else '.netrc')
  try:
    return netrc.netrc(path)
  except IOError as exc:
    raise NetrcException('Could not read netrc file %s: %s' % (path, exc))
  except netrc.NetrcParseError as exc:
    netrc_stat = os.stat(exc.filename)
    if netrc_stat.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
      raise NetrcException(
          'netrc file %s cannot be used because its file permissions '
          'are insecure.  netrc file permissions should be 600.' % path)
    else:
      raise NetrcException(
          'Cannot use netrc file %s due to a parsing error: %s' % (path, exc))


def _is_response_cached(method, full_url):  # pragma: no cover
  """Returns True if response to GET request is in requests_cache."""
  if method != 'GET':
    return False
  try:
    cache = requests_cache.get_cache()
  except AttributeError:
    cache = None
  return cache.has_url(full_url) if cache else False
