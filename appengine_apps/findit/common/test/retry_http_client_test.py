# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
import unittest
import urllib

from common import retry_http_client


class DummyHttpClientImpl(retry_http_client.RetryHttpClient):
  def __init__(self, simulated_failures):
    super(DummyHttpClientImpl, self).__init__()
    self.requests = []
    self.request_count = 0
    self.simulated_failures = simulated_failures

  def _Get(self, url, timeout):
    self.requests.append({
        'time': time.time(),
        'url': url,
        'timeout': timeout,
    })
    self.request_count += 1
    if self.request_count > self.simulated_failures:
      return 200, 'success'
    else:
      return 404, 'failure'

class HttpClientTest(unittest.TestCase):
  def testRequestWithTimeout(self):
    url = 'http://test'
    timeout = 70
    dummy_http_client = DummyHttpClientImpl(0)
    status_code, content = dummy_http_client.Get(url, timeout=timeout)
    self.assertEquals(200, status_code)
    self.assertEquals('success', content)
    self.assertEquals(1, dummy_http_client.request_count)
    self.assertEquals(url, dummy_http_client.requests[0]['url'])
    self.assertEquals(timeout, dummy_http_client.requests[0]['timeout'])

  def testRequestWithParameters(self):
    url = 'http://test'
    params = {'a': 1, 'b': 'b&b'}
    dummy_http_client = DummyHttpClientImpl(0)
    status_code, content = dummy_http_client.Get(url, params=params)
    self.assertEquals(200, status_code)
    self.assertEquals('success', content)
    self.assertEquals(1, dummy_http_client.request_count)
    target_url, query_str = urllib.splitquery(
        dummy_http_client.requests[0]['url'])
    self.assertEquals(url, target_url)
    for query in query_str.split('&'):
      name, value = urllib.splitvalue(query)
      self.assertIn(name, params)
      self.assertEqual(urllib.quote(str(params[name])), value)

  def testRequestWithRetry(self):
    url = 'http://test'
    simulated_failures = 2

    def runWithInterval(retry_interval):
      dummy_http_client = DummyHttpClientImpl(simulated_failures)

      status_code, content = dummy_http_client.Get(
          url, retries=simulated_failures + 2, retry_interval=retry_interval)
      self.assertEquals(200, status_code)
      self.assertEquals('success', content)
      self.assertEquals(simulated_failures + 1, dummy_http_client.request_count)

      last_request_time = None
      count = 0
      for request in dummy_http_client.requests:
        count += 1

        self.assertEquals(url, request['url'])
        if last_request_time:
          if retry_interval > 1:
            expected_interval = retry_interval ** (count - 1)
          else:
            expected_interval = retry_interval
          self.assertLessEqual(expected_interval,
                               request['time'] - last_request_time)
        last_request_time = request['time']

    runWithInterval(0.1)
    runWithInterval(1.1)

  def testFailedRequest(self):
    url = 'http://test'
    dummy_http_client = DummyHttpClientImpl(5)
    status_code, content = dummy_http_client.Get(
        url, retries=2, retry_interval=0.1)
    self.assertEquals(2, dummy_http_client.request_count)
    self.assertEquals(404, status_code)
    self.assertEquals('failure', content)
