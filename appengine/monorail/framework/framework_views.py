# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""View classes to make it easy to display framework objects in EZT."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import time

from third_party import ezt

from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import permissions
from framework import template_helpers
from framework import timestr
from proto import user_pb2
from services import client_config_svc
import settings


_LABEL_DISPLAY_CHARS = 30
_LABEL_PART_DISPLAY_CHARS = 15


class LabelView(object):
  """Wrapper class that makes it easier to display a label via EZT."""

  def __init__(self, label, config):
    """Make several values related to this label available as attrs.

    Args:
      label: artifact label string.  E.g., 'Priority-High' or 'Frontend'.
      config: PB with a well_known_labels list, or None.
    """
    self.name = label
    self.is_restrict = ezt.boolean(permissions.IsRestrictLabel(label))

    self.docstring = ''
    if config:
      for wkl in config.well_known_labels:
        if label.lower() == wkl.label.lower():
          self.docstring = wkl.label_docstring

    if '-' in label:
      self.prefix, self.value = label.split('-', 1)
    else:
      self.prefix, self.value = '', label


class StatusView(object):
  """Wrapper class that makes it easier to display a status via EZT."""

  def __init__(self, status, config):
    """Make several values related to this status available as attrs.

    Args:
      status: artifact status string.  E.g., 'New' or 'Accepted'.
      config: PB with a well_known_statuses list, or None.
    """

    self.name = status

    self.docstring = ''
    self.means_open = ezt.boolean(True)
    if config:
      for wks in config.well_known_statuses:
        if status.lower() == wks.status.lower():
          self.docstring = wks.status_docstring
          self.means_open = ezt.boolean(wks.means_open)


class UserView(object):
  """Wrapper class to easily display basic user information in a template."""

  def __init__(self, user, is_group=False):
    self.user = user
    self.is_group = is_group
    email = user.email or ''
    self.user_id = user.user_id
    self.email = email
    if user.obscure_email:
      self.profile_url = '/u/%s/' % user.user_id
    else:
      self.profile_url = '/u/%s/' % email
    self.obscure_email = user.obscure_email
    self.banned = ''

    (self.username, self.domain,
     self.obscured_username) = ParseAndObscureAddress(email)
    # No need to obfuscate or reveal client email.
    # Instead display a human-readable username.
    if self.user_id == framework_constants.DELETED_USER_ID:
      self.display_name = framework_constants.DELETED_USER_NAME
      self.obscure_email = ''
      self.profile_url = ''
    elif self.email in client_config_svc.GetServiceAccountMap():
      self.display_name = client_config_svc.GetServiceAccountMap()[self.email]
    elif not self.obscure_email:
      self.display_name = email
    else:
      self.display_name = '%s...@%s' % (self.obscured_username, self.domain)

    self.avail_message, self.avail_state = (
        framework_helpers.GetUserAvailability(user, is_group))
    self.avail_message_short = template_helpers.FitUnsafeText(
        self.avail_message, 35)

  def RevealEmail(self):
    if not self.email:
      return
    if self.email not in client_config_svc.GetServiceAccountMap():
      self.obscure_email = False
      self.display_name = self.email
      self.profile_url = '/u/%s/' % self.email


def MakeAllUserViews(
    cnxn, user_service, *list_of_user_id_lists, **kw):
  """Make a dict {user_id: user_view, ...} for all user IDs given."""
  distinct_user_ids = set()
  distinct_user_ids.update(*list_of_user_id_lists)
  group_ids = kw.get('group_ids', [])
  user_dict = user_service.GetUsersByIDs(cnxn, distinct_user_ids)
  return {user_id: UserView(user_pb, is_group=user_id in group_ids)
          for user_id, user_pb in user_dict.items()}


def MakeUserView(cnxn, user_service, user_id):
  """Make a UserView for the given user ID."""
  user = user_service.GetUser(cnxn, user_id)
  return UserView(user)


def StuffUserView(user_id, email, obscure_email):
  """Construct a UserView with the given parameters for testing."""
  user = user_pb2.MakeUser(user_id, email=email, obscure_email=obscure_email)
  return UserView(user)


def ParseAndObscureAddress(email):
  """Break the given email into username and domain, and obscure.

  Args:
    email: string email address to process

  Returns:
    A 3-tuple (username, domain, obscured_username).
    The obscured_username is trucated the same way that Google Groups does it.
  """
  if '@' in email:
    username, user_domain = email.split('@', 1)
  else:  # don't fail if User table has unexpected email address format.
    username, user_domain = email, ''

  base_username = username.split('+')[0]
  cutoff_point = min(8, max(1, len(base_username) - 3))
  obscured_username = base_username[:cutoff_point]

  return username, user_domain, obscured_username


def _ShouldRevealEmail(auth, project, viewed_email):
  """Decide whether to publish a user's email address.

  Args:
   auth: The AuthData of the user viewing the email addresses.
   project: The project to which the viewed users belong.
   viewed_email: The email of the viewed user.

  Returns:
    True if email addresses should be published to the logged-in user.
  """
  # Case 1: Anon users don't see anything revealed.
  if auth.user_pb is None:
    return False

  # Case 2: site admins always see unobscured email addresses.
  if auth.user_pb.is_site_admin:
    return True

  # Case 3: Project members see the unobscured email of everyone in a project.
  if project and framework_bizobj.UserIsInProject(project, auth.effective_ids):
    return True

  # Case 4: Do not obscure your own email.
  if viewed_email and auth.user_pb.email == viewed_email:
    return True

  return False


def RevealAllEmailsToMembers(auth, project, users_by_id):
  """Allow project members to see unobscured email addresses in that project.

  Non project member addresses will be obscured.
  Site admins can see all email addresses unobscured.

  Args:
    auth: AuthInfo object for the signed in user.
    project: the current project.
    users_by_id: dictionary of UserView's that will be displayed.

  Returns:
    Nothing, but the UserViews in users_by_id may be modified to
    publish email address.
  """
  for user_view in users_by_id.values():
    if _ShouldRevealEmail(auth, project, user_view.email):
      user_view.RevealEmail()


def RevealAllEmails(users_by_id):
  """Allow anyone to see unobscured email addresses of project members.

  The modified view objects should only be used to generate views for other
  project members.

  Args:
    users_by_id: dictionary of UserViews that will be displayed.

  Returns:
    Nothing, but the UserViews in users_by_id may be modified to
    publish email address.
  """
  for user_view in users_by_id.values():
    user_view.RevealEmail()


def GetViewedUserDisplayName(mr):
  """Get display name of the viewed user given the logged-in user."""
  # Do not obscure email if current user is a site admin. Do not obscure
  # email if current user is viewing their own profile. For all other
  # cases do whatever obscure_email setting for the user is.
  viewing_self = mr.auth.user_id == mr.viewed_user_auth.user_id
  email_obscured = (not(mr.auth.user_pb.is_site_admin or viewing_self)
                    and mr.viewed_user_auth.user_view.obscure_email)
  if email_obscured:
    _, domain, obscured_username = ParseAndObscureAddress(
        mr.viewed_user_auth.email)
    viewed_user_display_name = '%s...@%s' % (obscured_username, domain)
  else:
    viewed_user_display_name = mr.viewed_user_auth.email

  return viewed_user_display_name
