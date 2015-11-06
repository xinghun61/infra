# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file handles controller-level access to Committer functionality."""

__author__ = 'agable@google.com (Aaron Gable)'


import logging

from google.appengine.ext import ndb

from appengine_module.chromium_committers import auth_util
from appengine_module.chromium_committers import model


class InvalidList(Exception):
  """Error raised to indicate that the requested list is invalid."""
  pass

class AuthorizationError(Exception):
  """Error raised to indicate that the user is not authorized for an action."""
  pass


def get_list_names_for_user(user):
  lists = model.EmailList.query().fetch(keys_only=True)
  return [l.string_id() for l in lists if auth_util.CheckUserInList(user, l)]


def get_list(user, list_name):
  logging.debug('"get_list" request for "%s" by %s', list_name, user)
  if not user:
    raise AuthorizationError('Authentication required.')
  if not list_name:
    raise InvalidList('Tried to view list with no name.')

  committer_list = ndb.Key(model.EmailList, list_name).get()
  emails = committer_list.emails if committer_list else []
  logging.debug('Fetched emails: %s', emails)
  if not emails:
    raise InvalidList('List is empty or does not exist.')

  valid_request = (
      user.is_auth(auth_util.User.AUTH_HMAC,
                   auth_util.User.AUTH_TRUSTED_APP,
                   auth_util.User.AUTH_TRUSTED_CLIENT) or
      auth_util.CheckUserInList(user, emails)
  )
  if not valid_request:
    raise AuthorizationError("User not permitted to view list.")
  return committer_list


def put_list(user, list_name, emails):
  logging.debug('"put_list" request for "%s" by %s', list_name, user)
  if not (user and (user.is_admin or user.is_auth(auth_util.User.AUTH_HMAC))):
    raise AuthorizationError('User does not have permission to mutate lists.')
  committer_list = model.EmailList(id=list_name, emails=emails)
  committer_list.put()
