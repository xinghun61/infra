# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import socket
import time
import unittest

import infra_libs
from infra_libs.ts_mon.common import http_metrics
from infra_libs import httplib2_utils
from infra_libs import ts_mon

import httplib2
import mock
import oauth2client.client


DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')


class LoadJsonCredentialsTest(unittest.TestCase):
  # Everything's good, should not raise any exceptions.
  def test_valid_credentials(self):
    creds = httplib2_utils.load_service_account_credentials(
      'valid_creds.json',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds, dict)
    self.assertIn('type', creds)
    self.assertIn('client_email', creds)
    self.assertIn('private_key', creds)

  # File exists but issue with the content: raises AuthError.
  def test_missing_type(self):
    with self.assertRaises(infra_libs.AuthError):
      httplib2_utils.load_service_account_credentials(
        'creds_missing_type.json',
        service_accounts_creds_root=DATA_DIR)

  def test_wrong_type(self):
    with self.assertRaises(infra_libs.AuthError):
      httplib2_utils.load_service_account_credentials(
        'creds_wrong_type.json',
        service_accounts_creds_root=DATA_DIR)

  def test_missing_client_email(self):
    with self.assertRaises(infra_libs.AuthError):
      httplib2_utils.load_service_account_credentials(
        'creds_missing_client_email.json',
        service_accounts_creds_root=DATA_DIR)

  def test_missing_private_key(self):
    with self.assertRaises(infra_libs.AuthError):
      httplib2_utils.load_service_account_credentials(
        'creds_missing_private_key.json',
        service_accounts_creds_root=DATA_DIR)

  def test_malformed(self):
    with self.assertRaises(infra_libs.AuthError):
      httplib2_utils.load_service_account_credentials(
        'creds_malformed.json',
        service_accounts_creds_root=DATA_DIR)

  # Problem with the file itself
  def test_file_not_found(self):
    with self.assertRaises(IOError):
      httplib2_utils.load_service_account_credentials(
        'this_file_should_not_exist.json',
        service_accounts_creds_root=DATA_DIR)


class GetSignedJwtAssertionCredentialsTest(unittest.TestCase):
  def test_valid_credentials(self):
    creds = infra_libs.get_signed_jwt_assertion_credentials(
      'valid_creds.json',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds,
                          oauth2client.client.SignedJwtAssertionCredentials)
    # A default scope must be provided, we don't care which one
    self.assertTrue(creds.scope)

  def test_valid_credentials_with_scope_as_string(self):
    creds = infra_libs.get_signed_jwt_assertion_credentials(
      'valid_creds.json',
      scope='repo',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds,
                          oauth2client.client.SignedJwtAssertionCredentials)
    self.assertIn('repo', creds.scope)

  def test_valid_credentials_with_scope_as_list(self):
    creds = infra_libs.get_signed_jwt_assertion_credentials(
      'valid_creds.json',
      scope=['gist'],
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds,
                          oauth2client.client.SignedJwtAssertionCredentials)
    self.assertIn('gist', creds.scope)

  # Only test one malformed case and rely on LoadJsonCredentialsTest
  # for the other cases.
  def test_malformed_credentials(self):
    with self.assertRaises(infra_libs.AuthError):
      infra_libs.get_signed_jwt_assertion_credentials(
        'creds_malformed.json',
        service_accounts_creds_root=DATA_DIR)


