# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""View classes to make it easy to display framework objects in EZT."""

from third_party import ezt

from framework import framework_bizobj
from framework import framework_constants
from framework import permissions
from framework import template_helpers
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
    self.tooltip = label
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
    self.tooltip = status

    self.docstring = ''
    self.means_open = ezt.boolean(True)
    if config:
      for wks in config.well_known_statuses:
        if status.lower() == wks.status.lower():
          self.docstring = wks.status_docstring
          self.means_open = ezt.boolean(wks.means_open)


class UserView(object):
  """Wrapper class to easily display basic user information in a template."""

  def __init__(self, user_id, email, obscure_email):
    email = email or ''
    self.user_id = user_id
    self.email = email
    self.profile_url = '/u/%s/' % user_id
    self.obscure_email = obscure_email
    self.banned = ''

    (self.username, self.domain,
     self.obscured_username) = ParseAndObscureAddress(email)
    # No need to obfuscate or reveal client email.
    # Instead display a human-readable username.
    if not self.email:
      self.display_name = 'a deleted user'
      self.obscure_email = ''
      self.profile_url = ''
    elif self.email in client_config_svc.GetServiceAccountMap():
      self.display_name = client_config_svc.GetServiceAccountMap()[self.email]
    elif not self.obscure_email:
      self.display_name = email
    else:
      self.display_name = '%s...@%s' % (self.obscured_username, self.domain)

  def RevealEmail(self):
    if not self.email:
      return
    if self.email not in client_config_svc.GetServiceAccountMap():
      self.obscure_email = False
      self.display_name = self.email
      self.profile_url = '/u/%s/' % self.email


def MakeAllUserViews(cnxn, user_service, *list_of_user_id_lists):
  """Make a dict {user_id: user_view, ...} for all user IDs given."""
  distinct_user_ids = set()
  distinct_user_ids.update(*list_of_user_id_lists)
  user_dict = user_service.GetUsersByIDs(cnxn, distinct_user_ids)
  return {user_id: UserView(user_id, user_pb.email, user_pb.obscure_email)
          for user_id, user_pb in user_dict.iteritems()}


def MakeUserView(cnxn, user_service, user_id):
  """Make a UserView for the given user ID."""
  user = user_service.GetUser(cnxn, user_id)
  return UserView(user_id, user.email, user.obscure_email)


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

  # Case 3: Domain users in same-org-only projects always see unobscured addrs.
  # TODO(jrobbins): re-implement same_org

  # Case 4: Project members see the unobscured email of everyone in a project.
  if project and framework_bizobj.UserIsInProject(project, auth.effective_ids):
    return True

  # Case 5: Emails that end in priviledged user domains see unobscured email
  #         addresses.
  if framework_bizobj.IsPriviledgedDomainUser(auth.user_pb.email):
    return True

  # Case 6: Do not obscure your own email.
  if viewed_email and auth.user_pb.email == viewed_email:
    return True

  return False


def RevealAllEmailsToMembers(mr, users_by_id):
  """Allow project members to see unobscured email addresses in that project.

  Non project member addresses will be obscured.
  Site admins can see all email addresses unobscured.

  Args:
    mr: common info parsed from the user's request.
    users_by_id: dictionary of UserView's that will be displayed.

  Returns:
    Nothing, but the UserViews in users_by_id may be modified to
    publish email address.
  """
  for user_view in users_by_id.itervalues():
    if _ShouldRevealEmail(mr.auth, mr.project, user_view.email):
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
  for user_view in users_by_id.itervalues():
    user_view.RevealEmail()
