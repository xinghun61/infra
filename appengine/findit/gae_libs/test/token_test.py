# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

import webapp2

from testing_utils import testing

from gae_libs import token
from gae_libs.handlers import base_handler


class DummyHandler(base_handler.BaseHandler):
  PERMISSION_LEVEL = base_handler.Permission.ANYONE

  @token.AddXSRFToken(action_id='test')
  def HandleGet(self):
    return {'data': {'key': 'value'}}

  @token.VerifyXSRFToken(action_id='test')
  def HandlePost(self):
    return {'data': {'key': 'value'}}


class TokenTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
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

  def testGeneratedXSRFTokenIsValidForSameUserAndSameAction(self):
    xsrf_token = token.GenerateXSRFToken('email', 'action')
    self.assertTrue(token.ValidateXSRFToken('email', xsrf_token, 'action'))

  def testGeneratedXSRFTokenIsInvalidForSameUserButDifferentAction(self):
    xsrf_token = token.GenerateXSRFToken('email', 'action1')
    self.assertFalse(token.ValidateXSRFToken('email', xsrf_token, 'action2'))

  def testGeneratedXSRFTokenIsInvalidForDifferentUserButSameAction(self):
    xsrf_token = token.GenerateXSRFToken('email1', 'action')
    self.assertFalse(token.ValidateXSRFToken('email2', xsrf_token, 'action'))

  def testGeneratedXSRFTokenIsInvalidForDifferentUserAndAction(self):
    xsrf_token = token.GenerateXSRFToken('email1', 'action1')
    self.assertFalse(token.ValidateXSRFToken('email2', xsrf_token, 'action2'))

  @mock.patch('gae_libs.token.GenerateXSRFToken')
  @mock.patch('gae_libs.http.auth_util.GetUserEmail', lambda: None)
  def testNotAddXSRFTokenIfUserNotLogin(self, mocked_GenerateXSRFToken):
    mocked_GenerateXSRFToken.side_effect = ['']
    response = self.test_app.get('/test-token?format=json')
    self.assertEqual(200, response.status_int)
    mocked_GenerateXSRFToken.assert_not_called()
    self.assertEqual({'key': 'value'}, response.json_body)

  @mock.patch('gae_libs.token.GenerateXSRFToken')
  @mock.patch('gae_libs.http.auth_util.GetUserEmail', lambda: 'test@google.com')
  def testAddXSRFTokenIfUserLogin(self, mocked_GenerateXSRFToken):
    mocked_GenerateXSRFToken.side_effect = ['token']
    response = self.test_app.get('/test-token?format=json')
    self.assertEqual(200, response.status_int)
    self.assertEqual({'key': 'value', 'xsrf_token': 'token'},
                     response.json_body)
    mocked_GenerateXSRFToken.assert_not_called()

  @mock.patch('gae_libs.token.ValidateXSRFToken')
  @mock.patch('gae_libs.http.auth_util.GetUserEmail', lambda: None)
  def testInvalidXSRFTokenIfUserNotLogin(self, mocked_ValidateXSRFToken):
    self.test_app.post(
        '/test-token?format=json', {'xsrf_token': 'token'}, status=403)
    mocked_ValidateXSRFToken.assert_not_called()

  @mock.patch('gae_libs.token.ValidateXSRFToken')
  @mock.patch('gae_libs.http.auth_util.GetUserEmail', lambda: 'test@google.com')
  def testInvalidXSRFTokenForUserLogin(self, mocked_ValidateXSRFToken):
    mocked_ValidateXSRFToken.side_effect = [False]
    self.test_app.post(
        '/test-token?format=json', {'xsrf_token': 'token'}, status=403)
    mocked_ValidateXSRFToken.assert_called_once_with(
        'test@google.com', 'token', 'test')

  @mock.patch('gae_libs.token.ValidateXSRFToken')
  @mock.patch('gae_libs.http.auth_util.GetUserEmail', lambda: 'test@google.com')
  def testValidXSRFTokenForUserLogin(self, mocked_ValidateXSRFToken):
    mocked_ValidateXSRFToken.side_effect = [True]
    response = self.test_app.post(
        '/test-token?format=json', {'xsrf_token': 'token'}, status=200)
    mocked_ValidateXSRFToken.assert_called_once_with(
        'test@google.com', 'token', 'test')
    self.assertEqual({'key': 'value'}, response.json_body)
