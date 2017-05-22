# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import os

from google.appengine.ext import ndb

from oauth2client import xsrfutil

from gae_libs.http import auth_util


_RANDOM_BYTE_LENGTH = 512


def GenerateRandomHexKey(length=_RANDOM_BYTE_LENGTH):
  """Returns a key hexed from random bytes at the given length for crypto."""
  # After encoded in hex, the length doubles.
  return os.urandom(length).encode('hex')


class SecretKey(ndb.Model):
  # Store the secret key.
  secret_key = ndb.StringProperty(indexed=False)

  @classmethod
  def GetSecretKey(cls, user_id):
    """Returns a secret key for the user and creates it on demand."""
    uid = hashlib.sha256(str(user_id)).hexdigest()
    entity = ndb.Key(cls, uid).get()
    if not entity:
      entity = cls(id=uid, secret_key=GenerateRandomHexKey())
      entity.put()
    return entity.secret_key


def GenerateXSRFToken(user_email, action_id=''):
  """Generates a XSRF token for the given user and action."""
  return xsrfutil.generate_token(
      SecretKey.GetSecretKey('site'), user_id=user_email, action_id=action_id)


def ValidateXSRFToken(user_email, xsrf_token, action_id=''):
  """Returns True if the XSRF token is valid for the given user and action."""
  return xsrfutil.validate_token(
      SecretKey.GetSecretKey('site'), xsrf_token,
      user_id=user_email, action_id=action_id)


class AddXSRFToken(object):
  """A decorator to add a XSRF token to the response for the handler."""

  def __init__(self, action_id=''):
    self._action_id = action_id

  def __call__(self, handler_method):
    def AddToken(handler, *args, **kwargs):
      result = handler_method(handler, *args, **kwargs)
      user_email = auth_util.GetUserEmail()
      if not user_email:
        return result
      xsrf_token = GenerateXSRFToken(user_email, self._action_id)
      result = result or {}
      result['data'] = result.get('data', {})
      result['data']['xsrf_token'] = xsrf_token
      return result

    return AddToken


class VerifyXSRFToken(object):
  """A decorator to enforce that the XSRF token is validated for the handler."""

  def __init__(self, action_id=''):
    self._action_id = action_id

  def __call__(self, handler_method):
    def VerifyToken(handler, *args, **kwargs):
      user_email = auth_util.GetUserEmail()
      xsrf_token = str(handler.request.get('xsrf_token'))
      if (not user_email or
          not ValidateXSRFToken(user_email, xsrf_token, self._action_id)):
        return handler.CreateError('Invalid XSRF token', return_code=403)
      return handler_method(handler, *args, **kwargs)
    return VerifyToken
