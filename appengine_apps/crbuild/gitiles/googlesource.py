# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base classes for Gerrit/Gitiles services hosted at googlesource.com."""

# TODO(pgervais): this file is not tested at all.

import httplib
import json
import logging
import urlparse

from google.appengine.api import app_identity
from google.appengine.api import urlfetch


AUTH_SCOPE = 'https://www.googleapis.com/auth/gerritcodereview'
RESPONSE_PREFIX = ")]}'"


class Error(Exception):  #pragma: no cover
  """Exception class for errors commuicating with a Google Source service."""
  def __init__(self, http_status, *args, **kwargs):
    super(Error, self).__init__(*args, **kwargs)
    self.http_status = http_status
    if self.http_status:
      self.message = '(%s) %s' % (self.http_status, self.message)


class AuthenticationError(Error):
  """Exception class for authentication errors with a Google Source service."""


class GoogleSourceServiceClient(object):  #pragma: no cover
  """Base class for GerritClient and GitilesClient hosted at googlesource.com.

  Requests are authenticated, blocking and not retried. If you need retries, use
  Push Tasks.
  """

  def __init__(self, hostname):
    assert hostname, 'hostname not set'
    self.hostname = hostname

  def _fetch(self, path, method='GET', headers=None, body=None,
             expect_status=(httplib.OK, httplib.NOT_FOUND)):
    """Makes a single authenticated blocking request using urlfetch.

    Raises
      AuthenticationError if authentication fails.
      Error if response status is not in expect_status tuple.

    Returns parsed json contents.
    """
    headers = headers or {}
    if not hasattr(expect_status, '__contains__'):
      expect_status = (expect_status,)

    auth_token, _ = app_identity.get_access_token(AUTH_SCOPE)
    payload = json.dumps(body) if body else None

    assert not path.startswith('/')
    url = urlparse.urljoin('https://' + self.hostname, 'a/' + path)
    request_headers = {
        'Content-Type': 'application/json',
        'Authorization': 'OAuth %s' % auth_token,
    }

    try:
      logging.debug('%s %s' % (method, url))
      response = urlfetch.fetch(url, payload=payload, method=method,
                                headers=request_headers, follow_redirects=False,
                                validate_certificate=True)
    except urlfetch.Error as err:
      raise Error(None, err.message)

    # Check if this is an authentication issue.
    auth_failed = response.status_code in (httplib.UNAUTHORIZED,
                                           httplib.FORBIDDEN)
    if auth_failed:
      reason = 'Authentication failed for %s' % self.hostname
      logging.error(reason)
      raise AuthenticationError(response.status_code, reason)

    if response.status_code not in expect_status:
      raise Error(response.status_code, response.content)

    if response.status_code == httplib.NOT_FOUND:
      return None
    content = response.content
    logging.info('Response: %s' % content)
    if not content.startswith(RESPONSE_PREFIX):
      msg = ('Unexpected response format. Expected prefix %s' %
             RESPONSE_PREFIX)
      raise Error(response.status_code, msg)
    content = content[len(RESPONSE_PREFIX):]
    return json.loads(content)
