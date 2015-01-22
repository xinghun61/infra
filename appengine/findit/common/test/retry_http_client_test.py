# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import urllib

from common import retry_http_client


class DummyHttpClient(retry_http_client.RetryHttpClient):
  def __init__(self, simulated_failures, failure_status):
    super(DummyHttpClient, self).__init__()
    self.requests = []
    self.request_count = 0
    self.simulated_failures = simulated_failures
    self.failure_status = failure_status

  def _Get(self, url, timeout_seconds):
    self.requests.append({
        'url': url,
        'timeout_seconds': timeout_seconds,
    })
    self.request_count += 1
    if self.request_count > self.simulated_failures:
      return 200, 'success'
    else:
      return self.failure_status, 'failure'

class HttpClientTest(unittest.TestCase):
  def testRequestWithTimeout(self):
    url = 'http://test'
    timeout_seconds = 70
    dummy_http_client = DummyHttpClient(0, 404)
    status_code, content = dummy_http_client.Get(
        url, timeout_seconds=timeout_seconds)
    self.assertEquals(200, status_code)
    self.assertEquals('success', content)
    self.assertEquals(1, dummy_http_client.request_count)
    self.assertEquals(url, dummy_http_client.requests[0]['url'])
    self.assertEquals(timeout_seconds,
                      dummy_http_client.requests[0]['timeout_seconds'])

  def testRequestWithParameters(self):
    url = 'http://test'
    params = {'a': 1, 'b': 'b&b'}
    dummy_http_client = DummyHttpClient(0, 404)
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

    original_time_sleep = retry_http_client.time.sleep
    try:
      def RunWithInterval(retry_interval):
        sleep_time = []
        def DummyTimeSleep(seconds):
          sleep_time.append(seconds)
        retry_http_client.time.sleep = DummyTimeSleep

        dummy_http_client = DummyHttpClient(simulated_failures, 503)

        status_code, content = dummy_http_client.Get(
            url, max_retries=simulated_failures + 2,
            retry_interval=retry_interval)
        self.assertEquals(200, status_code)
        self.assertEquals('success', content)
        self.assertEquals(simulated_failures + 1,
                          dummy_http_client.request_count)

        count = 0
        for request in dummy_http_client.requests:
          count += 1

          self.assertEquals(url, request['url'])
          if count > 1:
            if retry_interval > 1:
              expected_interval = retry_interval ** (count - 1)
            else:
              expected_interval = retry_interval
            self.assertLessEqual(expected_interval, sleep_time[count - 2])

      RunWithInterval(0.1)
      RunWithInterval(1.1)
    finally:
      retry_http_client.time.sleep = original_time_sleep

  def testFailedRequest(self):
    url = 'http://test'
    dummy_http_client = DummyHttpClient(5, 503)
    status_code, content = dummy_http_client.Get(
        url, max_retries=2, retry_interval=0.01)
    self.assertEquals(2, dummy_http_client.request_count)
    self.assertEquals(503, status_code)
    self.assertEquals('failure', content)

  def testNoRetryForSpecificHttpStatusCode(self):
    url = 'http://test'
    for expected_status_code in (302, 401, 403, 404, 501):
      dummy_http_client = DummyHttpClient(20000000, expected_status_code)

      status_code, content = dummy_http_client.Get(
          url, max_retries=2000, retry_interval=0.1)
      self.assertEquals(1, dummy_http_client.request_count)
      self.assertEquals(expected_status_code, status_code)
      self.assertEquals('failure', content)
