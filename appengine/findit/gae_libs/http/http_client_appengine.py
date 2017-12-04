# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

from google.appengine.api import urlfetch
from google.appengine.api import urlfetch_errors

from gae_libs.http import auth_util
from libs.http.retry_http_client import RetryHttpClient

_GAE_RETRIABLE_EXCEPTIONS = [
    urlfetch_errors.DownloadError,
    urlfetch_errors.InternalTransientError,
]


class HttpClientAppengine(RetryHttpClient):
  """A http client for running on appengine."""

  def __init__(self,
               follow_redirects=True,
               interceptor=auth_util.AuthenticatingInterceptor(
                   retriable_exceptions=_GAE_RETRIABLE_EXCEPTIONS),
               *args,
               **kwargs):
    """Create a new client suitable for use within the app engine app."""
    super(HttpClientAppengine, self).__init__(
        interceptor=interceptor, *args, **kwargs)
    self.follow_redirects = follow_redirects

  def _ShouldLogError(self, status_code):
    if status_code == 200:
      return False
    if not self.no_error_logging_statuses:
      return True
    return status_code not in self.no_error_logging_statuses

  def _SendRequest(self, url, method, data, timeout, headers=None):
    headers = headers or {}

    result = urlfetch.fetch(
        url,
        payload=data,
        method=method,
        headers=headers,
        deadline=timeout,
        follow_redirects=self.follow_redirects,
        validate_certificate=True)

    if self._ShouldLogError(result.status_code):
      logging.error('Request to %s resulted in %d, headers:%s', url,
                    result.status_code, json.dumps(result.headers.items()))

    return result.status_code, result.content, result.headers

  def _Get(self, url, timeout, headers):
    return self._SendRequest(url, urlfetch.GET, None, timeout, headers)

  def _Post(self, url, data, timeout, headers):
    return self._SendRequest(url, urlfetch.POST, data, timeout, headers)

  def _Put(self, url, data, timeout, headers):
    return self._SendRequest(url, urlfetch.PUT, data, timeout, headers)
