# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from apiclient.errors import HttpError
from endpoints_client import endpoints


class EndpointsTestCase(unittest.TestCase):
  def setUp(self):
    super(EndpointsTestCase, self).setUp()
    self.build = mock.Mock()
    self.cred = mock.Mock()
    self.http = mock.Mock()
    self.sleep = mock.Mock()
    self.patchers = [
        mock.patch('apiclient.discovery.build', self.build),
        mock.patch('httplib2.Http', self.http),
        mock.patch('oauth2client.appengine.AppAssertionCredentials', self.cred),
        mock.patch('time.sleep', self.sleep),
    ]
    for patcher in self.patchers:
      patcher.start()

  def tearDown(self):
    super(EndpointsTestCase, self).tearDown()
    for patcher in self.patchers:
      patcher.stop()

  def test_retries_errors_with_exponential_delay_when_building_client(self):
    self.build.side_effect = [
        HttpError(mock.Mock(), 'error'),
        HttpError(mock.Mock(), 'error'),
        HttpError(mock.Mock(), 'error'),
        'client'
    ]
    self.assertEquals(endpoints.build_client('foo', 'bar', 'baz'), 'client')
    self.sleep.assert_has_calls([mock.call(1), mock.call(2), mock.call(4)])

  def test_fails_to_build_client_after_5_errors(self):
    self.build.side_effect = [HttpError(mock.Mock(), 'error')] * 3
    with self.assertRaises(HttpError):
      endpoints.build_client('foo', 'bar', 'baz', num_tries=3)

  def test_uses_provided_http(self):
    self.cred.return_value.authorize = mock.Mock()
    endpoints.build_client('foo', 'bar', 'baz', http='myhttp')
    self.cred.return_value.authorize.assert_called_once_with('myhttp')

  def test_retries_supported_errors_on_requests_with_exponential_delay(self):
    request = mock.Mock()
    request.execute.side_effect = [
      HttpError(mock.Mock(status=500), 'error'),
      HttpError(mock.Mock(status=503), 'error'),
      HttpError(mock.Mock(status=403), 'error'),
      'response'
    ]
    self.assertEquals(endpoints.retry_request(request), 'response')
    self.sleep.assert_has_calls([mock.call(1), mock.call(2), mock.call(4)])

  def test_fails_requests_with_too_many_retries(self):
    request = mock.Mock()
    request.execute.side_effect = [HttpError(mock.Mock(status=500), 'err')] * 3
    with self.assertRaises(HttpError):
      endpoints.retry_request(request, num_tries=3)

  def test_fails_requests_with_unsupported_retry_errors(self):
    request = mock.Mock()
    request.execute.side_effect = [
        HttpError(mock.Mock(status=400), 'err'),
        'response'
    ]
    with self.assertRaises(HttpError):
      endpoints.retry_request(request)
