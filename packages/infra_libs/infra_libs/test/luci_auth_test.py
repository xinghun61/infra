# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import json
import os
import time
import unittest

import httplib2

from infra_libs import httplib2_utils
from infra_libs import luci_auth
from infra_libs import luci_ctx
from infra_libs import utils


# Mocked port of the local auth server.
_PORT = 12345

# "Good" local_auth section value in LUCI_CONTEXT.
_LOCAL_AUTH = {
  'default_account_id': 'task',
  'secret': 'zzz',
  'rpc_port': _PORT,
}


class AuthTest(unittest.TestCase):
  @contextlib.contextmanager
  def luci_ctx(self, body):
    luci_ctx._reset()
    with utils.temporary_directory() as tempdir:
      ctx_file = os.path.join(tempdir, 'ctx.json')
      with open(ctx_file, 'w') as f:
        json.dump(body, f)
      yield {'LUCI_CONTEXT': ctx_file}

  def mocked_http(self, reply, status=200):
    if not isinstance(reply, basestring):
      reply = json.dumps(reply)
    return httplib2_utils.HttpMock([
      (
        r'.*',
        {'Context-Type': 'application/json', 'status': status},
        reply,
      ),
    ])

  def test_available_yes(self):
    with self.luci_ctx({'local_auth': _LOCAL_AUTH}) as environ:
      self.assertTrue(luci_auth.available(environ=environ))

  def test_available_no_ctx(self):
    with self.luci_ctx({}) as environ:
      self.assertFalse(luci_auth.available(environ=environ))

  def test_broken_ctx(self):
    with self.luci_ctx({'local_auth': {'rpc_port': 'zzz'}}) as environ:
      with self.assertRaises(luci_auth.LUCIAuthError):
        luci_auth.available(environ=environ)

  def test_available_no_default_account(self):
    local_auth = _LOCAL_AUTH.copy()
    local_auth.pop('default_account_id')
    with self.luci_ctx({'local_auth': local_auth}) as environ:
      self.assertFalse(luci_auth.available(environ=environ))

  def test_get_access_token_happy_with_exp(self):
    with self.luci_ctx({'local_auth': _LOCAL_AUTH}) as environ:
      expiry = int(time.time()) + 3600
      http = self.mocked_http({
          'access_token': 'new-token',
          'expiry': expiry,
      })
      tok, exp = luci_auth.get_access_token(
          scopes=['a', 'b'],
          environ=environ,
          http=http)
      self.assertEqual(tok, 'new-token')
      self.assertEqual(exp, datetime.datetime.utcfromtimestamp(expiry))
      self.assertEqual(http.requests_made, [http.HttpCall(
          uri='http://127.0.0.1:%s/rpc/'
              'LuciLocalAuthService.GetOAuthToken' % _PORT,
          method='POST',
          body='{"scopes": ["a", "b"], "secret": "zzz", "account_id": "task"}',
          headers={'Content-Type': 'application/json'},
      )])

  def test_get_access_token_happy_without_exp(self):
    with self.luci_ctx({'local_auth': _LOCAL_AUTH}) as environ:
      tok, exp = luci_auth.get_access_token(
          scopes=['a', 'b'],
          environ=environ,
          http=self.mocked_http({
            'access_token': 'new-token',
          }))
      self.assertEqual(tok, 'new-token')
      self.assertIsNone(exp)

  def test_get_access_token_bad_scopes_1(self):
    with self.luci_ctx({'local_auth': _LOCAL_AUTH}) as environ:
      with self.assertRaises(TypeError):
        luci_auth.get_access_token(
            scopes='not a list',
            environ=environ,
            http=self.mocked_http({}))

  def test_get_access_token_bad_scopes_2(self):
    with self.luci_ctx({'local_auth': _LOCAL_AUTH}) as environ:
      with self.assertRaises(TypeError):
        luci_auth.get_access_token(
            scopes=[1, 2, 3],
            environ=environ,
            http=self.mocked_http({}))

  def test_get_access_token_no_ctx(self):
    with self.luci_ctx({}) as environ:
      with self.assertRaises(luci_auth.LUCIAuthError):
        luci_auth.get_access_token(
            scopes=['a', 'b'],
            environ=environ,
            http=self.mocked_http({}))

  def test_get_access_token_bad_status(self):
    with self.luci_ctx({'local_auth': _LOCAL_AUTH}) as environ:
      with self.assertRaises(luci_auth.LUCIAuthError):
        luci_auth.get_access_token(
            scopes=['a', 'b'],
            environ=environ,
            http=self.mocked_http({}, status=500))

  def test_get_access_token_bad_body(self):
    with self.luci_ctx({'local_auth': _LOCAL_AUTH}) as environ:
      with self.assertRaises(luci_auth.LUCIAuthError):
        luci_auth.get_access_token(
            scopes=['a', 'b'],
            environ=environ,
            http=self.mocked_http('not json', status=200))

  def test_get_access_token_error_code(self):
    with self.luci_ctx({'local_auth': _LOCAL_AUTH}) as environ:
      with self.assertRaises(luci_auth.LUCIAuthError):
        luci_auth.get_access_token(
            scopes=['a', 'b'],
            environ=environ,
            http=self.mocked_http({'error_code': 1}, status=200))

  def test_luci_credentials_happy(self):
    expiry = int(time.time()) + 3600
    with self.luci_ctx({'local_auth': _LOCAL_AUTH}) as environ:
      creds = luci_auth.LUCICredentials(
          scopes=['a', 'b'],
          environ=environ,
          http=self.mocked_http({
            'access_token': 'new-token',
            'expiry': expiry,
          }))
      creds.refresh(httplib2.Http())
      self.assertEqual('new-token', creds.access_token)

  def test_luci_credentials_no_ctx(self):
    with self.luci_ctx({}) as environ:
      with self.assertRaises(luci_auth.LUCIAuthError):
        luci_auth.LUCICredentials(scopes=['a', 'b'], environ=environ)
