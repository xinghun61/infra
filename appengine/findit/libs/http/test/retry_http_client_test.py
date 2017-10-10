# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock
import urllib

from testing_utils import testing

from libs.http import retry_http_client
from libs.http.interceptor import LoggingInterceptor


class RetryRuntimeErrorInterceptor(LoggingInterceptor):

  def OnException(self, request, exception, can_retry):
    _ = can_retry
    exception = super(RetryRuntimeErrorInterceptor, self).OnException(
        request, exception, can_retry)
    if type(exception) == RuntimeError:
      return None
    return exception


class DummyHttpClient(retry_http_client.RetryHttpClient):

  def __init__(self, simulated_failures, failure_status):
    super(DummyHttpClient, self).__init__()
    self.requests = []
    self.request_count = 0
    self.simulated_failures = simulated_failures
    self.failure_status = failure_status

  def GetBackoff(self, *_):
    return 0

  def _Get(self, url, timeout_seconds, headers=None):
    if 'runtimeerror' in url:
      raise RuntimeError(url)
    elif 'exception' in url:
      raise Exception(url)

    self.requests.append({
        'url': url,
        'timeout_seconds': timeout_seconds,
    })
    self.request_count += 1
    if self.request_count > self.simulated_failures:
      return 200, 'success - GET'
    else:
      return self.failure_status, 'failure - GET'

  def _Post(self, url, data, timeout_seconds, headers=None):
    self.requests.append({
        'url': url,
        'timeout_seconds': timeout_seconds,
    })
    self.request_count += 1
    if self.request_count > self.simulated_failures:
      return 200, 'success - POST'
    else:
      return self.failure_status, 'failure - POST'

  def _Put(self, url, data, timeout_seconds, headers=None):
    self.requests.append({
        'url': url,
        'timeout_seconds': timeout_seconds,
    })
    self.request_count += 1
    if self.request_count > self.simulated_failures:
      return 200, 'success - PUT'
    else:
      return self.failure_status, 'failure - PUT'


