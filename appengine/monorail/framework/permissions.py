# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
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
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import bisect
import collections
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
EDIT_ISSUE_APPROVAL = 'EditIssueApproval'
DELETE_ISSUE = 'DeleteIssue'
# This allows certain API clients to attribute comments to other users.
# The permission is not offered in the UI, but it can be typed in as
# a custom permission name.  The ID of the API client is also recorded.
IMPORT_COMMENT = 'ImportComment'
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
    tracker_pb2.ApprovalStatus.NA,
    tracker_pb2.ApprovalStatus.APPROVED,
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

    # Get all extra perms for all effective ids.
    # Id X might have perm A and Y might have B, if both A and B are needed
    # True should be returned.
    extra_perms = set()
    for user_id in effective_ids:
      extra_perms.update(p.lower() for p in GetExtraPerms(project, user_id))
    return all(self.HasPerm(perm, None, None, extra_perms)
               for perm in needed_perms)

  def HasPerm(self, perm_name, user_id, project, extra_perms=None):
    """Return True if the user has the given permission (ignoring user groups).

    Args:
      perm_name: string name of permission, e.g., 'EditIssue'.
      user_id: int user id of the user, or None if user is not signed in.
      project: Project PB for the project being accessed, or None if not
          in a project.
      extra_perms: list of extra perms. If not given, GetExtraPerms will be
          called to get them.

    Returns:
      True if the user has the given perm.
    """
    perm_name = perm_name.lower()

    # Return early if possible.
    if perm_name in self.perm_names:
      return True

    if extra_perms is None:
      # TODO(jrobbins): room for performance improvement: pre-compute
      # extra perms (maybe merge them into the perms object), avoid
      # redundant call to lower().
      return any(
          p.lower() == perm_name
          for p in GetExtraPerms(project, user_id))

    return perm_name in extra_perms

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
     EDIT_ISSUE_APPROVAL,
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