class GetAuthenticatedHttp(unittest.TestCase):
  def test_valid_credentials(self):
    http = infra_libs.get_authenticated_http(
      'valid_creds.json',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(http, httplib2.Http)

  def test_valid_credentials_authenticated(self):
    http = infra_libs.get_authenticated_http(
      'valid_creds.json',
      service_accounts_creds_root=DATA_DIR,
      http_identifier='test_case')
    self.assertIsInstance(http, infra_libs.InstrumentedHttp)

  # Only test one malformed case and rely on LoadJsonCredentialsTest
  # for the other cases.
  def test_malformed_credentials(self):
    with self.assertRaises(infra_libs.AuthError):
      infra_libs.get_authenticated_http(
        'creds_malformed.json',
        service_accounts_creds_root=DATA_DIR)


class InstrumentedHttplib2Test(unittest.TestCase):
  def setUp(self):
    super(InstrumentedHttplib2Test, self).setUp()
    self.mock_time = mock.create_autospec(time.time, spec_set=True)
    self.mock_time.return_value = 42
    self.http = infra_libs.InstrumentedHttp('test', time_fn=self.mock_time)
    self.http._request = mock.Mock()
    ts_mon.reset_for_unittest()

  def test_success_status(self):
    self.http._request.return_value = (
        httplib2.Response({'status': 200}),
        'content')

    response, _ = self.http.request('http://foo/')
    self.assertEqual(200, response.status)
    self.assertEqual(1, http_metrics.response_status.get(
        {'name': 'test', 'client': 'httplib2', 'status': 200}))
    self.assertIsNone(http_metrics.response_status.get(
        {'name': 'test', 'client': 'httplib2', 'status': 404}))

  def test_error_status(self):
    self.http._request.return_value = (
        httplib2.Response({'status': 404}),
        'content')

    response, _ = self.http.request('http://foo/')
    self.assertEqual(404, response.status)
    self.assertIsNone(http_metrics.response_status.get(
        {'name': 'test', 'client': 'httplib2', 'status': 200}))
    self.assertEqual(1, http_metrics.response_status.get(
        {'name': 'test', 'client': 'httplib2', 'status': 404}))

  def test_timeout(self):
    self.http._request.side_effect = socket.timeout

    with self.assertRaises(socket.timeout):
      self.http.request('http://foo/')
    self.assertIsNone(http_metrics.response_status.get(
        {'name': 'test', 'client': 'httplib2', 'status': 200}))
    self.assertEqual(1, http_metrics.response_status.get(
        {'name': 'test', 'client': 'httplib2',
         'status': http_metrics.STATUS_TIMEOUT}))

  def test_connection_error(self):
    self.http._request.side_effect = socket.error

    with self.assertRaises(socket.error):
      self.http.request('http://foo/')
    self.assertIsNone(http_metrics.response_status.get(
        {'name': 'test', 'client': 'httplib2', 'status': 200}))
    self.assertEqual(1, http_metrics.response_status.get(
        {'name': 'test', 'client': 'httplib2',
         'status': http_metrics.STATUS_ERROR}))

  def test_exception(self):
    self.http._request.side_effect = httplib2.HttpLib2Error

    with self.assertRaises(httplib2.HttpLib2Error):
      self.http.request('http://foo/')
    self.assertIsNone(http_metrics.response_status.get(
        {'name': 'test', 'client': 'httplib2', 'status': 200}))
    self.assertEqual(1, http_metrics.response_status.get(
        {'name': 'test', 'client': 'httplib2',
         'status': http_metrics.STATUS_EXCEPTION}))

  def test_response_bytes(self):
    self.http._request.return_value = (
        httplib2.Response({'status': 200}),
        'content')

    _, content = self.http.request('http://foo/')
    self.assertEqual('content', content)
    self.assertEqual(1, http_metrics.response_bytes.get(
        {'name': 'test', 'client': 'httplib2'}).count)
    self.assertEqual(7, http_metrics.response_bytes.get(
        {'name': 'test', 'client': 'httplib2'}).sum)

  def test_request_bytes(self):
    self.http._request.return_value = (
        httplib2.Response({'status': 200}),
        'content')

    _, content = self.http.request('http://foo/', body='wibblewibble')
    self.assertEqual('content', content)
    self.assertEqual(1, http_metrics.request_bytes.get(
        {'name': 'test', 'client': 'httplib2'}).count)
    self.assertEqual(12, http_metrics.request_bytes.get(
        {'name': 'test', 'client': 'httplib2'}).sum)

  def test_duration(self):
    current_time = [4.2]

    def time_side_effect():
      ret = current_time[0]
      current_time[0] += 0.3
      return ret
    self.mock_time.side_effect = time_side_effect

    self.http._request.return_value = (
        httplib2.Response({'status': 200}),
        'content')

    _, _ = self.http.request('http://foo/')
    self.assertEqual(1, http_metrics.durations.get(
        {'name': 'test', 'client': 'httplib2'}).count)
    self.assertAlmostEqual(300, http_metrics.durations.get(
        {'name': 'test', 'client': 'httplib2'}).sum)


class HttpMockTest(unittest.TestCase):
  def test_empty(self):
    http = infra_libs.HttpMock([])
    with self.assertRaises(AssertionError):
      http.request('https://www.google.com', 'GET')

  def test_invalid_parameter(self):
    with self.assertRaises(TypeError):
      infra_libs.HttpMock(None)

  def test_uris_wrong_length(self):
    with self.assertRaises(ValueError):
      infra_libs.HttpMock([(1, 2)])

  def test_uris_wrong_type(self):
    with self.assertRaises(ValueError):
      infra_libs.HttpMock([(None,)])

  def test_invalid_uri(self):
    with self.assertRaises(TypeError):
      infra_libs.HttpMock([(1, {'status': '100'}, None)])

  def test_invalid_headers(self):
    with self.assertRaises(TypeError):
      infra_libs.HttpMock([('https://www.google.com', None, None)])

  def test_headers_without_status(self):
    with self.assertRaises(ValueError):
      infra_libs.HttpMock([('https://www.google.com', {'foo': 'bar'}, None)])

  def test_invalid_body(self):
    with self.assertRaises(TypeError):
      infra_libs.HttpMock([('https://www.google.com', {'status': '200'}, 42)])

  def test_one_uri(self):
    http = infra_libs.HttpMock([('https://www.google.com',
                                 {'status': '403'},
                                 'bar')])
    response, body = http.request('https://www.google.com', 'GET')
    self.assertIsInstance(response, httplib2.Response)
    self.assertEqual(response.status, 403)
    self.assertEqual(body, 'bar')

  def test_two_uris(self):
    http = infra_libs.HttpMock([('https://www.google.com',
                                 {'status': 200}, 'foo'),
                                ('.*', {'status': 404}, '')])
    response, body = http.request('https://mywebserver.woo.hoo', 'GET')
    self.assertIsInstance(response, httplib2.Response)
    self.assertEqual(response.status, 404)
    self.assertEqual(body, '')

    self.assertEqual(http.requests_made[0].uri, 'https://mywebserver.woo.hoo')
    self.assertEqual(http.requests_made[0].method, 'GET')
    self.assertEqual(http.requests_made[0].body, None)
    self.assertEqual(http.requests_made[0].headers, None)
