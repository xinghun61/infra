# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions used by the Monorail servlet base class."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import calendar
import datetime
import logging
import urllib

from framework import framework_bizobj
from framework import framework_helpers
from framework import permissions
from framework import template_helpers
from framework import urls
from framework import xsrf

_ZERO = datetime.timedelta(0)

class _UTCTimeZone(datetime.tzinfo):
    """UTC"""
    def utcoffset(self, _dt):
        return _ZERO
    def tzname(self, _dt):
        return "UTC"
    def dst(self, _dt):
        return _ZERO

_UTC = _UTCTimeZone()


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

  ts = datetime.datetime(*timestamp, tzinfo=_UTC)
  return calendar.timegm(ts.timetuple())


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


def ComputeIssueEntryURL(mr, config):
  """Compute the URL to use for the "New issue" subtab.

  Args:
    mr: commonly used info parsed from the request.
    config: ProjectIssueConfig for the current project.

  Returns:
    A URL string to use.  It will be simply "entry" in the non-customized
    case. Otherewise it will be a fully qualified URL that includes some
    query string parameters.
  """
  if not config.custom_issue_entry_url:
    return '/p/%s/issues/entry' % (mr.project_name)

  base_url = config.custom_issue_entry_url
  sep = '&' if '?' in base_url else '?'
  token = xsrf.GenerateToken(
    mr.auth.user_id, '/p/%s%s%s' % (mr.project_name, urls.ISSUE_ENTRY, '.do'))
  role_name = framework_helpers.GetRoleName(mr.auth.effective_ids, mr.project)

  continue_url = urllib.quote(framework_helpers.FormatAbsoluteURL(
      mr, urls.ISSUE_ENTRY + '.do'))

  return '%s%stoken=%s&role=%s&continue=%s' % (
      base_url, sep, urllib.quote(token),
      urllib.quote(role_name or ''), continue_url)


def IssueListURL(mr, config, query_string=None):
  """Make an issue list URL for non-members or members."""
  url = '/p/%s%s' % (mr.project_name, urls.ISSUE_LIST)
  if query_string:
    url += '?' + query_string
  elif framework_bizobj.UserIsInProject(mr.project, mr.auth.effective_ids):
    if config and config.member_default_query:
      url += '?q=' + urllib.quote_plus(config.member_default_query)
  return url
