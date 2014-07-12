# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for generating and verifying user authentication."""

__author__ = 'agable@google.com (Aaron Gable)'


import functools
import logging

from google.appengine.api import users
from google.appengine.ext import ndb

import model


def CheckUserInList(key_or_emails):
  """Return true if the currently logged in user is in the email list.

  Args:
    key_or_emails: either a list of string email addresses, or an ndb.Key
                   pointing to a model.EmailList object.
  """
  user = users.get_current_user()
  if not user:
    logging.warning('No logged in user.')
    return False
  email = user.email()

  if users.is_current_user_admin():
    logging.info('User %s is admin.', email)
    return True

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
