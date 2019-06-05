# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions and classes used by the project pages."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import re

import settings
from framework import framework_bizobj
from framework import framework_views
from framework import permissions
from project import project_views
from proto import project_pb2


_RE_EMAIL_SEPARATORS = re.compile(r'\s|,|;')


def BuildProjectMembers(cnxn, project, user_service):
  """Gather data for the members section of a project page.

  Args:
    cnxn: connection to SQL database.
    project: Project PB of current project.
    user_service: an instance of UserService for user persistence.

  Returns:
    A dictionary suitable for use with EZT.
  """
  # First, get all needed info on all users in one batch of requests.
  users_by_id = framework_views.MakeAllUserViews(
      cnxn, user_service, framework_bizobj.AllProjectMembers(project))

  # Second, group the user proxies by role for display.
  owner_proxies = [users_by_id[owner_id]
                   for owner_id in project.owner_ids]
  committer_proxies = [users_by_id[committer_id]
                       for committer_id in project.committer_ids]
  contributor_proxies = [users_by_id[contrib_id]
                         for contrib_id in project.contributor_ids]

  return {
      'owners': owner_proxies,
      'committers': committer_proxies,
      'contributors': contributor_proxies,
      'all_members': users_by_id.values(),
      }


def BuildProjectAccessOptions(project):
  """Return a list of project access values for use in an HTML menu.

  Args:
    project: current Project PB, or None when creating a new project.

  Returns:
    A list of ProjectAccessView objects that can be used in EZT.
  """
  access_levels = [project_pb2.ProjectAccess.ANYONE,
                   project_pb2.ProjectAccess.MEMBERS_ONLY]
  access_views = []
  for access in access_levels:
    # Offer the allowed access levels.  When editing an existing project,
    # its current access level may always be kept, even if it is no longer
    # in the list of allowed access levels for new projects.
    if (access in settings.allowed_access_levels or
        (project and access == project.access)):
      access_views.append(project_views.ProjectAccessView(access))

  return access_views


def ParseUsernames(cnxn, user_service, usernames_text):
  """Parse all usernames from a text field and return a list of user IDs.

  Args:
    cnxn: connection to SQL database.
    user_service: an instance of UserService for user persistence.
    usernames_text: string that the user entered into a form field for a list
        of email addresses.  Or, None if the browser did not send that value.

  Returns:
    A set of user IDs for the users named.  Or, an empty set if the
    usernames_field was not in post_data.
  """
  if not usernames_text:  # The user did not enter any addresses.
    return set()

  email_list = _RE_EMAIL_SEPARATORS.split(usernames_text)
  # skip empty strings between consecutive separators
  email_list = [email for email in email_list if email]

  id_dict = user_service.LookupUserIDs(cnxn, email_list, autocreate=True)
  return set(id_dict.values())


def ParseProjectAccess(project, access_num_str):
  """Parse and validate the "access" field out of post_data.

  Args:
    project: Project PB for the project that was edited, or None if the
        user is creating a new project.
    access_num_str: string of digits from the users POST that identifies
       the desired project access level.  Or, None if that widget was not
       offered to the user.

  Returns:
    An enum project access level, or None if the user did not specify
    any value or if the value specified was invalid.
  """
  access = None
  if access_num_str:
    access_number = int(access_num_str)
    available_access_levels = BuildProjectAccessOptions(project)
    allowed_access_choices = [access_view.key for access_view
                              in available_access_levels]
    if access_number in allowed_access_choices:
      access = project_pb2.ProjectAccess(access_number)

  return access


def MembersWithoutGivenIDs(project, exclude_ids):
  """Return three lists of member user IDs, with member_ids not in them."""
  owner_ids = [user_id for user_id in project.owner_ids
               if user_id not in exclude_ids]
  committer_ids = [user_id for user_id in project.committer_ids
                   if user_id not in exclude_ids]
  contributor_ids = [user_id for user_id in project.contributor_ids
                     if user_id not in exclude_ids]

  return owner_ids, committer_ids, contributor_ids


def MembersWithGivenIDs(project, new_member_ids, role):
  """Return three lists of member IDs with the new IDs in the right one.

  Args:
    project: Project PB for the project to get current members from.
    new_member_ids: set of user IDs for members being added.
    role: string name of the role that new_member_ids should be granted.

  Returns:
    Three lists of member IDs with new_member_ids added to the appropriate
    list and removed from any other role.

  Raises:
    ValueError: if the role is not one of owner, committer, or contributor.
  """
  owner_ids, committer_ids, contributor_ids = MembersWithoutGivenIDs(
      project, new_member_ids)

  if role == 'owner':
    owner_ids.extend(new_member_ids)
  elif role == 'committer':
    committer_ids.extend(new_member_ids)
  elif role == 'contributor':
    contributor_ids.extend(new_member_ids)
  else:
    raise ValueError()

  return owner_ids, committer_ids, contributor_ids


def UsersInvolvedInProject(project):
  """Return a set of all user IDs referenced in the Project."""
  result = set()
  result.update(project.owner_ids)
  result.update(project.committer_ids)
  result.update(project.contributor_ids)
  result.update([perm.member_id for perm in project.extra_perms])
  return result


def UsersWithPermsInProject(project, perms_needed, users_by_id,
                            effective_ids_by_user):
  # Users that have the given permission are stored in direct_users_for_perm,
  # users whose effective ids have the given permission are stored in
  # indirect_users_for_perm.
  direct_users_for_perm = {perm: set() for perm in perms_needed}
  indirect_users_for_perm = {perm: set() for perm in perms_needed}

  # Iterate only over users that have extra permissions, so we don't
  # have to search the extra perms more than once for each user.
  for extra_perm_pb in project.extra_perms:
    extra_perms = set(perm.lower() for perm in extra_perm_pb.perms)
    for perm, users in direct_users_for_perm.iteritems():
      if perm.lower() in extra_perms:
        users.add(extra_perm_pb.member_id)

  # Then, iterate over all users, but don't compute extra permissions.
  for user_id, user_view in users_by_id.iteritems():
    effective_ids = effective_ids_by_user[user_id].union([user_id])
    user_perms = permissions.GetPermissions(
        user_view.user, effective_ids, project)
    for perm, users in direct_users_for_perm.iteritems():
      if not effective_ids.isdisjoint(users):
        indirect_users_for_perm[perm].add(user_id)
      if user_perms.HasPerm(perm, None, None, []):
        users.add(user_id)

  for perm, users in direct_users_for_perm.iteritems():
    users.update(indirect_users_for_perm[perm])

  return direct_users_for_perm
