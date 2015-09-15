# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
import urllib


_NO_RETRY_CODE = [200, 302, 401, 403, 404, 501]


class RetryHttpClient(object):
  """Represents a http client to send http/https request to a remote server.

  Subclasses should implement abstract functions below.
  """
  def __init__(self, no_error_logging_statuses=None):
    # If an http request results in the given statuses, the subclasses should
    # not log an error.
    self.no_error_logging_statuses = no_error_logging_statuses

  def _Get(self, url, timeout_seconds, headers):  # pylint: disable=W0613, R0201
    """Sends the actual HTTP GET request.

    Returns:
      (status_code, content)
      status_code: the HTTP status code of the response.
      content: the content of the response.
    """
    raise NotImplementedError(
        '_Get() should be implemented in the child class')  # pragma: no cover

  def _Post(self, url, data, timeout_seconds,
            headers):  # pylint: disable=W0613, R0201
    """Sends the actual HTTP POST request.

    Returns:
      (status_code, content)
    """
    raise NotImplementedError(
        '_Post() should be implemented in the child class')  # pragma: no cover

  def GetBackoff(self, retry_backoff, tries):
    """Returns how many seconds to wait before next retry.

    When ``retry_backoff`` is more than 1, return an exponential backoff;
    otherwise we keep it the same.

    Params:
      retry_backoff (float): The base backoff in seconds.
      tries (int): Indicates how many tries have been done.
    """
    if retry_backoff > 1:
      return retry_backoff * (2 ** (tries - 1))
    else:
      return retry_backoff

  def _Retry(self, url, method, data=None, params=None, timeout_seconds=60,
               max_retries=5, retry_backoff=1.5, headers=None):
    if params and method == 'GET':
      url = '%s?%s' % (url, urllib.urlencode(params))

    tries = 0
    while tries < max_retries:
      tries += 1

      if method == 'GET':
        status_code, content = self._Get(url, timeout_seconds, headers)
      else:
        status_code, content = self._Post(url, data, timeout_seconds, headers)

      if status_code in _NO_RETRY_CODE:
        break
      else:
        time.sleep(self.GetBackoff(retry_backoff, tries))

    return status_code, content

  def Get(self, url, params=None, timeout_seconds=60,
          max_retries=5, retry_backoff=1.5, headers=None):
    """Sends a GET request to the url with the given parameters and headers.

    Params:
      url (str): The raw url to send request to. If ``params`` is specified, the
          url should not include any parameter in it.
      params (dict): A key-value dict of parameters to send in the request.
      timeout_seconds (int): The timeout for read/write of the http request.
      max_retries (int): The maxmium times of retries for the request when the
          returning http status code is not in 200, 302, 401, 403, 404, or 501.
      retry_backoff (float): The base backoff in seconds for retry.

    Returns:
      (status_code, content)
    """
    return self._Retry(url, 'GET', None, params, timeout_seconds,
                         max_retries, retry_backoff, headers)

  def Post(self, url, data, timeout_seconds=60,
           max_retries=5, retry_backoff=1.5, headers=None):
    """Sends a POST request to the url with the given parameters and headers.

    Params:
      url (str): The raw url to send request to. If ``params`` is specified, the
          url should not include any parameter in it.
      data (dict): The data to send for post request.
      timeout_seconds (int): The timeout for read/write of the http request.
      max_retries (int): The maxmium times of retries for the request when the
          returning http status code is not in 200, 302, 401, 403, 404, or 501.
      retry_backoff (float): The base backoff in seconds for retry.

    Returns:
      (status_code, content)
    """
    return self._Retry(url, 'POST', data, None, timeout_seconds,
                         max_retries, retry_backoff, headers)
