# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for generating and verifying user authentication."""

__author__ = 'agable@google.com (Aaron Gable)'


import collections
import endpoints
import functools
import logging

from google.appengine.ext import ndb
from google.appengine.api import oauth
from google.appengine.api import users


TRUSTED_APP_IDS = [
  'chrome-infra-auth',
  'chrome-infra-auth-dev',
  'chromiumcodereview-hr',
]


class User(object):
  """A generalized user, compatible with both AppEngine and Cloud Endpoints."""

  AUTH_COOKIES = 'appengine'
  AUTH_HMAC = 'hmac'
  AUTH_OAUTH = 'oauth'
  AUTH_TRUSTED_APP = 'trusted_app'

  def __init__(self, email, is_admin, auth):
    self._email = email
    self._is_admin = is_admin
    self._auth = frozenset(auth)

  def __str__(self):
    return 'User(email=%s, admin=%s, auth=%s)' % (self._email, self._is_admin,
                                                  self._auth)

  @property
  def email(self):
    return self._email

  @property
  def is_logged_in(self):
    return self.email is not None

  @property
  def is_admin(self):
    if callable(self._is_admin):
      # Allow lazy evaluation (is expensive for endpoints).
      self._is_admin = self._is_admin()
    return self._is_admin

  def is_auth(self, *auth):
    return bool(self._auth & set(auth))

  @classmethod
  def from_request(cls, request):
    email = None
    admin = False
    auth = []

    app_id = request.headers.get('X-Appengine-Inbound-Appid')
    if app_id in TRUSTED_APP_IDS:
      auth.append(cls.AUTH_TRUSTED_APP)

    if getattr(request, 'authenticated', None) == 'hmac':
      # Added via hmac_util.CheckHmacAuth decorator.
      auth.append(cls.AUTH_HMAC)

    u = users.get_current_user()
    if u:
      email = u.email()
      admin = users.is_current_user_admin()
      auth.append(cls.AUTH_COOKIES)
    return cls(email, admin, auth)


  @classmethod
  def from_endpoints(cls):
    u = endpoints.get_current_user()
    if not u:
      return None
    return cls(u.email(),
               lambda: oauth.is_current_user_admin(endpoints.EMAIL_SCOPE),
               cls.AUTH_OAUTH)


def CheckUserInList(user, key_or_emails):
  """Return true if the currently logged in user is in the email list.

  Args:
    key_or_emails: either a list of string email addresses, or an ndb.Key
                   pointing to a model.EmailList object.
  """
  if not user:
    logging.warning('No logged in user.')
    return False

  if user.is_admin:
    logging.info('User %s is admin.', user)
    return True

  email = user.email
  if not email:
    logging.warning('User has no associated e-mail.')
    return False

  if isinstance(key_or_emails, ndb.Key):
    email_list = key_or_emails.get()
    emails = email_list.emails if email_list else []
  elif isinstance(key_or_emails, list):
    emails = key_or_emails
  else:
    logging.error('Invalid input (not a list or datastore key): %s',
                  key_or_emails)
    return False

  if email in emails:
    logging.info('User %s in email list.', email)
    return True

  if (email.endswith('@google.com') and
      email.replace('@google.com', '@chromium.org') in emails):
    logging.info('User %s in email list via google -> chromium map.', email)
    return True

  logging.warning('User %s not in email list.', email)
  return False


def RequireAuth(handler):
  """Decorator for webapp2 request handler methods.

  Only use on webapp2.RequestHandler methods (e.g. get, post, put),
  and only after using a 'Check____Auth' decorator.

  Expects the handler's self.request.authenticated to be not False-ish.
  If it doesn't exist or evaluates to False, 403s. Otherwise, passes
  control to the wrapped handler.
  """
  @functools.wraps(handler)
  def wrapper(self, *args, **kwargs):
    """Does the real legwork and calls the wrapped handler."""
    if not getattr(self.request, 'authenticated', None):
      self.abort(403)
    else:
      handler(self, *args, **kwargs)

  return wrapper
