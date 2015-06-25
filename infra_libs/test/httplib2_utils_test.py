# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from infra_libs import httplib2_utils

import httplib2
import mock
import oauth2client.client


DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')


class ConstantsTest(unittest.TestCase):
  def test_constants_presence(self):
    self.assertTrue(httplib2_utils.SERVICE_ACCOUNTS_CREDS_ROOT)


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
    with self.assertRaises(httplib2_utils.AuthError):
      httplib2_utils.load_service_account_credentials(
        'creds_missing_type.json',
        service_accounts_creds_root=DATA_DIR)

  def test_wrong_type(self):
    with self.assertRaises(httplib2_utils.AuthError):
      httplib2_utils.load_service_account_credentials(
        'creds_wrong_type.json',
        service_accounts_creds_root=DATA_DIR)

  def test_missing_client_email(self):
    with self.assertRaises(httplib2_utils.AuthError):
      httplib2_utils.load_service_account_credentials(
        'creds_missing_client_email.json',
        service_accounts_creds_root=DATA_DIR)

  def test_missing_private_key(self):
    with self.assertRaises(httplib2_utils.AuthError):
      httplib2_utils.load_service_account_credentials(
        'creds_missing_private_key.json',
        service_accounts_creds_root=DATA_DIR)

  def test_malformed(self):
    with self.assertRaises(httplib2_utils.AuthError):
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
    creds = httplib2_utils.get_signed_jwt_assertion_credentials(
      'valid_creds.json',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds,
                          oauth2client.client.SignedJwtAssertionCredentials)
    # A default scope must be provided, we don't care which one
    self.assertTrue(creds.scope)

  def test_valid_credentials_with_scope_as_string(self):
    creds = httplib2_utils.get_signed_jwt_assertion_credentials(
      'valid_creds.json',
      scope='repo',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds,
                          oauth2client.client.SignedJwtAssertionCredentials)
    self.assertIn('repo', creds.scope)

  def test_valid_credentials_with_scope_as_list(self):
    creds = httplib2_utils.get_signed_jwt_assertion_credentials(
      'valid_creds.json',
      scope=['gist'],
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds,
                          oauth2client.client.SignedJwtAssertionCredentials)
    self.assertIn('gist', creds.scope)

  # Only test one malformed case and rely on LoadJsonCredentialsTest
  # for the other cases.
  def test_malformed_credentials(self):
    with self.assertRaises(httplib2_utils.AuthError):
      httplib2_utils.get_signed_jwt_assertion_credentials(
        'creds_malformed.json',
        service_accounts_creds_root=DATA_DIR)


class GetAuthenticatedHttp(unittest.TestCase):
  def test_valid_credentials(self):
    http = httplib2_utils.get_authenticated_http(
      'valid_creds.json',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(http, httplib2.Http)

  # Only test one malformed case and rely on LoadJsonCredentialsTest
  # for the other cases.
  def test_malformed_credentials(self):
    with self.assertRaises(httplib2_utils.AuthError):
      httplib2_utils.get_authenticated_http(
        'creds_malformed.json',
        service_accounts_creds_root=DATA_DIR)


class InstrumentedHttplib2Test(unittest.TestCase):
  def setUp(self):
    super(InstrumentedHttplib2Test, self).setUp()
    self.mock_time = mock.Mock()
    self.mock_time.return_value = 42
    self.http = httplib2_utils.InstrumentedHttp('test', time_fn=self.mock_time)
    self.http._reset_metrics_for_testing()
    self.http._request = mock.Mock()

  def test_success_status(self):
    self.http._request.return_value = (
        httplib2.Response({'status': 200}),
        'content')

    response, _ = self.http.request('http://foo/')
    self.assertEqual(200, response.status)
    self.assertEqual(1, self.http.response_status_metric.get(
        {'name': 'test', 'client': 'httplib2', 'status': 200}))
    self.assertEqual(0, self.http.response_status_metric.get(
        {'name': 'test', 'client': 'httplib2', 'status': 404}))

  def test_error_status(self):
    self.http._request.return_value = (
        httplib2.Response({'status': 404}),
        'content')

    response, _ = self.http.request('http://foo/')
    self.assertEqual(404, response.status)
    self.assertEqual(0, self.http.response_status_metric.get(
        {'name': 'test', 'client': 'httplib2', 'status': 200}))
    self.assertEqual(1, self.http.response_status_metric.get(
        {'name': 'test', 'client': 'httplib2', 'status': 404}))

  def test_response_bytes(self):
    self.http._request.return_value = (
        httplib2.Response({'status': 200}),
        'content')

    _, content = self.http.request('http://foo/')
    self.assertEqual('content', content)
    self.assertEqual(1, self.http.response_bytes_metric.get(
        {'name': 'test', 'client': 'httplib2'}).count)
    self.assertEqual(7, self.http.response_bytes_metric.get(
        {'name': 'test', 'client': 'httplib2'}).sum)

  def test_request_bytes(self):
    self.http._request.return_value = (
        httplib2.Response({'status': 200}),
        'content')

    _, content = self.http.request('http://foo/', body='wibblewibble')
    self.assertEqual('content', content)
    self.assertEqual(1, self.http.request_bytes_metric.get(
        {'name': 'test', 'client': 'httplib2'}).count)
    self.assertEqual(12, self.http.request_bytes_metric.get(
        {'name': 'test', 'client': 'httplib2'}).sum)

  def test_duration(self):
    time = [4.2]

    def time_side_effect():
      ret = time[0]
      time[0] += 0.3
      return ret
    self.mock_time.side_effect = time_side_effect

    self.http._request.return_value = (
        httplib2.Response({'status': 200}),
        'content')

    _, _ = self.http.request('http://foo/')
    self.assertEqual(1, self.http.durations_metric.get(
        {'name': 'test', 'client': 'httplib2'}).count)
    self.assertAlmostEqual(300, self.http.durations_metric.get(
        {'name': 'test', 'client': 'httplib2'}).sum)