def UpdateIssuePermissions(
    perms, project, issue, effective_ids, granted_perms=None, config=None):
  """Update the PermissionSet for an specific issue.

  Take into account granted permissions and label restrictions to filter the
  permissions, and updates the VIEW and EDIT_ISSUE permissions depending on the
  role of the user in the issue (i.e. owner, reporter, cc or approver).

  Args:
    perms: The PermissionSet to update.
    project: The Project PB for the issue project.
    issue: The Issue PB.
    effective_ids: Set of int user IDs for the current user and all user
        groups that s/he is a member of.  This will be an empty set for
        anonymous users.
    granted_perms: optional list of strings of permissions that the user is
        granted only within the scope of one issue, e.g., by being named in
        a user-type custom field that grants permissions.
    config: optional ProjectIssueConfig PB where granted perms should be
        extracted from, if granted_perms is not given.
  """
  if config:
    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, effective_ids, config)
  elif granted_perms is None:
    granted_perms = []

  # If the user has no permission to view the project, it has no permissions on
  # this issue.
  if not perms.HasPerm(VIEW, None, None):
    return EMPTY_PERMISSIONSET

  # Compute the restrictions for the given issue and store them in a dictionary
  # of {perm: set(needed_perms)}.
  restrictions = collections.defaultdict(set)
  if perms.consider_restrictions:
    for label in GetRestrictions(issue):
      label = label.lower()
      # format: Restrict-Action-ToThisPerm
      _, requested_perm, needed_perm = label.split('-', 2)
      restrictions[requested_perm.lower()].add(needed_perm.lower())

  # Store the user permissions, and the extra permissions of all effective IDs
  # in the given project.
  all_perms = set(perms.perm_names)
  for effective_id in effective_ids:
    all_perms.update(p.lower() for p in GetExtraPerms(project, effective_id))

  # And filter them applying the restriction labels.
  filtered_perms = set()
  for perm_name in all_perms:
    perm_name = perm_name.lower()
    restricted = any(
        restriction not in all_perms and restriction not in granted_perms
        for restriction in restrictions.get(perm_name, []))
    if not restricted:
      filtered_perms.add(perm_name)

  # Add any granted permissions.
  filtered_perms.update(granted_perms)

  # The VIEW perm might have been removed due to restrictions, but the issue
  # owner, reporter, cc and approvers can always be an issue.
  allowed_ids = set(
      tracker_bizobj.GetCcIds(issue)
      + tracker_bizobj.GetApproverIds(issue)
      + [issue.reporter_id, tracker_bizobj.GetOwnerId(issue)])
  if effective_ids and not allowed_ids.isdisjoint(effective_ids):
    filtered_perms.add(VIEW.lower())

  # If the issue is deleted, only the VIEW and DELETE_ISSUE permissions are
  # relevant.
  if issue.deleted:
    if VIEW.lower() not in filtered_perms:
      return EMPTY_PERMISSIONSET
    if DELETE_ISSUE.lower() in filtered_perms:
      return PermissionSet([VIEW, DELETE_ISSUE], perms.consider_restrictions)
    return PermissionSet([VIEW], perms.consider_restrictions)

  # The EDIT_ISSUE permission might have been removed due to restrictions, but
  # the owner has always permission to edit it.
  if effective_ids and tracker_bizobj.GetOwnerId(issue) in effective_ids:
    filtered_perms.add(EDIT_ISSUE.lower())

  return PermissionSet(filtered_perms, perms.consider_restrictions)


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

  _, extra_perms = FindExtraPerms(project, member_id)

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
    A pair (idx, extra_perms).
    * If project is None or member_id is not part of the project, both are None.
    * If member_id has no extra_perms, extra_perms is None, and idx points to
      the position where it should go to keep the ExtraPerms sorted in project.
    * Otherwise, idx is the position of member_id in the project's extra_perms,
      and extra_perms is an ExtraPerms PB.
  """
  class ExtraPermsView(object):
    def __len__(self):
      return len(project.extra_perms)
    def __getitem__(self, idx):
      return project.extra_perms[idx].member_id

  if not project:
    # TODO(jrobbins): maybe define extra perms for site-wide operations.
    return None, None

  # Users who have no current role cannot have any extra perms.  Don't
  # consider effective_ids (which includes user groups) for this check.
  if not framework_bizobj.UserIsInProject(project, {member_id}):
    return None, None

  extra_perms_view = ExtraPermsView()
  # Find the index of the first extra_perms.member_id greater than or equal to
  # member_id.
  idx = bisect.bisect_left(extra_perms_view, member_id)
  if idx >= len(project.extra_perms) or extra_perms_view[idx] > member_id:
    return idx, None
  return idx, project.extra_perms[idx]


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


def CanDeleteComment(comment, commenter, user_id, perms):
  """Returns true if the user can (un)delete the given comment.

  UpdateIssuePermissions must have been called first.

  Args:
    comment: An IssueComment PB object.
    commenter: An User PB object with the user who created the comment.
    user_id: The ID of the user whose permission we want to check.
    perms: The PermissionSet with the issue permissions.

  Returns:
    True if the user can (un)delete the comment.
  """
  # User is not logged in or has no permissions.
  if not user_id or not perms:
    return False

  # Nobody can (un)delete comments by banned users or spam comments, which
  # should be un-flagged instead.
  if commenter.banned or comment.is_spam:
    return False

  # Site admin or project owners can delete any comment.
  permit_delete_any = perms.HasPerm(DELETE_ANY, None, None, [])
  if permit_delete_any:
    return True

  # Users cannot undelete unless they deleted.
  if comment.deleted_by and comment.deleted_by != user_id:
    return False

  # Users can delete their own items.
  permit_delete_own = perms.HasPerm(DELETE_OWN, None, None, [])
  if permit_delete_own and comment.user_id == user_id:
    return True

  return False


def CanFlagComment(comment, commenter, comment_reporters, user_id, perms):
  """Returns true if the user can flag the given comment.

  UpdateIssuePermissions must have been called first.
  Assumes that the user has permission to view the issue.

  Args:
    comment: An IssueComment PB object.
    commenter: An User PB object with the user who created the comment.
    perms: The PermissionSet with the issue permissions.

  Returns:
    A tuple (can_flag, is_flagged).
    can_flag is True if the user can flag the comment. and is_flagged is True
    if the user sees the comment marked as spam.
  """
  # Nobody can flag comments by banned users.
  if commenter.banned:
    return False, comment.is_spam

  # If a comment was deleted for a reason other than being spam, nobody can
  # flag or un-flag it.
  if comment.deleted_by and not comment.is_spam:
    return False, comment.is_spam

  # A user with the VerdictSpam permission sees whether the comment is flagged
  # as spam or not, and can mark it as flagged or un-flagged.
  # If the comment is flagged as spam, all users see it as flagged, but only
  # those with the VerdictSpam can un-flag it.
  permit_verdict_spam = perms.HasPerm(VERDICT_SPAM, None, None, [])
  if permit_verdict_spam or comment.is_spam:
    return permit_verdict_spam, comment.is_spam

  # Otherwise, the comment is not marked as flagged and the user doesn't have
  # the VerdictSpam permission.
  # They are able to report a comment as spam if they have the FlagSpam
  # permission, and they see the comment as flagged if the have previously
  # reported it as spam.
  permit_flag_spam = perms.HasPerm(FLAG_SPAM, None, None, [])
  return permit_flag_spam, user_id in comment_reporters


def CanViewComment(comment, commenter, user_id, perms):
  """Returns true if the user can view the given comment.

  UpdateIssuePermissions must have been called first.
  Assumes that the user has permission to view the issue.

  Args:
    comment: An IssueComment PB object.
    commenter: An User PB object with the user who created the comment.
    user_id: The ID of the user whose permission we want to check.
    perms: The PermissionSet with the issue permissions.

  Returns:
    True if the user can view the comment.
  """
  # Nobody can view comments by banned users.
  if commenter.banned:
    return False

  # Only users with the permission to un-flag comments can view flagged
  # comments.
  if comment.is_spam:
    # If the comment is marked as spam, whether the user can un-flag the comment
    # or not doesn't depend on who reported it as spam.
    can_flag, _ = CanFlagComment(comment, commenter, [], user_id, perms)
    return can_flag

  # Only users with the permission to un-delete comments can view deleted
  # comments.
  if comment.deleted_by:
    return CanDeleteComment(comment, commenter, user_id, perms)

  return True


def CanViewInboundMessage(comment, user_id, perms):
  """Returns true if the user can view the given comment's inbound message.

  UpdateIssuePermissions must have been called first.
  Assumes that the user has permission to view the comment.

  Args:
    comment: An IssueComment PB object.
    commenter: An User PB object with the user who created the comment.
    user_id: The ID of the user whose permission we want to check.
    perms: The PermissionSet with the issue permissions.

  Returns:
    True if the user can view the comment's inbound message.
  """
  return (perms.HasPerm(VIEW_INBOUND_MESSAGES, None, None, [])
          or comment.user_id == user_id)


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


def CanViewGroupMembers(perms, effective_ids, group_settings, member_ids,
                        owner_ids, user_project_ids):
  """Return True if the given user may view a user group's members.

  Args:
    perms: Permissionset for the current user.
    effective_ids: set of user IDs for the logged in user.
    group_settings: PB of UserGroupSettings.
    member_ids: A list of member ids of this user group.
    owner_ids: A list of owner ids of this user group.
    user_project_ids: A list of project ids which the user has a role.

  Returns:
    True if the user should be allowed to view the group's members.
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

