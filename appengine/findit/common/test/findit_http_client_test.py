# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock
import urlparse

from testing_utils import testing

from libs.http import retry_http_client

from common import monitoring
from common import findit_http_client


class DummyHttpClient(findit_http_client.FinditHttpClient):
  """Returns mock response based on the url."""

  def _Get(self, url, _timeout_seconds, headers=None):
    url = urlparse.urlparse(url)
    query = urlparse.parse_qs(url.query)
    status_string = query.get('status', ['404'])[0]  # parse_qs returns a list.
    content = query.get('content', [''])[0]  # Ditto.
    return int(status_string), content

  def _Post(self, url, data, timeout_seconds, headers=None):
    raise NotImplementedError('Post not supported')


class HttpClientMetricsInterceptorTest(testing.AppengineTestCase):

  @mock.patch.object(monitoring, 'outgoing_http_errors')
  @mock.patch.object(monitoring, 'outgoing_http_statuses')
  def testNoException(self, mock_status_metric, mock_error_metric):
    client = DummyHttpClient()
    url = 'https://test.com/help?status=200&content=hello'
    status, content = client.Get(url)
    self.assertEqual(200, status)
    self.assertEqual('hello', content)
    mock_status_metric.increment.assert_called_once_with({
        'host': 'test.com',
        'status_code': '200',
    })
    mock_error_metric.increment.assert_not_called()

  @mock.patch.object(monitoring, 'outgoing_http_errors')
  @mock.patch.object(monitoring, 'outgoing_http_statuses')
  def testWithException(self, mock_status_metric, mock_error_metric):
    client = DummyHttpClient()
    url = 'https://test.com/'
    with self.assertRaises(NotImplementedError):
      _status, _content = client.Post(url, {})
    mock_error_metric.increment.assert_called_once_with({
        'host': 'test.com',
        'exception': 'exceptions.NotImplementedError',
    })
    mock_status_metric.increment.assert_not_called()
