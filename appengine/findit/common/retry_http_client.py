# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
import urllib


class RetryHttpClient(object):
  """Represent a http client to send http/https request to a remote server."""

  def _Get(self, url, timeout):  # pylint: disable=W0613, R0201
    """Send the actual HTTP GET request.

    Returns:
      (status_code, content)
      state_code: the http status code of the response.
      content: the content of the response.
    """
    raise NotImplementedError()  # pragma: no cover

  def WaitForNextRetry(self, retry_interval, execution_count):
    if retry_interval > 1:
      time.sleep(retry_interval ** execution_count)
    else:
      time.sleep(retry_interval)

  def Get(self, url, params=None, timeout=60, retries=5, retry_interval=0.5):
    """Send a GET request to the url with the given parameters and headers.

    Returns:
      (status_code, content)
      state_code: the http status code of the response.
      content: the content of the response.
    """
    if params:
      url = '%s?%s' % (url, urllib.urlencode(params))

    count = 0
    while True:
      count += 1

      status_code, content = self._Get(url, timeout)

      if status_code == 200:
        break
      elif count >= retries:
        break
      else:
        self.WaitForNextRetry(retry_interval, count)

    return status_code, content
