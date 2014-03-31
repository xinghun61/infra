# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for generating and verifying user authentication."""

__author__ = 'agable@google.com (Aaron Gable)'


import functools
import logging

from google.appengine.api import users
from google.appengine.ext import ndb

import constants
import model


def CheckUserAuth(handler):
  """Decorator for webapp2 request handler methods.

  Only use on webapp2.RequestHandler methods (e.g. get, post, put).

  Checks to see if the user is logged in, and if they are
  * If they are an administrator of the app, or
  * If their email appears in the list of allowed addresses

  Sets request.authenticated to 'user' if successful. Otherwise, None.
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
      self.request.authenticated = 'user'
      handler(self, *args, **kwargs)

    if getattr(self.request, 'authenticated', None):
      finish_auth('Already authenticated.')
      return

    user = users.get_current_user()
    if not user:
      abort_auth('No logged in user.')
      return

    if users.is_current_user_admin():
      finish_auth('User is admin.')
      return

    email = user.email()
    email_list = ndb.Key(model.EmailList, constants.LIST).get()
    allowed_emails = email_list.emails if email_list else []

    if email in allowed_emails:
      finish_auth('User in allowed email list.')
      return

    if (email.endswith('@google.com') and
        email.replace('@google.com', '@chromium.org') in allowed_emails):
      finish_auth('User in allowed email list via google -> chromium map.')
      return

    abort_auth('User not in allowed email list.')

  return wrapper


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