def CanViewContributorList(mr, project):
  """Return True if we should display the list project contributors.

  This is used on the project summary page, when deciding to offer the
  project People page link, and when generating autocomplete options
  that include project members.

  Args:
    mr: commonly used info parsed from the request.
    project: the Project we're interested in.

  Returns:
    True if we should display the project contributor list.
  """
  if not project:
    return False  # We are not even in a project context.

  if not project.only_owners_see_contributors:
    return True  # Contributor list is not resticted.

  # If it is hub-and-spoke, check for the perm that allows the user to
  # view it anyway.
  return mr.perms.HasPerm(
      VIEW_CONTRIBUTOR_LIST, mr.auth.user_id, project)


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
    return False

  perms = UpdateIssuePermissions(
      perms, project, issue, effective_ids, granted_perms=granted_perms)
  return perms.HasPerm(VIEW, None, None)


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
  perms = UpdateIssuePermissions(
      perms, project, issue, effective_ids, granted_perms=granted_perms)
  return perms.HasPerm(EDIT_ISSUE, None, None)


def CanCommentIssue(effective_ids, perms, project, issue, granted_perms=None):
  """Return True if a user can comment on an issue."""

  return perms.CanUsePerm(
      ADD_ISSUE_COMMENT, effective_ids, project,
      GetRestrictions(issue), granted_perms=granted_perms)


def CanUpdateApprovalStatus(
    effective_ids, perms, project, approver_ids, new_status):
  """Return True if a user can change the approval status to the new status."""
  if not effective_ids.isdisjoint(approver_ids):
    return True # Approval approvers can always change the approval status

  if new_status not in RESTRICTED_APPROVAL_STATUSES:
    return True

  return perms.CanUsePerm(EDIT_ISSUE_APPROVAL, effective_ids, project, [])


def CanUpdateApprovers(effective_ids, perms, project, current_approver_ids):
  """Return True if a user can edit the list of approvers for an approval."""
  if not effective_ids.isdisjoint(current_approver_ids):
    return True

  return perms.CanUsePerm(EDIT_ISSUE_APPROVAL, effective_ids, project, [])


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


def CanViewHotlist(effective_ids, perms, hotlist):
  """Return True if a user can view the given hotlist."""
  if not hotlist.is_private or perms.HasPerm(ADMINISTER_SITE, None, None):
    return True

  return any([user_id in (hotlist.owner_ids + hotlist.editor_ids)
              for user_id in effective_ids])


def CanEditHotlist(effective_ids, perms, hotlist):
  """Return True if a user is editor(add/remove issues and change rankings)."""
  return perms.HasPerm(ADMINISTER_SITE, None, None) or any(
      [user_id in (hotlist.owner_ids + hotlist.editor_ids)
       for user_id in effective_ids])


def CanAdministerHotlist(effective_ids, perms, hotlist):
  """Return True if user is owner(add/remove members, edit/delete hotlist)."""
  return perms.HasPerm(ADMINISTER_SITE, None, None) or any(
      [user_id in hotlist.owner_ids for user_id in effective_ids])


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
