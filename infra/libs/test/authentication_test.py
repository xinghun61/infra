# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from infra.libs import authentication

import httplib2
import oauth2client.client


DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')


class ConstantsTest(unittest.TestCase):
  def test_constants_presence(self):
    self.assertTrue(authentication.SERVICE_ACCOUNTS_CREDS_ROOT)


class LoadJsonCredentialsTest(unittest.TestCase):
  # Everything's good, should not raise any exceptions.
  def test_valid_credentials(self):
    creds = authentication.load_json_credentials(
      'valid_creds.json',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds, dict)
    self.assertIn('type', creds)
    self.assertIn('client_email', creds)
    self.assertIn('private_key', creds)

  # File exists but issue with the content: raises AuthError.
  def test_missing_type(self):
    with self.assertRaises(authentication.AuthError):
      authentication.load_json_credentials(
        'creds_missing_type.json',
        service_accounts_creds_root=DATA_DIR)

  def test_wrong_type(self):
    with self.assertRaises(authentication.AuthError):
      authentication.load_json_credentials(
        'creds_wrong_type.json',
        service_accounts_creds_root=DATA_DIR)

  def test_missing_client_email(self):
    with self.assertRaises(authentication.AuthError):
      authentication.load_json_credentials(
        'creds_missing_client_email.json',
        service_accounts_creds_root=DATA_DIR)

  def test_missing_private_key(self):
    with self.assertRaises(authentication.AuthError):
      authentication.load_json_credentials(
        'creds_missing_private_key.json',
        service_accounts_creds_root=DATA_DIR)

  def test_malformed(self):
    with self.assertRaises(authentication.AuthError):
      authentication.load_json_credentials(
        'creds_malformed.json',
        service_accounts_creds_root=DATA_DIR)

  # Problem with the file itself
  def test_file_not_found(self):
    with self.assertRaises(IOError):
      authentication.load_json_credentials(
        'this_file_should_not_exist.json',
        service_accounts_creds_root=DATA_DIR)


class GetSignedJwtAssertionCredentialsTest(unittest.TestCase):
  def test_valid_credentials(self):
    creds = authentication.get_signed_jwt_assertion_credentials(
      'valid_creds.json',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds,
                          oauth2client.client.SignedJwtAssertionCredentials)
    # A default scope must be provided, we don't care which one
    self.assertTrue(creds.scope)

  def test_valid_credentials_with_scope_as_string(self):
    creds = authentication.get_signed_jwt_assertion_credentials(
      'valid_creds.json',
      scope='repo',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds,
                          oauth2client.client.SignedJwtAssertionCredentials)
    self.assertIn('repo', creds.scope)

  def test_valid_credentials_with_scope_as_list(self):
    creds = authentication.get_signed_jwt_assertion_credentials(
      'valid_creds.json',
      scope=['gist'],
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(creds,
                          oauth2client.client.SignedJwtAssertionCredentials)
    self.assertIn('gist', creds.scope)

  # Only test one malformed case and rely on LoadJsonCredentialsTest
  # for the other cases.
  def test_malformed_credentials(self):
    with self.assertRaises(authentication.AuthError):
      authentication.get_signed_jwt_assertion_credentials(
        'creds_malformed.json',
        service_accounts_creds_root=DATA_DIR)


class GetAuthenticatedHttp(unittest.TestCase):
  def test_valid_credentials(self):
    http = authentication.get_authenticated_http(
      'valid_creds.json',
      service_accounts_creds_root=DATA_DIR)
    self.assertIsInstance(http, httplib2.Http)

  # Only test one malformed case and rely on LoadJsonCredentialsTest
  # for the other cases.
  def test_malformed_credentials(self):
    with self.assertRaises(authentication.AuthError):
      authentication.get_authenticated_http(
        'creds_malformed.json',
        service_accounts_creds_root=DATA_DIR)
