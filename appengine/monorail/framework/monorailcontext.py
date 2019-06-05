# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Context object to hold utility objects used during request processing.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from framework import authdata
from framework import permissions
from framework import profiler
from framework import sql
from framework import template_helpers


class MonorailContext(object):
  """Context with objects used in request handling mechanics.

  Attrributes:
    cnxn: MonorailConnection to the SQL DB.
    auth: AuthData object that identifies the account making the request.
    perms: PermissionSet for requesting user, set by LookupLoggedInUserPerms().
    profiler: Profiler object.
    warnings: A list of warnings to present to the user.
    errors: A list of errors to present to the user.

  Unlike MonorailRequest, this object does not parse any part of the request,
  retrieve any business objects (other than the User PB for the requesting
  user), or check any permissions.
  """

  def __init__(
      self, services, cnxn=None, requester=None, auth=None, perms=None):
    """Construct a MonorailContext.

    Args:
      services: Connection to backends.
      cnxn: Optional connection to SQL database.
      requester: String email address of user making the request or None.
      auth: AuthData object used during testing.
      perms: PermissionSet used during testing.
    """
    self.cnxn = cnxn or sql.MonorailConnection()
    self.auth = auth or authdata.AuthData.FromEmail(
        self.cnxn, requester, services, autocreate=True)
    self.perms = perms  # Usually None until LookupLoggedInUserPerms() called.
    self.profiler = profiler.Profiler()

    # TODO(jrobbins): make self.errors not be UI-centric.
    self.warnings = []
    self.errors = template_helpers.EZTError()

  def LookupLoggedInUserPerms(self, project):
    """Look up perms for user making a request in project (can be None)."""
    with self.profiler.Phase('looking up signed in user permissions'):
      self.perms = permissions.GetPermissions(
          self.auth.user_pb, self.auth.effective_ids, project)

  def CleanUp(self):
    """Close the DB cnxn and any other clean up."""
    if self.cnxn:
      self.cnxn.Close()
    self.cnxn = None

  def __repr__(self):
    """Return a string more useful for debugging."""
    return '%s(cnxn=%r, auth=%r, perms=%r)' % (
        self.__class__.__name__, self.cnxn, self.auth, self.perms)
