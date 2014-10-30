# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.api import urlfetch

from appengine_module.findit.common.retry_http_client import RetryHttpClient


class HttpClientAppengine(RetryHttpClient):  # pragma: no cover
  """A http client for running on appengine."""

  def _Get(self, url, timeout):
    # We wanted to validate certificate to avoid the man in the middle.
    result = urlfetch.fetch(url, deadline=timeout, validate_certificate=True)

    if result.status_code != 200:
      logging.error('Request to %s failed with code=%d: %s',
                    url, result.status_code, result.content)

    return result.status_code, result.content
