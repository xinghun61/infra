# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock
import urlparse

from testing_utils import testing

from libs.http import retry_http_client
from libs.http import interceptor


class DummyHttpClient(retry_http_client.RetryHttpClient):
  """Returns mock response based on the url."""

  def __init__(self):
    super(DummyHttpClient,
          self).__init__(interceptor=interceptor.LoggingInterceptor())

  def _Get(self, url, timeout_seconds, headers=None):
    url = urlparse.urlparse(url)
    query = urlparse.parse_qs(url.query)
    status_string = query.get('status', ['404'])[0]  # parse_qs returns a list.
    content = query.get('content', [''])[0]  # Ditto.
    return int(status_string), content, {}

  def _Post(self, url, data, timeout_seconds, headers=None):
    raise NotImplementedError('Post not supported')


class InterceptorTest(testing.AppengineTestCase):

  @mock.patch.object(logging, 'info')
  def testNoException(self, mock_logging):
    client = DummyHttpClient()
    url = 'https://test.com/help?status=200&content=hello'
    status, content = client.Get(url)
    self.assertEqual(status, 200)
    self.assertEqual(content, 'hello')
    mock_logging.assert_called_once_with('got response status 200 for url %s',
                                         url)

  @mock.patch.object(logging, 'warning')
  def testWithException(self, mock_logging):
    client = DummyHttpClient()
    url = 'https://test.com/'
    with self.assertRaises(NotImplementedError):
      _status, _content = client.Post(url, {})
    mock_logging.assert_called_once_with('got exception %s("%s") for url %s',
                                         NotImplementedError,
                                         'Post not supported', url)

  @mock.patch.object(logging, 'exception')
  def testWithExceptionNoRetries(self, mock_logging):
    client = DummyHttpClient()
    url = 'https://test.com/'
    with self.assertRaises(NotImplementedError):
      _status, _content = client.Post(url, {}, max_retries=1)
    mock_logging.assert_called_once_with('got exception %s("%s") for url %s',
                                         NotImplementedError,
                                         'Post not supported', url)

  def testGetHost(self):
    self.assertEqual(
        'test.com',
        interceptor.HttpInterceptorBase.GetHost('https://test.com/long/path'))
    self.assertIsNone(interceptor.HttpInterceptorBase.GetHost(''))


  @mock.patch.object(logging, 'info')
  def testNoExceptionHttpError(self, mock_logging):
    client = DummyHttpClient()
    url = 'https://test.com/help?status=404&content=Not_Found'
    status, content = client.Get(url)
    self.assertEqual(status, 404)
    self.assertEqual(content, 'Not_Found')
    mock_logging.assert_called_once_with(
        'request to %s responded with %d http status and headers %s', url, 404,
        '{}')

