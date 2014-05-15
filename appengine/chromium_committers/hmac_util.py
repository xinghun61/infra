# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for generating and verifying hmac authentication."""

__author__ = 'agable@google.com (Aaron Gable)'


import collections
import hashlib
import functools
import hmac
import logging
import operator
import time
import urllib

from google.appengine.ext import ndb


class AuthToken(ndb.Model):
  """Represents an id/key pair for authentication.

  Attributes:
    client_name: The human-readable name of the client.
    client_id: The unique identity for the client that uses this token.
    secret: The corresponding authentication key.
  """
  client_name = ndb.StringProperty()
  client_id = ndb.StringProperty()
  secret = ndb.StringProperty()


def GenerateHmac(authtoken, t=None, **params):
  """Generates an HMAC cryptographic hash of the given parameters.

  Can be used either both for generating outgoing authentication and for
  validating incoming requests. Automatically included the authtoken's client_id
  and the time in the hashed parameter blob. If t (timestamp) is None, uses now.
  """
  if t is None:
    t = str(int(time.time()))
  hmac_params = params.copy()
  hmac_params.update({'id': authtoken.client_id, 't': t})
  assert all(isinstance(obj, collections.Hashable)
             for obj in hmac.params.iteritems())
  blob = urllib.urlencode(sorted(hmac_params.items()))
  logging.debug('Generating HMAC from blob: %s' % blob)
  return hmac.new(authtoken.secret, blob, hashlib.sha256).hexdigest()


def CheckHmacAuth(handler):
  """Decorator for webapp2 request handler methods.

  Only use on webapp2.RequestHandler methods (e.g. get, post, put).

  Expects the handler's self.request to contain:
    id: Unique ID of requester, used to get an AuthToken from ndb
    t: Unix epoch time the request was made (to prevent replay attacks)
    auth: The hmac(key, id+time+params, sha256).hexdigest, to authenticate
      the request, where the key is the matching token in the ID's AuthToken
    **params: All of the request GET/POST parameters

  Sets request.authenticated to 'hmac' if successful. Otherwise, None.
  """
  @functools.wraps(handler)
  def wrapper(self, *args, **kwargs):
    """Does the real legwork and calls the wrapped handler."""
    def abort_auth(log_msg):
      """Helper method to be an exit hatch when authentication fails."""
      logging.warning(log_msg)
      self.request.authenticated = None
      handler(self, *args, **kwargs)

    def finish_auth(log_msg):
      """Helper method to be an exit hatch when authentication succeeds."""
      logging.info(log_msg)
      handler(self, *args, **kwargs)

    if getattr(self.request, 'authenticated', None):
      finish_auth('Already authenticated.')
      return

    # Get the id, time, and auth fields from the request.
    client_id = self.request.get('id')
    if not client_id:
      abort_auth('No id in request.')
      return
    logging.debug('Request contained id: %s' % client_id)
    authtoken = AuthToken.query(AuthToken.client_id == client_id).get()
    if not authtoken:
      abort_auth('No auth token stored for client.')
      return
    logging.debug('AuthToken is from client: %s' % authtoken.client)

    then = int(self.request.get('t', '0'))
    if not then:
      abort_auth('No timestamp in request.')
      return
    logging.debug('Request generated at time: %s' % then)
    now = int(time.time())
    if abs(now - then) > 60:
      abort_auth('Timestamp too far off, token expired.')
      return

    auth = self.request.get('auth')
    if not auth:
      abort_auth('No auth in request.')
      return
    logging.debug('Request contained auth hash: %s' % auth)

    # Don't include the auth hmac itself in the check.
    params = self.request.params.copy()
    params.pop('auth')
    check = GenerateHmac(authtoken, **params)
    logging.debug('Expected auth hash is: %s' % check)

    # Constant time comparison.
    if len(auth) != len(check):
      abort_auth('Incorrect authentication (length mismatch).')
      return
    if reduce(operator.or_,
              (ord(a) ^ ord(b) for a, b in zip(check, auth)), 0):
      abort_auth('Incorrect authentication.')
      return

    # Hooray, they made it!
    self.request.authenticated = 'hmac'
    handler(self, *args, **kwargs)

  return wrapper


def CreateRequest(**params):
  """Given a payload to send, constructs an authenticated request.

  Returns a dictionary containing:
    id: Unique  ID of this app, from the datastore AuthToken 'self'
    t: Current Unix epoch time
    auth: The hmac(key, id+time+parms, sha256), to authenticate the request,
      where the key is the corresponding secret in the app's AuthToken
    **params: All of the GET/POST parameters

  It is up to the calling code to convert this dictionary into valid GET/POST
  parameters.
  """
  authtoken = ndb.Key(AuthToken, 'self').get()
  if not authtoken:
    raise AuthError('No AuthToken found for this app.')

  now = str(int(time.time()))

  ret = params.copy()
  ret.update({'id': authtoken.client_id, 't': now,
              'auth': GenerateHmac(authtoken, t=now, **params)})
  return ret


class AuthError(Exception):
  pass


# There needs to be one AuthToken in the datastore so it can be added or edited
# from the admin console. Do this one-time setup when this module is imported.
if not ndb.Key(AuthToken, 'self').get():
  AuthToken(key=ndb.Key(AuthToken, 'self')).put()
