# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions used by the Monorail servlet base class."""

import datetime
import logging
import time

from framework import permissions
from framework import template_helpers


_WEEKDAY = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
            'Saturday', 'Sunday']


def GetBannerTime(timestamp):
  """Converts a timestamp into EZT-ready data so it can appear in the banner.

  Args:
    timestamp: timestamp expressed in the following format:
         [year,month,day,hour,minute,second]
         e.g. [2009,3,20,21,45,50] represents March 20 2009 9:45:50 PM

  Returns:
    EZT-ready data used to display the time inside the banner message.
  """
  if timestamp is None:
    return None

  # Get the weekday and 'hour:min AM/PM' to display the timestamp
  # to users with javascript disabled
  ts = datetime.datetime(*[int(t) for t in timestamp])
  weekday = _WEEKDAY[ts.weekday()]
  hour_min = datetime.datetime.strftime(ts, '%I:%M%p')

  # Convert the timestamp to milliseconds since the epoch to display
  # the timestamp to users with javascript
  ts_ms = time.mktime(ts.timetuple()) * 1000

  return template_helpers.EZTItem(
      ts=ts_ms, year=ts.year, month=ts.month, day=ts.day, hour=ts.hour,
      minute=ts.minute, second=ts.second, weekday=weekday, hour_min=hour_min)


def AssertBasePermissionForUser(user, user_view):
  """Verify user permissions and state.

  Args:
    user: user_pb2.User protocol buffer for the user
    user_view: framework.views.UserView for the user
  """
  if permissions.IsBanned(user, user_view):
    raise permissions.BannedUserException(
        'You have been banned from using this site')


def AssertBasePermission(mr):
  """Make sure that the logged in user can view the requested page.

  Args:
    mr: common information parsed from the HTTP request.

  Returns:
    Nothing

  Raises:
    BannedUserException: If the user is banned.
    PermissionException: If the user does not have permisssion to view.
  """
  AssertBasePermissionForUser(mr.auth.user_pb, mr.auth.user_view)

  if mr.project_name and not CheckPerm(mr, permissions.VIEW):
    logging.info('your perms are %r', mr.perms)
    raise permissions.PermissionException(
        'User is not allowed to view this project')


def CheckPerm(mr, perm, art=None, granted_perms=None):
  """Convenience method that makes permission checks easier.

  Args:
    mr: common information parsed from the HTTP request.
    perm: A permission constant, defined in module framework.permissions
    art: Optional artifact pb
    granted_perms: optional set of perms granted specifically in that artifact.

  Returns:
    A boolean, whether the request can be satisfied, given the permission.
  """
  return mr.perms.CanUsePerm(
      perm, mr.auth.effective_ids, mr.project,
      permissions.GetRestrictions(art), granted_perms=granted_perms)


def CheckPermForProject(mr, perm, project, art=None):
  """Convenience method that makes permission checks for projects easier.

  Args:
    mr: common information parsed from the HTTP request.
    perm: A permission constant, defined in module framework.permissions
    project: The project to enforce permissions for.
    art: Optional artifact pb

  Returns:
    A boolean, whether the request can be satisfied, given the permission.
  """
  perms = permissions.GetPermissions(
      mr.auth.user_pb, mr.auth.effective_ids, project)
  return perms.CanUsePerm(
      perm, mr.auth.effective_ids, project, permissions.GetRestrictions(art))
