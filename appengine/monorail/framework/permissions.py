# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes and functions to implement permission checking.

The main data structure is a simple map from (user role, project status,
project_access_level) to specific perms.

A perm is simply a string that indicates that the user has a given
permission.  The servlets and templates can test whether the current
user has permission to see a UI element or perform an action by
testing for the presence of the corresponding perm in the user's
permission set.

The user role is one of admin, owner, member, outsider user, or anon.
The project status is one of the project states defined in project_pb2,
or a special constant defined below.  Likewise for access level.
"""

import logging
import time

from third_party import ezt

import settings
from framework import framework_bizobj
from framework import framework_constants
from proto import project_pb2
from proto import site_pb2
from proto import tracker_pb2
from proto import usergroup_pb2
from tracker import tracker_bizobj

# Constants that define permissions.
# Note that perms with a leading "_" can never be granted
# to users who are not site admins.
VIEW = 'View'
EDIT_PROJECT = 'EditProject'
CREATE_PROJECT = 'CreateProject'
PUBLISH_PROJECT = '_PublishProject'  # for making "doomed" projects LIVE
VIEW_DEBUG = '_ViewDebug'  # on-page debugging info
EDIT_OTHER_USERS = '_EditOtherUsers'  # can edit other user's prefs, ban, etc.
CUSTOMIZE_PROCESS = 'CustomizeProcess'  # can use some enterprise features
VIEW_EXPIRED_PROJECT = '_ViewExpiredProject'  # view long-deleted projects
# View the list of contributors even in hub-and-spoke projects.
VIEW_CONTRIBUTOR_LIST = 'ViewContributorList'

# Quota
VIEW_QUOTA = 'ViewQuota'
EDIT_QUOTA = 'EditQuota'

# Permissions for editing user groups
CREATE_GROUP = 'CreateGroup'
EDIT_GROUP = 'EditGroup'
DELETE_GROUP = 'DeleteGroup'
VIEW_GROUP = 'ViewGroup'

# Perms for Source tools
# TODO(jrobbins): Monorail is just issue tracking with no version control, so
# phase out use of the term "Commit", sometime after Monorail's initial launch.
COMMIT = 'Commit'

# Perms for issue tracking
CREATE_ISSUE = 'CreateIssue'
EDIT_ISSUE = 'EditIssue'
EDIT_ISSUE_OWNER = 'EditIssueOwner'
EDIT_ISSUE_SUMMARY = 'EditIssueSummary'
EDIT_ISSUE_STATUS = 'EditIssueStatus'
EDIT_ISSUE_CC = 'EditIssueCc'
DELETE_ISSUE = 'DeleteIssue'
ADD_ISSUE_COMMENT = 'AddIssueComment'
VIEW_INBOUND_MESSAGES = 'ViewInboundMessages'
CREATE_HOTLIST = 'CreateHotlist'
# Note, there is no separate DELETE_ATTACHMENT perm.  We
# allow a user to delete an attachment iff they could soft-delete
# the comment that holds the attachment.

# Note: the "_" in the perm name makes it impossible for a
# project owner to grant it to anyone as an extra perm.
ADMINISTER_SITE = '_AdministerSite'

# Permissions to soft-delete artifact comment
DELETE_ANY = 'DeleteAny'
DELETE_OWN = 'DeleteOwn'

# Granting this allows owners to delegate some team management work.
EDIT_ANY_MEMBER_NOTES = 'EditAnyMemberNotes'

# Permission to star/unstar any artifact.
SET_STAR = 'SetStar'

# Permission to flag any artifact as spam.
FLAG_SPAM = 'FlagSpam'
VERDICT_SPAM = 'VerdictSpam'
MODERATE_SPAM = 'ModerateSpam'

RESTRICTED_APPROVAL_STATUSES = [
    tracker_pb2.ApprovalStatus.NA, tracker_pb2.ApprovalStatus.REVIEW_STARTED,
    tracker_pb2.ApprovalStatus.APPROVED, tracker_pb2.ApprovalStatus.NEEDS_REVIEW,
    tracker_pb2.ApprovalStatus.NOT_APPROVED]

STANDARD_ADMIN_PERMISSIONS = [
    EDIT_PROJECT, CREATE_PROJECT, PUBLISH_PROJECT, VIEW_DEBUG,
    EDIT_OTHER_USERS, CUSTOMIZE_PROCESS,
    VIEW_QUOTA, EDIT_QUOTA, ADMINISTER_SITE,
    EDIT_ANY_MEMBER_NOTES, VERDICT_SPAM, MODERATE_SPAM]

STANDARD_ISSUE_PERMISSIONS = [
    VIEW, EDIT_ISSUE, ADD_ISSUE_COMMENT, DELETE_ISSUE, FLAG_SPAM]

# Monorail has no source control, but keep COMMIT for backward compatability.
STANDARD_SOURCE_PERMISSIONS = [COMMIT]

STANDARD_COMMENT_PERMISSIONS = [DELETE_OWN, DELETE_ANY]

STANDARD_OTHER_PERMISSIONS = [CREATE_ISSUE, FLAG_SPAM, SET_STAR]

STANDARD_PERMISSIONS = (STANDARD_ADMIN_PERMISSIONS +
                        STANDARD_ISSUE_PERMISSIONS +
                        STANDARD_SOURCE_PERMISSIONS +
                        STANDARD_COMMENT_PERMISSIONS +
                        STANDARD_OTHER_PERMISSIONS)

# roles
SITE_ADMIN_ROLE = 'admin'
OWNER_ROLE = 'owner'
COMMITTER_ROLE = 'committer'
CONTRIBUTOR_ROLE = 'contributor'
USER_ROLE = 'user'
ANON_ROLE = 'anon'

# Project state out-of-band values for keys
UNDEFINED_STATUS = 'undefined_status'
UNDEFINED_ACCESS = 'undefined_access'
WILDCARD_ACCESS = 'wildcard_access'


class PermissionSet(object):
  """Class to represent the set of permissions available to the user."""

  def __init__(self, perm_names, consider_restrictions=True):
    """Create a PermissionSet with the given permissions.

    Args:
      perm_names: a list of permission name strings.
      consider_restrictions: if true, the user's permissions can be blocked
          by restriction labels on an artifact.  Project owners and site
          admins do not consider restrictions so that they cannot
          "lock themselves out" of editing an issue.
    """
    self.perm_names = frozenset(p.lower() for p in perm_names)
    self.consider_restrictions = consider_restrictions

  def __getattr__(self, perm_name):
    """Easy permission testing in EZT.  E.g., [if-any perms.format_drive]."""
    return ezt.boolean(self.HasPerm(perm_name, None, None))

  def CanUsePerm(
      self, perm_name, effective_ids, project, restriction_labels,
      granted_perms=None):
    """Return True if the user can use the given permission.

    Args:
      perm_name: string name of permission, e.g., 'EditIssue'.
      effective_ids: set of int user IDs for the user (including any groups),
          or an empty set if user is not signed in.
      project: Project PB for the project being accessed, or None if not
          in a project.
      restriction_labels: list of strings that restrict permission usage.
      granted_perms: optional list of lowercase strings of permissions that the
          user is granted only within the scope of one issue, e.g., by being
          named in a user-type custom field that grants permissions.

    Restriction labels have 3 parts, e.g.:
    'Restrict-EditIssue-InnerCircle' blocks the use of just the
    EditIssue permission, unless the user also has the InnerCircle
    permission.  This allows fine-grained restrictions on specific
    actions, such as editing, commenting, or deleting.

    Restriction labels and permissions are case-insensitive.

    Returns:
      True if the user can use the given permission, or False
      if they cannot (either because they don't have that permission
      or because it is blocked by a relevant restriction label).
    """
    # TODO(jrobbins): room for performance improvement: avoid set creation and
    # repeated string operations.
    granted_perms = granted_perms or set()
    perm_lower = perm_name.lower()
    if perm_lower in granted_perms:
      return True

    needed_perms = {perm_lower}
    if self.consider_restrictions:
      for label in restriction_labels:
        label = label.lower()
        # format: Restrict-Action-ToThisPerm
        _kw, requested_perm, needed_perm = label.split('-', 2)
        if requested_perm == perm_lower and needed_perm not in granted_perms:
          needed_perms.add(needed_perm)

    if not effective_ids:
      effective_ids = {framework_constants.NO_USER_SPECIFIED}
    # Id X might have perm A and Y might have B, if both A and B are needed
    # True should be returned.
    for perm in needed_perms:
      if not any(
          self.HasPerm(perm, user_id, project) for user_id in effective_ids):
        return False

    return True

  def HasPerm(self, perm_name, user_id, project):
    """Return True if the user has the given permission (ignoring user groups).

    Args:
      perm_name: string name of permission, e.g., 'EditIssue'.
      user_id: int user id of the user, or None if user is not signed in.
      project: Project PB for the project being accessed, or None if not
          in a project.

    Returns:
      True if the user has the given perm.
    """
    # TODO(jrobbins): room for performance improvement: pre-compute
    # extra perms (maybe merge them into the perms object), avoid
    # redundant call to lower().
    extra_perms = [p.lower() for p in GetExtraPerms(project, user_id)]
    perm_name = perm_name.lower()
    return perm_name in self.perm_names or perm_name in extra_perms

  def DebugString(self):
    """Return a useful string to show when debugging."""
    return 'PermissionSet(%s)' % ', '.join(sorted(self.perm_names))

  def __repr__(self):
    return '%s(%r)' % (self.__class__.__name__, self.perm_names)


EMPTY_PERMISSIONSET = PermissionSet([])

READ_ONLY_PERMISSIONSET = PermissionSet([VIEW])

USER_PERMISSIONSET = PermissionSet([
    VIEW, FLAG_SPAM, SET_STAR,
    CREATE_ISSUE, ADD_ISSUE_COMMENT,
    DELETE_OWN])

CONTRIBUTOR_ACTIVE_PERMISSIONSET = PermissionSet(
    [VIEW,
     FLAG_SPAM, VERDICT_SPAM, SET_STAR,
     CREATE_ISSUE, ADD_ISSUE_COMMENT,
     DELETE_OWN])

CONTRIBUTOR_INACTIVE_PERMISSIONSET = PermissionSet(
    [VIEW])

COMMITTER_ACTIVE_PERMISSIONSET = PermissionSet(
    [VIEW, COMMIT, VIEW_CONTRIBUTOR_LIST,
     FLAG_SPAM, VERDICT_SPAM, SET_STAR, VIEW_QUOTA,
     CREATE_ISSUE, ADD_ISSUE_COMMENT, EDIT_ISSUE, VIEW_INBOUND_MESSAGES,
     DELETE_OWN])

COMMITTER_INACTIVE_PERMISSIONSET = PermissionSet(
    [VIEW, VIEW_CONTRIBUTOR_LIST,
     VIEW_INBOUND_MESSAGES, VIEW_QUOTA])

OWNER_ACTIVE_PERMISSIONSET = PermissionSet(
    [VIEW, VIEW_CONTRIBUTOR_LIST, EDIT_PROJECT, COMMIT,
     FLAG_SPAM, VERDICT_SPAM, SET_STAR, VIEW_QUOTA,
     CREATE_ISSUE, ADD_ISSUE_COMMENT, EDIT_ISSUE, DELETE_ISSUE,
     VIEW_INBOUND_MESSAGES,
     DELETE_ANY, EDIT_ANY_MEMBER_NOTES],
    consider_restrictions=False)

OWNER_INACTIVE_PERMISSIONSET = PermissionSet(
    [VIEW, VIEW_CONTRIBUTOR_LIST, EDIT_PROJECT,
     VIEW_INBOUND_MESSAGES, VIEW_QUOTA],
    consider_restrictions=False)

ADMIN_PERMISSIONSET = PermissionSet(
    [VIEW, VIEW_CONTRIBUTOR_LIST,
     CREATE_PROJECT, EDIT_PROJECT, PUBLISH_PROJECT, VIEW_DEBUG,
     COMMIT, CUSTOMIZE_PROCESS, FLAG_SPAM, VERDICT_SPAM, SET_STAR,
     ADMINISTER_SITE, VIEW_EXPIRED_PROJECT, EDIT_OTHER_USERS,
     VIEW_QUOTA, EDIT_QUOTA,
     CREATE_ISSUE, ADD_ISSUE_COMMENT, EDIT_ISSUE, DELETE_ISSUE,
     VIEW_INBOUND_MESSAGES,
     DELETE_ANY, EDIT_ANY_MEMBER_NOTES,
     CREATE_GROUP, EDIT_GROUP, DELETE_GROUP, VIEW_GROUP,
     MODERATE_SPAM, CREATE_HOTLIST],
     consider_restrictions=False)

GROUP_IMPORT_BORG_PERMISSIONSET = PermissionSet(
    [CREATE_GROUP, VIEW_GROUP, EDIT_GROUP])

# Permissions for project pages, e.g., the project summary page
_PERMISSIONS_TABLE = {

    # Project owners can view and edit artifacts in a LIVE project.
    (OWNER_ROLE, project_pb2.ProjectState.LIVE, WILDCARD_ACCESS):
      OWNER_ACTIVE_PERMISSIONSET,

    # Project owners can view, but not edit artifacts in ARCHIVED.
    # Note: EDIT_PROJECT is not enough permission to change an ARCHIVED project
    # back to LIVE if a delete_time was set.
    (OWNER_ROLE, project_pb2.ProjectState.ARCHIVED, WILDCARD_ACCESS):
      OWNER_INACTIVE_PERMISSIONSET,

    # Project members can view their own project, regardless of state.
    (COMMITTER_ROLE, project_pb2.ProjectState.LIVE, WILDCARD_ACCESS):
      COMMITTER_ACTIVE_PERMISSIONSET,
    (COMMITTER_ROLE, project_pb2.ProjectState.ARCHIVED, WILDCARD_ACCESS):
      COMMITTER_INACTIVE_PERMISSIONSET,

    # Project contributors can view their own project, regardless of state.
    (CONTRIBUTOR_ROLE, project_pb2.ProjectState.LIVE, WILDCARD_ACCESS):
      CONTRIBUTOR_ACTIVE_PERMISSIONSET,
    (CONTRIBUTOR_ROLE, project_pb2.ProjectState.ARCHIVED, WILDCARD_ACCESS):
      CONTRIBUTOR_INACTIVE_PERMISSIONSET,

    # Non-members users can read and comment in projects with access == ANYONE
    (USER_ROLE, project_pb2.ProjectState.LIVE,
     project_pb2.ProjectAccess.ANYONE):
      USER_PERMISSIONSET,

    # Anonymous users can only read projects with access == ANYONE.
    (ANON_ROLE, project_pb2.ProjectState.LIVE,
     project_pb2.ProjectAccess.ANYONE):
      READ_ONLY_PERMISSIONSET,

    # Permissions for site pages, e.g., creating a new project
    (USER_ROLE, UNDEFINED_STATUS, UNDEFINED_ACCESS):
      PermissionSet([CREATE_PROJECT, CREATE_GROUP, CREATE_HOTLIST]),
    }

def GetPermissions(user, effective_ids, project):
  """Return a permission set appropriate for the user and project.

  Args:
    user: The User PB for the signed-in user, or None for anon users.
    effective_ids: set of int user IDs for the current user and all user
        groups that s/he is a member of.  This will be an empty set for
        anonymous users.
    project: either a Project protobuf, or None for a page whose scope is
        wider than a single project.

  Returns:
    a PermissionSet object for the current user and project (or for
    site-wide operations if project is None).

  If an exact match for the user's role and project status is found, that is
  returned. Otherwise, we look for permissions for the user's role that is
  not specific to any project status, or not specific to any project access
  level.  If neither of those are defined, we give the user an empty
  permission set.
  """
  # Site admins get ADMIN_PERMISSIONSET regardless of groups or projects.
  if user and user.is_site_admin:
    return ADMIN_PERMISSIONSET

  # Grant the borg job permission to view/edit groups
  if user and user.email == settings.borg_service_account:
    return GROUP_IMPORT_BORG_PERMISSIONSET

  # Anon users don't need to accumulate anything.
  if not effective_ids:
    role, status, access = _GetPermissionKey(None, project)
    return _LookupPermset(role, status, access)

  effective_perms = set()
  consider_restrictions = True

  # Check for signed-in user with no roles in the current project.
  if not project or not framework_bizobj.UserIsInProject(
      project, effective_ids):
    role, status, access = _GetPermissionKey(None, project)
    return _LookupPermset(USER_ROLE, status, access)

  # Signed-in user gets the union of all his/her PermissionSets from the table.
  for user_id in effective_ids:
    role, status, access = _GetPermissionKey(user_id, project)
    role_perms = _LookupPermset(role, status, access)
    # Accumulate a union of all the user's permissions.
    effective_perms.update(role_perms.perm_names)
    # If any role allows the user to ignore restriction labels, then
    # ignore them overall.
    if not role_perms.consider_restrictions:
      consider_restrictions = False

  return PermissionSet(
      effective_perms, consider_restrictions=consider_restrictions)


def _LookupPermset(role, status, access):
  """Lookup the appropriate PermissionSet in _PERMISSIONS_TABLE.

  Args:
    role: a string indicating the user's role in the project.
    status: a Project PB status value, or UNDEFINED_STATUS.
    access: a Project PB access value, or UNDEFINED_ACCESS.

  Returns:
    A PermissionSet that is appropriate for that kind of user in that
    project context.
  """
  if (role, status, access) in _PERMISSIONS_TABLE:
    return _PERMISSIONS_TABLE[(role, status, access)]
  elif (role, status, WILDCARD_ACCESS) in _PERMISSIONS_TABLE:
    return _PERMISSIONS_TABLE[(role, status, WILDCARD_ACCESS)]
  else:
    return EMPTY_PERMISSIONSET


def _GetPermissionKey(user_id, project, expired_before=None):
  """Return a permission lookup key appropriate for the user and project."""
  if user_id is None:
    role = ANON_ROLE
  elif project and IsExpired(project, expired_before=expired_before):
    role = USER_ROLE  # Do not honor roles in expired projects.
  elif project and user_id in project.owner_ids:
    role = OWNER_ROLE
  elif project and user_id in project.committer_ids:
    role = COMMITTER_ROLE
  elif project and user_id in project.contributor_ids:
    role = CONTRIBUTOR_ROLE
  else:
    role = USER_ROLE

  # TODO(jrobbins): re-implement same_org

  if project is None:
    status = UNDEFINED_STATUS
  else:
    status = project.state

  if project is None:
    access = UNDEFINED_ACCESS
  else:
    access = project.access

  return role, status, access


def GetExtraPerms(project, member_id):
  """Return a list of extra perms for the user in the project.

  Args:
    project: Project PB for the current project.
    member_id: user id of a project owner, member, or contributor.

  Returns:
    A list of strings for the extra perms granted to the
    specified user in this project.  The list will often be empty.
  """

  extra_perms = FindExtraPerms(project, member_id)

  if extra_perms:
    return list(extra_perms.perms)
  else:
    return []


def FindExtraPerms(project, member_id):
  """Return a ExtraPerms PB for the given user in the project.

  Args:
    project: Project PB for the current project, or None if the user is
      not currently in a project.
    member_id: user ID of a project owner, member, or contributor.

  Returns:
    An ExtraPerms PB, or None.
  """
  if not project:
    # TODO(jrobbins): maybe define extra perms for site-wide operations.
    return None

  # Users who have no current role cannot have any extra perms.  Don't
  # consider effective_ids (which includes user groups) for this check.
  if not framework_bizobj.UserIsInProject(project, {member_id}):
    return None

  for extra_perms in project.extra_perms:
    if extra_perms.member_id == member_id:
      return extra_perms

  return None


def GetCustomPermissions(project):
  """Return a sorted iterable of custom perms granted in a project."""
  custom_permissions = set()
  for extra_perms in project.extra_perms:
    for perm in extra_perms.perms:
      if perm not in STANDARD_PERMISSIONS:
        custom_permissions.add(perm)

  return sorted(custom_permissions)


def UserCanViewProject(user, effective_ids, project, expired_before=None):
  """Return True if the user can view the given project.

  Args:
    user: User protobuf for the user trying to view the project.
    effective_ids: set of int user IDs of the user trying to view the project
        (including any groups), or an empty set for anonymous users.
    project: the Project protobuf to check.
    expired_before: option time value for testing.

  Returns:
    True if the user should be allowed to view the project.
  """
  perms = GetPermissions(user, effective_ids, project)

  if IsExpired(project, expired_before=expired_before):
    needed_perm = VIEW_EXPIRED_PROJECT
  else:
    needed_perm = VIEW

  return perms.CanUsePerm(needed_perm, effective_ids, project, [])


def IsExpired(project, expired_before=None):
  """Return True if a project deletion has been pending long enough already.

  Args:
    project: The project being viewed.
    expired_before: If supplied, this method will return True only if the
      project expired before the given time.

  Returns:
    True if the project is eligible for reaping.
  """
  if project.state != project_pb2.ProjectState.ARCHIVED:
    return False

  if expired_before is None:
    expired_before = int(time.time())

  return project.delete_time and project.delete_time < expired_before


def CanDelete(logged_in_user_id, effective_ids, perms, deleted_by_user_id,
              creator_user_id, project, restrictions, granted_perms=None):
  """Returns true if user has delete permission.

  Args:
    logged_in_user_id: int user id of the logged in user.
    effective_ids: set of int user IDs for the user (including any groups),
        or an empty set if user is not signed in.
    perms: instance of PermissionSet describing the current user's permissions.
    deleted_by_user_id: int user ID of the user having previously deleted this
        comment, or None, if the comment has never been deleted.
    creator_user_id: int user ID of the user having created this comment.
    project: Project PB for the project being accessed, or None if not
        in a project.
    restrictions: list of strings that restrict permission usage.
    granted_perms: optional list of strings of permissions that the user is
        granted only within the scope of one issue, e.g., by being named in
        a user-type custom field that grants permissions.

  Returns:
    True if the logged in user has delete permissions.
  """

  # User is not logged in or has no permissions.
  if not logged_in_user_id or not perms:
    return False

  # Site admin or project owners can delete any comment.
  permit_delete_any = perms.CanUsePerm(
      DELETE_ANY, effective_ids, project, restrictions,
      granted_perms=granted_perms)
  if permit_delete_any:
    return True

  # Users cannot undelete unless they deleted.
  if deleted_by_user_id and deleted_by_user_id != logged_in_user_id:
    return False

  # Users can delete their own items.
  permit_delete_own = perms.CanUsePerm(
      DELETE_OWN, effective_ids, project, restrictions)
  if permit_delete_own and creator_user_id == logged_in_user_id:
    return True

  return False


def CanView(effective_ids, perms, project, restrictions, granted_perms=None):
  """Checks if user has permission to view an issue."""
  return perms.CanUsePerm(
      VIEW, effective_ids, project, restrictions, granted_perms=granted_perms)


def CanCreateProject(perms):
  """Return True if the given user may create a project.

  Args:
    perms: Permissionset for the current user.

  Returns:
    True if the user should be allowed to create a project.
  """
  # "ANYONE" means anyone who has the needed perm.
  if (settings.project_creation_restriction ==
      site_pb2.UserTypeRestriction.ANYONE):
    return perms.HasPerm(CREATE_PROJECT, None, None)

  if (settings.project_creation_restriction ==
      site_pb2.UserTypeRestriction.ADMIN_ONLY):
    return perms.HasPerm(ADMINISTER_SITE, None, None)

  return False


def CanCreateGroup(perms):
  """Return True if the given user may create a user group.

  Args:
    perms: Permissionset for the current user.

  Returns:
    True if the user should be allowed to create a group.
  """
  # "ANYONE" means anyone who has the needed perm.
  if (settings.group_creation_restriction ==
      site_pb2.UserTypeRestriction.ANYONE):
    return perms.HasPerm(CREATE_GROUP, None, None)

  if (settings.group_creation_restriction ==
      site_pb2.UserTypeRestriction.ADMIN_ONLY):
    return perms.HasPerm(ADMINISTER_SITE, None, None)

  return False


def CanEditGroup(perms, effective_ids, group_owner_ids):
  """Return True if the given user may edit a user group.

  Args:
    perms: Permissionset for the current user.
    effective_ids: set of user IDs for the logged in user.
    group_owner_ids: set of user IDs of the user group owners.

  Returns:
    True if the user should be allowed to edit the group.
  """
  return (perms.HasPerm(EDIT_GROUP, None, None) or
          not effective_ids.isdisjoint(group_owner_ids))


def CanViewGroup(perms, effective_ids, group_settings, member_ids, owner_ids,
                 user_project_ids):
  """Return True if the given user may view a user group.

  Args:
    perms: Permissionset for the current user.
    effective_ids: set of user IDs for the logged in user.
    group_settings: PB of UserGroupSettings.
    member_ids: A list of member ids of this user group.
    owner_ids: A list of owner ids of this user group.
    user_project_ids: A list of project ids which the user has a role.

  Returns:
    True if the user should be allowed to view the group.
  """
  if perms.HasPerm(VIEW_GROUP, None, None):
    return True
  # The user could view this group with membership of some projects which are
  # friends of the group.
  if (group_settings.friend_projects and user_project_ids
      and (set(group_settings.friend_projects) & set(user_project_ids))):
    return True
  visibility = group_settings.who_can_view_members
  if visibility == usergroup_pb2.MemberVisibility.OWNERS:
    return not effective_ids.isdisjoint(owner_ids)
  elif visibility == usergroup_pb2.MemberVisibility.MEMBERS:
    return (not effective_ids.isdisjoint(member_ids) or
            not effective_ids.isdisjoint(owner_ids))
  else:
    return True


def IsBanned(user, user_view):
  """Return True if this user is banned from using our site."""
  if user is None:
    return False  # Anyone is welcome to browse

  if user.banned:
    return True  # We checked the "Banned" checkbox for this user.

  if user_view:
    if user_view.domain in settings.banned_user_domains:
      return True  # Some spammers create many accounts with the same domain.

  if '+' in (user.email or ''):
    # Spammers can make plus-addr Google accounts in unexpected domains.
    return True

  return False


def CanBan(mr, services):
  """Return True if the user is allowed to ban other users, site-wide."""
  if mr.perms.HasPerm(ADMINISTER_SITE, None, None):
    return True

  owned, _, _ = services.project.GetUserRolesInAllProjects(mr.cnxn,
      mr.auth.effective_ids)
  return len(owned) > 0

def CanViewContributorList(mr):
  """Return True if we should display the list project contributors.

  This is used on the project summary page, when deciding to offer the
  project People page link, and when generating autocomplete options
  that include project members.

  Args:
    mr: commonly used info parsed from the request.

  Returns:
    True if we should display the project contributor list.
  """
  if not mr.project:
    return False  # We are not even in a project context.

  if not mr.project.only_owners_see_contributors:
    return True  # Contributor list is not resticted.

  # If it is hub-and-spoke, check for the perm that allows the user to
  # view it anyway.
  return mr.perms.HasPerm(
      VIEW_CONTRIBUTOR_LIST, mr.auth.user_id, mr.project)


def ShouldCheckForAbandonment(mr):
  """Return True if user should be warned before changing/deleting their role.

  Args:
    mr: common info parsed from the user's request.

  Returns:
    True if user should be warned before changing/deleting their role.
  """
  # Note: No need to warn admins because they won't lose access anyway.
  if mr.perms.CanUsePerm(
      ADMINISTER_SITE, mr.auth.effective_ids, mr.project, []):
    return False

  return mr.perms.CanUsePerm(
      EDIT_PROJECT, mr.auth.effective_ids, mr.project, [])


# For speed, we remember labels that we have already classified as being
# restriction labels or not being restriction labels.  These sets are for
# restrictions in general, not for any particular perm.
_KNOWN_RESTRICTION_LABELS = set()
_KNOWN_NON_RESTRICTION_LABELS = set()


def IsRestrictLabel(label, perm=''):
  """Returns True if a given label is a restriction label.

  Args:
    label: string for the label to examine.
    perm: a permission that can be restricted (e.g. 'View' or 'Edit').
        Defaults to '' to mean 'any'.

  Returns:
    True if a given label is a restriction label (of the specified perm)
  """
  if label in _KNOWN_NON_RESTRICTION_LABELS:
    return False
  if not perm and label in _KNOWN_RESTRICTION_LABELS:
    return True

  prefix = ('restrict-%s-' % perm.lower()) if perm else 'restrict-'
  is_restrict = label.lower().startswith(prefix) and label.count('-') >= 2

  if is_restrict:
    _KNOWN_RESTRICTION_LABELS.add(label)
  elif not perm:
    _KNOWN_NON_RESTRICTION_LABELS.add(label)

  return is_restrict


def HasRestrictions(issue, perm=''):
  """Return True if the issue has any restrictions (on the specified perm)."""
  return (
      any(IsRestrictLabel(lab, perm=perm) for lab in issue.labels) or
      any(IsRestrictLabel(lab, perm=perm) for lab in issue.derived_labels))


def GetRestrictions(issue):
  """Return a list of restriction labels on the given issue."""
  if not issue:
    return []

  return [lab.lower() for lab in tracker_bizobj.GetLabels(issue)
          if IsRestrictLabel(lab)]


def CanViewIssue(
    effective_ids, perms, project, issue, allow_viewing_deleted=False,
    granted_perms=None):
  """Checks if user has permission to view an artifact.

  Args:
    effective_ids: set of user IDs for the logged in user and any user
        group memberships.  Should be an empty set for anon users.
    perms: PermissionSet for the user.
    project: Project PB for the project that contains this issue.
    issue: Issue PB for the issue being viewed.
    allow_viewing_deleted: True if the user should be allowed to view
        deleted artifacts.
    granted_perms: optional list of strings of permissions that the user is
        granted only within the scope of one issue, e.g., by being named in
        a user-type custom field that grants permissions.

  Returns:
    True iff the user can view the specified issue.
  """
  if issue.deleted and not allow_viewing_deleted:
    # No one can view a deleted issue.  If the user can undelete, that
    # goes through the custom 404 page.
    return False

  # Check to see if the user can view anything in the project.
  if not perms.CanUsePerm(VIEW, effective_ids, project, []):
    return False

  if not HasRestrictions(issue):
    return True

  return CanViewRestrictedIssueInVisibleProject(
      effective_ids, perms, project, issue, granted_perms=granted_perms)


def CanViewRestrictedIssueInVisibleProject(
    effective_ids, perms, project, issue, granted_perms=None):
  """Return True if the user can view this issue. Assumes project is OK."""
  # The reporter, owner, and CC'd users can always see the issue.
  # In effect, these fields override artifact restriction labels.
  if effective_ids:
    if (issue.reporter_id in effective_ids or
        tracker_bizobj.GetOwnerId(issue) in effective_ids or
        not effective_ids.isdisjoint(tracker_bizobj.GetCcIds(issue))):
      return True

  # Otherwise, apply the usual permission checking.
  return CanView(
      effective_ids, perms, project, GetRestrictions(issue),
      granted_perms=granted_perms)


def CanEditIssue(effective_ids, perms, project, issue, granted_perms=None):
  """Return True if a user can edit an issue.

  Args:
    effective_ids: set of user IDs for the logged in user and any user
        group memberships.  Should be an empty set for anon users.
    perms: PermissionSet for the user.
    project: Project PB for the project that contains this issue.
    issue: Issue PB for the issue being viewed.
    granted_perms: optional list of strings of permissions that the user is
        granted only within the scope of one issue, e.g., by being named in
        a user-type custom field that grants permissions.

  Returns:
    True iff the user can edit the specified issue.
  """
  # TODO(jrobbins): We need to actually grant View+EditIssue in most cases.
  # So, always grant View whenever there is any granted perm.
  if not CanViewIssue(
      effective_ids, perms, project, issue, granted_perms=granted_perms):
    return False

  # The issue owner can always edit the issue.
  if effective_ids:
    if tracker_bizobj.GetOwnerId(issue) in effective_ids:
      return True

  # Otherwise, apply the usual permission checking.
  return perms.CanUsePerm(
      EDIT_ISSUE, effective_ids, project, GetRestrictions(issue),
      granted_perms=granted_perms)


def CanCommentIssue(effective_ids, perms, project, issue, granted_perms=None):
  """Return True if a user can comment on an issue."""

  return perms.CanUsePerm(
      ADD_ISSUE_COMMENT, effective_ids, project,
      GetRestrictions(issue), granted_perms=granted_perms)


def CanUpdateApprovalStatus(
    effective_ids, approver_ids, current_status, new_status):
  """Return True if a user can change the approval status to the new status."""
  if not effective_ids.isdisjoint(approver_ids):
    return True # Approval approvers can always change the approval status

  if set([current_status, new_status]).isdisjoint(RESTRICTED_APPROVAL_STATUSES):
    return True

  return False


def CanUpdateApprovers(effective_ids, current_approver_ids):
  """Return True if a user can edit the list of approvers for an approval."""
  if not effective_ids.isdisjoint(current_approver_ids):
    return True

  return False


def CanViewComponentDef(effective_ids, perms, project, component_def):
  """Return True if a user can view the given component definition."""
  if not effective_ids.isdisjoint(component_def.admin_ids):
    return True  # Component admins can view that component.

  # TODO(jrobbins): check restrictions on the component definition.
  return perms.CanUsePerm(VIEW, effective_ids, project, [])


def CanEditComponentDef(effective_ids, perms, project, component_def, config):
  """Return True if a user can edit the given component definition."""
  if not effective_ids.isdisjoint(component_def.admin_ids):
    return True  # Component admins can edit that component.

  # Check to see if user is admin of any parent component.
  parent_components = tracker_bizobj.FindAncestorComponents(
      config, component_def)
  for parent in parent_components:
    if not effective_ids.isdisjoint(parent.admin_ids):
      return True

  return perms.CanUsePerm(EDIT_PROJECT, effective_ids, project, [])


def CanViewFieldDef(effective_ids, perms, project, field_def):
  """Return True if a user can view the given field definition."""
  if not effective_ids.isdisjoint(field_def.admin_ids):
    return True  # Field admins can view that field.

  # TODO(jrobbins): check restrictions on the field definition.
  return perms.CanUsePerm(VIEW, effective_ids, project, [])


def CanEditFieldDef(effective_ids, perms, project, field_def):
  """Return True if a user can edit the given field definition."""
  if not effective_ids.isdisjoint(field_def.admin_ids):
    return True  # Field admins can edit that field.

  return perms.CanUsePerm(EDIT_PROJECT, effective_ids, project, [])


def CanViewTemplate(effective_ids, perms, project, template):
  """Return True if a user can view the given issue template."""
  if not effective_ids.isdisjoint(template.admin_ids):
    return True  # template admins can view that template.

  # Members-only templates are only shown to members, other templates are
  # shown to any user that is generally allowed to view project content.
  if template.members_only:
    return framework_bizobj.UserIsInProject(project, effective_ids)
  else:
    return perms.CanUsePerm(VIEW, effective_ids, project, [])


def CanEditTemplate(effective_ids, perms, project, template):
  """Return True if a user can edit the given field definition."""
  if not effective_ids.isdisjoint(template.admin_ids):
    return True  # Template admins can edit that template.

  return perms.CanUsePerm(EDIT_PROJECT, effective_ids, project, [])


def CanViewHotlist(effective_ids, hotlist):
  """Return True if a user can view the given hotlist."""
  if not hotlist.is_private:
    return True

  # TODO(lukasperaza): allow site admins to see any hotlist
  return any([user_id in (hotlist.owner_ids + hotlist.editor_ids)
              for user_id in effective_ids])


def CanEditHotlist(effective_ids, hotlist):
  """Return True if a user is editor(add/remove issues and change rankings)."""
  return any([user_id in (hotlist.owner_ids + hotlist.editor_ids)
              for user_id in effective_ids])


def CanAdministerHotlist(effective_ids, hotlist):
  """Return True if user is owner(add/remove members, edit/delte hotlist)."""
  return any([user_id in hotlist.owner_ids for user_id in effective_ids])


def CanCreateHotlist(perms):
  """Return True if the given user may create a hotlist.

  Args:
    perms: Permissionset for the current user.

  Returns:
    True if the user should be allowed to create a hotlist.
  """
  if (settings.hotlist_creation_restriction ==
      site_pb2.UserTypeRestriction.ANYONE):
    return perms.HasPerm(CREATE_HOTLIST, None, None)

  if (settings.hotlist_creation_restriction ==
      site_pb2.UserTypeRestriction.ADMIN_ONLY):
    return perms.HasPerm(ADMINISTER_SITE, None, None)


class Error(Exception):
  """Base class for errors from this module."""


class PermissionException(Error):
  """The user is not authorized to make the current request."""


class BannedUserException(Error):
  """The user has been banned from using our service."""
