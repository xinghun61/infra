# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
from datetime import datetime
import mock

import webapp2

from testing_utils import testing

from gae_libs import token
from gae_libs.handlers import base_handler
from libs import time_util


class DummyHandler(base_handler.BaseHandler):
  PERMISSION_LEVEL = base_handler.Permission.ANYONE

  @token.AddXSRFToken(action_id='test')
  def HandleGet(self):
    return {'data': {'key': 'value'}}

  @token.VerifyXSRFToken(action_id='test')
  def HandlePost(self):
    return {'data': {'key': 'value'}}


class TokenTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/test-token', DummyHandler),
      ], debug=True)

  @mock.patch('os.urandom')
  def testGenerateRandomHexKey(self, mocked_urandom):
    mocked_urandom.side_effect = ['abcd']
    hex_key = token.GenerateRandomHexKey(256)
    mocked_urandom.assert_called_once_with(256)
    self.assertEqual('61626364', hex_key)

  @mock.patch('os.urandom')
  def testGetSecretKeySameUser(self, mocked_urandom):
    mocked_urandom.side_effect = ['abcd']
    secret_key = token.SecretKey.GetSecretKey('me')
    mocked_urandom.assert_called_once_with(token._RANDOM_BYTE_LENGTH)
    self.assertEqual('61626364', secret_key)
    self.assertEqual('61626364', token.SecretKey.GetSecretKey('me'))

  @mock.patch('os.urandom')
  def testGetSecretKeyDifferentUser(self, mocked_urandom):
    mocked_urandom.side_effect = ['abcd', 'efgh']
    my_key = token.SecretKey.GetSecretKey('me')
    your_key = token.SecretKey.GetSecretKey('you')
    self.assertNotEqual(my_key, your_key)

  @mock.patch.object(time_util, 'GetUTCNow')
  def testGeneratedXSRFTokenIsValidForSameUserAndSameAction(self, mock_now):
    mock_now.side_effect = [
        datetime(2017, 6, 13, 0, 0, 0),
        datetime(2017, 6, 13, 0, 1, 0)
    ]
    xsrf_token = token.GenerateAuthToken('key', 'email', 'action')
    valid, expired = token.ValidateAuthToken(
        'key', xsrf_token, 'email', 'action')
    self.assertTrue(valid)
    self.assertFalse(expired)

  def testGeneratedXSRFTokenIsInvalidForSameUserButDifferentAction(self):
    xsrf_token = token.GenerateAuthToken('key', 'email', 'action1')
    valid, expired = token.ValidateAuthToken(
        'key', xsrf_token, 'email', 'action2')
    self.assertFalse(valid)
    self.assertFalse(expired)

  def testGeneratedXSRFTokenIsInvalidForDifferentUserButSameAction(self):
    xsrf_token = token.GenerateAuthToken('key', 'email1', 'action')
    valid, expired = token.ValidateAuthToken(
        'key', xsrf_token, 'email2', 'action')
    self.assertFalse(valid)
    self.assertFalse(expired)

  def testGeneratedXSRFTokenIsInvalidForDifferentUserAndAction(self):
    xsrf_token = token.GenerateAuthToken('key', 'email1', 'action1')
    valid, expired = token.ValidateAuthToken(
        'key', xsrf_token, 'email2', 'action2')
    self.assertFalse(valid)
    self.assertFalse(expired)

  @mock.patch('gae_libs.token.GenerateAuthToken')
  @mock.patch('gae_libs.http.auth_util.GetUserEmail', lambda: None)
  def testNotAddXSRFTokenIfUserNotLogin(self, mocked_GenerateAuthToken):
    mocked_GenerateAuthToken.side_effect = ['']
    response = self.test_app.get('/test-token?format=json')
    self.assertEqual(200, response.status_int)
    mocked_GenerateAuthToken.assert_not_called()
    self.assertEqual({'key': 'value'}, response.json_body)

  @mock.patch('gae_libs.token.GenerateAuthToken')
  @mock.patch('gae_libs.http.auth_util.GetUserEmail', lambda: 'test@google.com')
  def testAddXSRFTokenIfUserLogin(self, mocked_GenerateAuthToken):
    mocked_GenerateAuthToken.side_effect = ['token']
    response = self.test_app.get('/test-token?format=json')
    self.assertEqual(200, response.status_int)
    self.assertEqual({
        'key': 'value',
        'xsrf_token': 'token'
    }, response.json_body)
    mocked_GenerateAuthToken.assert_not_called()

  @mock.patch('gae_libs.token.ValidateAuthToken')
  @mock.patch('gae_libs.http.auth_util.GetUserEmail', lambda: 'test@google.com')
  def testInvalidXSRFTokenForUserLogin(self, mocked_ValidateAuthToken):
    mocked_ValidateAuthToken.side_effect = [(False, False)]
    self.test_app.post(
        '/test-token?format=json', {'xsrf_token': 'token'}, status=403)
    mocked_ValidateAuthToken.assert_called_once_with('site', 'token',
                                                     'test@google.com', 'test')

  @mock.patch('gae_libs.token.ValidateAuthToken')
  @mock.patch('gae_libs.http.auth_util.GetUserEmail', lambda: 'test@google.com')
  def testValidXSRFTokenForUserLogin(self, mocked_ValidateAuthToken):
    mocked_ValidateAuthToken.side_effect = [(True, False)]
    response = self.test_app.post(
        '/test-token?format=json', {'xsrf_token': 'token'}, status=200)
    mocked_ValidateAuthToken.assert_called_once_with('site', 'token',
                                                     'test@google.com', 'test')
    self.assertEqual({'key': 'value'}, response.json_body)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 06, 13, 0, 0, 0))
  def testValidateAuthTokenSucceed(self, _):
    tested_token = token.GenerateAuthToken('key', 'email')
    valid, expired = token.ValidateAuthToken('key', tested_token, 'email')
    self.assertTrue(valid)
    self.assertFalse(expired)

  def testValidateAuthTokenNoToken(self):
    valid, expired = token.ValidateAuthToken('key', None, 'email')
    self.assertFalse(valid)
    self.assertFalse(expired)

  def testValidateAuthTokenDateInvalid(self):
    tested_token = base64.urlsafe_b64encode('token')
    valid, expired = token.ValidateAuthToken('key', tested_token, 'email')
    self.assertFalse(valid)
    self.assertFalse(expired)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 06, 13, 2, 0, 0))
  def testValidateAuthTokenExpired(self, _):
    tested_token = token.GenerateAuthToken(
        'key', 'email', when=datetime(2017, 06, 13, 0, 0, 0))
    valid, expired = token.ValidateAuthToken('key', tested_token, 'email')
    self.assertTrue(valid)
    self.assertTrue(expired)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 06, 13, 0, 0, 0))
  def testValidateAuthTokenLengthDifferent(self, _):
    token_created_timestamp = time_util.ConvertToTimestamp(
        datetime(2017, 06, 13, 0, 0, 0))
    tested_token = base64.urlsafe_b64encode('token:' +
                                            str(token_created_timestamp))
    valid, expired = token.ValidateAuthToken('key', tested_token, 'email')
    self.assertFalse(valid)
    self.assertFalse(expired)