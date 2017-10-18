# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to hold information parsed from a request.
@@@"""

from google.appengine.api import users

from proto import user_pb2
from framework import framework_views


class AuthData(object):
  """This object holds authentication data about a user.

  This is used by MonorailRequest as it determines which user the
  requester is authenticated as and fetches the user's data.  It can
  also be used to lookup perms for user IDs specified in issue fields.

  Attributes:
    user_id: The user ID of the user (or 0 if not signed in).
    effective_ids: A set of user IDs that includes the signed in user's
        direct user ID and the user IDs of all their user groups.
        This set will be empty for anonymous users.
    user_view: UserView object for the signed-in user.
    user_pb: User object for the signed-in user.
    email: email address for the user, or None.
  """

  def __init__(self):
    self.user_id = 0
    self.effective_ids = set()
    self.user_view = None
    self.user_pb = user_pb2.MakeUser(0)
    self.email = None

  @classmethod
  def FromRequest(cls, cnxn, services):
    """Determine auth information from the request and fetches user data.

    If everything works and the user is signed in, then all of the public
    attributes of the AuthData instance will be filled in appropriately.

    Args:
      cnxn: connection to the SQL database.
      services: Interface to all persistence storage backends.

    Returns:
      A new AuthData object.
    """
    user = users.get_current_user()
    if user is None:
      return cls()
    else:
      # We create a User row for each user who visits the site.
      # TODO(jrobbins): we should really only do it when they take action.
      return cls.FromEmail(cnxn, user.email(), services, autocreate=True)

  @classmethod
  def FromEmail(cls, cnxn, email, services, autocreate=False):
    """Determine auth information for the given user email address.

    Args:
      cnxn: monorail connection to the database.
      email: string email address of the user.
      services: connections to backend servers.
      autocreate: set to True to create a new row in the Users table if needed.

    Returns:
      A new AuthData object.

    Raises:
      user_svc.NoSuchUserException: If the user of the email does not exist.
    """
    auth = cls()
    auth.email = email
    if email:
      auth.user_id = services.user.LookupUserID(
          cnxn, email, autocreate=autocreate)
      assert auth.user_id

    cls._FinishInitialization(cnxn, auth, services)
    return auth

  @classmethod
  def FromUserID(cls, cnxn, user_id, services):
    """Determine auth information for the given user ID.

    Args:
      cnxn: monorail connection to the database.
      user_id: int user ID of the user.
      services: connections to backend servers.

    Returns:
      A new AuthData object.
    """
    auth = cls()
    auth.user_id = user_id
    if auth.user_id:
      auth.email = services.user.LookupUserEmail(cnxn, user_id)

    cls._FinishInitialization(cnxn, auth, services)
    return auth

  @classmethod
  def _FinishInitialization(cls, cnxn, auth, services):
    """Fill in the test of the fields based on the user_id."""
    # TODO(jrobbins): re-implement same_org
    if auth.user_id:
      auth.effective_ids = services.usergroup.LookupMemberships(
          cnxn, auth.user_id)
      auth.effective_ids.add(auth.user_id)
      auth.user_pb = services.user.GetUser(cnxn, auth.user_id)
      if auth.user_pb:
        auth.user_view = framework_views.UserView(auth.user_pb)
