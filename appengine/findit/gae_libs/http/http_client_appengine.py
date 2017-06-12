# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

from google.appengine.api import urlfetch

from gae_libs.http import auth_util
from libs.http.retry_http_client import RetryHttpClient


class HttpClientAppengine(RetryHttpClient):
  """A http client for running on appengine."""

  def __init__(self, follow_redirects=True,
               authenticator=auth_util.Authenticator(), *args, **kwargs):
    super(HttpClientAppengine, self).__init__(*args, **kwargs)
    self.follow_redirects = follow_redirects
    self.authenticator = authenticator

  def _ShouldLogError(self, status_code):
    if status_code == 200:
      return False
    if not self.no_error_logging_statuses:
      return True
    return status_code not in self.no_error_logging_statuses

  def _SendRequest(self, url, method, data, timeout, headers=None):
    # We wanted to validate certificate to avoid the man in the middle.
    headers = headers or {}

    # For google hosts, add Oauth2.0 token to authenticate the requests.
    headers.update(self.authenticator.GetHttpHeadersFor(url))

    result = urlfetch.fetch(
        url, payload=data, method=method, headers=headers, deadline=timeout,
        follow_redirects=self.follow_redirects, validate_certificate=True)

    if self._ShouldLogError(result.status_code):
      logging.error('Request to %s resulted in %d, headers:%s', url,
                    result.status_code, json.dumps(result.headers.items()))

    return result.status_code, result.content

  def _Get(self, url, timeout, headers):
    return self._SendRequest(url, urlfetch.GET, None, timeout, headers)

  def _Post(self, url, data, timeout, headers):
    return self._SendRequest(url, urlfetch.POST, data, timeout, headers)

  def _Put(self, url, data, timeout, headers):
    return self._SendRequest(url, urlfetch.PUT, data, timeout, headers)