class HttpClientTest(testing.AppengineTestCase):

  def testRequestWithTimeout(self):
    url = 'http://test'
    timeout_seconds = 70
    dummy_http_client = DummyHttpClient(0, 404)
    status_code, content = dummy_http_client.Get(
        url, timeout_seconds=timeout_seconds)
    self.assertEquals(200, status_code)
    self.assertEquals('success - GET', content)
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
    self.assertEquals('success - GET', content)
    self.assertEquals(1, dummy_http_client.request_count)
    target_url, query_str = urllib.splitquery(
        dummy_http_client.requests[0]['url'])
    self.assertEquals(url, target_url)
    for query in query_str.split('&'):
      name, value = urllib.splitvalue(query)
      self.assertIn(name, params)
      self.assertEqual(urllib.quote(str(params[name])), value)

  def testGetBackoff(self):
    cases = [
        # (retry_backoff, tries, expected_backoff)
        (1, 1, 1),
        (1, 2, 1),
        (2, 1, 2),
        (2, 2, 4)
    ]
    for retry_backoff, tries, expected_backoff in cases:
      http_client = retry_http_client.RetryHttpClient()
      self.assertLessEqual(expected_backoff,
                           http_client.GetBackoff(retry_backoff, tries))

  def testRequestWithRetry(self):
    simulated_failures = 2

    self.mock_sleep()

    dummy_http_client = DummyHttpClient(simulated_failures, 503)

    status_code, content = dummy_http_client.Get(
        'http://test', max_retries=simulated_failures + 2, retry_backoff=1)
    self.assertEquals(200, status_code)
    self.assertEquals('success - GET', content)
    self.assertEquals(simulated_failures + 1, dummy_http_client.request_count)

  def testFailedRequest(self):
    dummy_http_client = DummyHttpClient(5, 503)
    status_code, content = dummy_http_client.Get(
        'http://test', max_retries=2, retry_backoff=0.01)
    self.assertEquals(2, dummy_http_client.request_count)
    self.assertEquals(503, status_code)
    self.assertEquals('failure - GET', content)

  def testFailedRequestWithNoInterceptor(self):
    dummy_http_client = DummyHttpClient(5, 503)
    dummy_http_client.interceptor = None
    status_code, content = dummy_http_client.Get(
        'http://test', max_retries=2, retry_backoff=0.01)
    self.assertEquals(1, dummy_http_client.request_count)
    self.assertEquals(503, status_code)
    self.assertEquals('failure - GET', content)

  def testNoRetryForSpecificHttpStatusCode(self):
    for expected_status_code in (302, 401, 403, 404, 501):
      dummy_http_client = DummyHttpClient(20000000, expected_status_code)

      status_code, content = dummy_http_client.Get(
          'http://test', max_retries=2000, retry_backoff=0.1)
      self.assertEquals(1, dummy_http_client.request_count)
      self.assertEquals(expected_status_code, status_code)
      self.assertEquals('failure - GET', content)

  def testPostFailure(self):
    dummy_http_client = DummyHttpClient(1, 404)
    status_code, content = dummy_http_client.Post('http://test', {'data': 0})
    self.assertEquals(404, status_code)
    self.assertEquals('failure - POST', content)

  def testPostSuccess(self):
    dummy_http_client = DummyHttpClient(0, 404)
    status_code, content = dummy_http_client.Post('http://test', {'data': 0})
    self.assertEquals(200, status_code)
    self.assertEquals('success - POST', content)

  def testNoRetryForSpecificHttpStatusCodePost(self):
    for expected_status_code in (302, 401, 403, 404, 501):
      dummy_http_client = DummyHttpClient(20000000, expected_status_code)

      status_code, content = dummy_http_client.Post('http://test', {'data': 0})
      self.assertEquals(1, dummy_http_client.request_count)
      self.assertEquals(expected_status_code, status_code)
      self.assertEquals('failure - POST', content)

  def testRetryForPost(self):
    dummy_http_client = DummyHttpClient(5, 503)
    status_code, content = dummy_http_client.Post(
        'http://test', {'data': 0}, max_retries=3)
    self.assertEquals(3, dummy_http_client.request_count)
    self.assertEquals(503, status_code)
    self.assertEquals('failure - POST', content)

  def testPutFailure(self):
    dummy_http_client = DummyHttpClient(1, 404)
    status_code, content = dummy_http_client.Put('http://test', {'data': 0})
    self.assertEquals(404, status_code)
    self.assertEquals('failure - PUT', content)

  def testPutSuccess(self):
    dummy_http_client = DummyHttpClient(0, 404)
    status_code, content = dummy_http_client.Put('http://test', {'data': 0})
    self.assertEquals(200, status_code)
    self.assertEquals('success - PUT', content)

  def testNoRetryForSpecificHttpStatusCodePut(self):
    for expected_status_code in (302, 401, 403, 404, 501):
      dummy_http_client = DummyHttpClient(20000000, expected_status_code)

      status_code, content = dummy_http_client.Put('http://test', {'data': 0})
      self.assertEquals(1, dummy_http_client.request_count)
      self.assertEquals(expected_status_code, status_code)
      self.assertEquals('failure - PUT', content)

  def testRetryForPut(self):
    dummy_http_client = DummyHttpClient(5, 503)
    status_code, content = dummy_http_client.Put(
        'http://test', {'data': 0}, max_retries=3)
    self.assertEquals(3, dummy_http_client.request_count)
    self.assertEquals(503, status_code)
    self.assertEquals('failure - PUT', content)

  @mock.patch.object(logging, 'warning')
  @mock.patch.object(logging, 'exception')
  def testRetriableException(self, mock_except, mock_warn):
    dummy_http_client = DummyHttpClient(0, 404)
    dummy_http_client.interceptor = RetryRuntimeErrorInterceptor()
    status_code, content = dummy_http_client.Get('http://runtimeerror')
    self.assertFalse(status_code)
    self.assertFalse(content)
    self.assertEqual(4, len(mock_warn.call_args_list))
    self.assertEqual(1, len(mock_except.call_args_list))

  @mock.patch.object(logging, 'warning')
  def testNonRetriableException(self, mock_logging):
    dummy_http_client = DummyHttpClient(0, 404)
    dummy_http_client.interceptor = RetryRuntimeErrorInterceptor()
    with self.assertRaises(Exception):
      _status_code, _content = dummy_http_client.Get('http://exception')
    self.assertEqual(1, len(mock_logging.call_args_list))

  def testNonRetriableExceptionWithInterceptor(self):
    dummy_http_client = DummyHttpClient(0, 404)
    dummy_http_client.interceptor = None
    with self.assertRaises(Exception):
      _status_code, _content = dummy_http_client.Get('http://exception')
