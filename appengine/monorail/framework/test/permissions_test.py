# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for permissions.py."""

import time
import unittest

import mox

import settings
from framework import authdata
from framework import framework_constants
from framework import framework_views
from framework import permissions
from proto import features_pb2
from proto import project_pb2
from proto import site_pb2
from proto import tracker_pb2
from proto import user_pb2
from proto import usergroup_pb2
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


class PermissionSetTest(unittest.TestCase):

  def setUp(self):
    self.perms = permissions.PermissionSet(['A', 'b', 'Cc'])
    self.proj = project_pb2.Project()
    self.proj.contributor_ids.append(111L)
    self.proj.contributor_ids.append(222L)
    self.proj.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=111L, perms=['Cc', 'D', 'e', 'Ff']))
    self.proj.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=222L, perms=['G', 'H']))
    # user 3 used to be a member and had extra perms, but no longer in project.
    self.proj.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=333L, perms=['G', 'H']))

  def testGetAttr(self):
    self.assertTrue(self.perms.a)
    self.assertTrue(self.perms.A)
    self.assertTrue(self.perms.b)
    self.assertTrue(self.perms.Cc)
    self.assertTrue(self.perms.CC)

    self.assertFalse(self.perms.z)
    self.assertFalse(self.perms.Z)

  def testCanUsePerm_Anonymous(self):
    effective_ids = set()
    self.assertTrue(self.perms.CanUsePerm('A', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('D', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('Z', effective_ids, self.proj, []))

  def testCanUsePerm_SignedInNoGroups(self):
    effective_ids = {111L}
    self.assertTrue(self.perms.CanUsePerm('A', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm('D', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm(
        'D', effective_ids, self.proj, ['Restrict-D-A']))
    self.assertFalse(self.perms.CanUsePerm('G', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('Z', effective_ids, self.proj, []))

    effective_ids = {222L}
    self.assertTrue(self.perms.CanUsePerm('A', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('D', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm('G', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('Z', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm(
        'Z', effective_ids, self.proj, ['Restrict-Z-A']))

  def testCanUsePerm_SignedInWithGroups(self):
    effective_ids = {111L, 222L, 333L}
    self.assertTrue(self.perms.CanUsePerm('A', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm('D', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm('G', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm(
        'G', effective_ids, self.proj, ['Restrict-G-D']))
    self.assertFalse(self.perms.CanUsePerm('Z', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm(
        'G', effective_ids, self.proj, ['Restrict-G-Z']))

  def testCanUsePerm_FormerMember(self):
    effective_ids = {333L}
    self.assertTrue(self.perms.CanUsePerm('A', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('D', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('G', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('Z', effective_ids, self.proj, []))

  def testHasPerm_InPermSet(self):
    self.assertTrue(self.perms.HasPerm('a', 0, None))
    self.assertTrue(self.perms.HasPerm('a', 0, self.proj))
    self.assertTrue(self.perms.HasPerm('A', 0, None))
    self.assertTrue(self.perms.HasPerm('A', 0, self.proj))
    self.assertFalse(self.perms.HasPerm('Z', 0, None))
    self.assertFalse(self.perms.HasPerm('Z', 0, self.proj))

  def testHasPerm_InExtraPerms(self):
    self.assertTrue(self.perms.HasPerm('d', 111L, self.proj))
    self.assertTrue(self.perms.HasPerm('D', 111L, self.proj))
    self.assertTrue(self.perms.HasPerm('Cc', 111L, self.proj))
    self.assertTrue(self.perms.HasPerm('CC', 111L, self.proj))
    self.assertFalse(self.perms.HasPerm('Z', 111L, self.proj))

    self.assertFalse(self.perms.HasPerm('d', 222L, self.proj))
    self.assertFalse(self.perms.HasPerm('D', 222L, self.proj))

    # Only current members can have extra permissions
    self.proj.contributor_ids = []
    self.assertFalse(self.perms.HasPerm('d', 111L, self.proj))

    # TODO(jrobbins): also test consider_restrictions=False and
    # restriction labels directly in this class.

  def testHasPerm_OverrideExtraPerms(self):
    # D is an extra perm for 111L...
    self.assertTrue(self.perms.HasPerm('d', 111L, self.proj))
    self.assertTrue(self.perms.HasPerm('D', 111L, self.proj))
    # ...unless we tell HasPerm it isn't.
    self.assertFalse(self.perms.HasPerm('d', 111L, self.proj, []))
    self.assertFalse(self.perms.HasPerm('D', 111L, self.proj, []))
    # Perms in self.perms are still considered
    self.assertTrue(self.perms.HasPerm('Cc', 111L, self.proj, []))
    self.assertTrue(self.perms.HasPerm('CC', 111L, self.proj, []))
    # Z is not an extra perm...
    self.assertFalse(self.perms.HasPerm('Z', 111L, self.proj))
    # ...unless we tell HasPerm it is.
    self.assertTrue(self.perms.HasPerm('Z', 111L, self.proj, ['z']))

  def testHasPerm_GrantedPerms(self):
    self.assertTrue(self.perms.CanUsePerm(
        'A', {111L}, self.proj, [], granted_perms=['z']))
    self.assertTrue(self.perms.CanUsePerm(
        'a', {111L}, self.proj, [], granted_perms=['z']))
    self.assertTrue(self.perms.CanUsePerm(
        'a', {111L}, self.proj, [], granted_perms=['a']))
    self.assertTrue(self.perms.CanUsePerm(
        'Z', {111L}, self.proj, [], granted_perms=['y', 'z']))
    self.assertTrue(self.perms.CanUsePerm(
        'z', {111L}, self.proj, [], granted_perms=['y', 'z']))
    self.assertFalse(self.perms.CanUsePerm(
        'z', {111L}, self.proj, [], granted_perms=['y']))

  def testDebugString(self):
    self.assertEqual('PermissionSet()',
                     permissions.PermissionSet([]).DebugString())
    self.assertEqual('PermissionSet(a)',
                     permissions.PermissionSet(['A']).DebugString())
    self.assertEqual('PermissionSet(a, b, cc)', self.perms.DebugString())

  def testRepr(self):
    self.assertEqual('PermissionSet(frozenset([]))',
                     permissions.PermissionSet([]).__repr__())
    self.assertEqual('PermissionSet(frozenset([\'a\']))',
                     permissions.PermissionSet(['A']).__repr__())


class PermissionsTest(unittest.TestCase):

  NOW = 1277762224  # Any timestamp will do, we only compare it to itself +/- 1
  COMMITTER_USER_ID = 111L
  OWNER_USER_ID = 222L
  CONTRIB_USER_ID = 333L
  SITE_ADMIN_USER_ID = 444L

  def MakeProject(self, project_name, state, add_members=True, access=None):
    args = dict(project_name=project_name, state=state)
    if add_members:
      args.update(owner_ids=[self.OWNER_USER_ID],
                  committer_ids=[self.COMMITTER_USER_ID],
                  contributor_ids=[self.CONTRIB_USER_ID])

    if access:
      args.update(access=access)

    return fake.Project(**args)

  def setUp(self):
    self.live_project = self.MakeProject('live', project_pb2.ProjectState.LIVE)
    self.archived_project = self.MakeProject(
        'archived', project_pb2.ProjectState.ARCHIVED)
    self.other_live_project = self.MakeProject(
        'other_live', project_pb2.ProjectState.LIVE, add_members=False)
    self.members_only_project = self.MakeProject(
        's3kr3t', project_pb2.ProjectState.LIVE,
        access=project_pb2.ProjectAccess.MEMBERS_ONLY)

    self.nonmember = user_pb2.User()
    self.member = user_pb2.User()
    self.owner = user_pb2.User()
    self.contrib = user_pb2.User()
    self.site_admin = user_pb2.User()
    self.site_admin.is_site_admin = True
    self.borg_user = user_pb2.User(email=settings.borg_service_account)

    self.normal_artifact = tracker_pb2.Issue()
    self.normal_artifact.labels.extend(['hot', 'Key-Value'])
    self.normal_artifact.reporter_id = 111L

    # Two PermissionSets w/ permissions outside of any project.
    self.normal_user_perms = permissions.GetPermissions(
        None, {111L}, None)
    self.admin_perms = permissions.PermissionSet(
        [permissions.ADMINISTER_SITE,
         permissions.CREATE_PROJECT])

    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()

  def testGetPermissions_Admin(self):
    self.assertEqual(
        permissions.ADMIN_PERMISSIONSET,
        permissions.GetPermissions(self.site_admin, None, None))

  def testGetPermissions_BorgServiceAccount(self):
    self.assertEqual(
        permissions.GROUP_IMPORT_BORG_PERMISSIONSET,
        permissions.GetPermissions(self.borg_user, None, None))

  def CheckPermissions(self, perms, expected_list):
    expect_view, expect_commit, expect_edit_project = expected_list
    self.assertEqual(
        expect_view, perms.HasPerm(permissions.VIEW, None, None))
    self.assertEqual(
        expect_commit, perms.HasPerm(permissions.COMMIT, None, None))
    self.assertEqual(
        expect_edit_project,
        perms.HasPerm(permissions.EDIT_PROJECT, None, None))

  def testAnonPermissions(self):
    perms = permissions.GetPermissions(None, set(), self.live_project)
    self.CheckPermissions(perms, [True, False, False])

    perms = permissions.GetPermissions(None, set(), self.members_only_project)
    self.CheckPermissions(perms, [False, False, False])

  def testNonmemberPermissions(self):
    perms = permissions.GetPermissions(
        self.nonmember, {123}, self.live_project)
    self.CheckPermissions(perms, [True, False, False])

    perms = permissions.GetPermissions(
        self.nonmember, {123}, self.members_only_project)
    self.CheckPermissions(perms, [False, False, False])

  def testMemberPermissions(self):
    perms = permissions.GetPermissions(
        self.member, {self.COMMITTER_USER_ID}, self.live_project)
    self.CheckPermissions(perms, [True, True, False])

    perms = permissions.GetPermissions(
        self.member, {self.COMMITTER_USER_ID}, self.other_live_project)
    self.CheckPermissions(perms, [True, False, False])

    perms = permissions.GetPermissions(
        self.member, {self.COMMITTER_USER_ID}, self.members_only_project)
    self.CheckPermissions(perms, [True, True, False])

  def testOwnerPermissions(self):
    perms = permissions.GetPermissions(
        self.owner, {self.OWNER_USER_ID}, self.live_project)
    self.CheckPermissions(perms, [True, True, True])

    perms = permissions.GetPermissions(
        self.owner, {self.OWNER_USER_ID}, self.other_live_project)
    self.CheckPermissions(perms, [True, False, False])

    perms = permissions.GetPermissions(
        self.owner, {self.OWNER_USER_ID}, self.members_only_project)
    self.CheckPermissions(perms, [True, True, True])

  def testContributorPermissions(self):
    perms = permissions.GetPermissions(
        self.contrib, {self.CONTRIB_USER_ID}, self.live_project)
    self.CheckPermissions(perms, [True, False, False])

    perms = permissions.GetPermissions(
        self.contrib, {self.CONTRIB_USER_ID}, self.other_live_project)
    self.CheckPermissions(perms, [True, False, False])

    perms = permissions.GetPermissions(
        self.contrib, {self.CONTRIB_USER_ID}, self.members_only_project)
    self.CheckPermissions(perms, [True, False, False])

  def testLookupPermset_ExactMatch(self):
    self.assertEqual(
        permissions.USER_PERMISSIONSET,
        permissions._LookupPermset(
            permissions.USER_ROLE, project_pb2.ProjectState.LIVE,
            project_pb2.ProjectAccess.ANYONE))

  def testLookupPermset_WildcardAccess(self):
    self.assertEqual(
        permissions.OWNER_ACTIVE_PERMISSIONSET,
        permissions._LookupPermset(
            permissions.OWNER_ROLE, project_pb2.ProjectState.LIVE,
            project_pb2.ProjectAccess.MEMBERS_ONLY))

  def testGetPermissionKey_AnonUser(self):
    self.assertEqual(
        (permissions.ANON_ROLE, permissions.UNDEFINED_STATUS,
         permissions.UNDEFINED_ACCESS),
        permissions._GetPermissionKey(None, None))
    self.assertEqual(
        (permissions.ANON_ROLE, project_pb2.ProjectState.LIVE,
         project_pb2.ProjectAccess.ANYONE),
        permissions._GetPermissionKey(None, self.live_project))

  def testGetPermissionKey_ExpiredProject(self):
    self.archived_project.delete_time = self.NOW
    # In an expired project, the user's committe role does not count.
    self.assertEqual(
        (permissions.USER_ROLE, project_pb2.ProjectState.ARCHIVED,
         project_pb2.ProjectAccess.ANYONE),
        permissions._GetPermissionKey(
            self.COMMITTER_USER_ID, self.archived_project,
            expired_before=self.NOW + 1))
    # If not expired yet, the user's committe role still counts.
    self.assertEqual(
        (permissions.COMMITTER_ROLE, project_pb2.ProjectState.ARCHIVED,
         project_pb2.ProjectAccess.ANYONE),
        permissions._GetPermissionKey(
            self.COMMITTER_USER_ID, self.archived_project,
            expired_before=self.NOW - 1))

  def testGetPermissionKey_DefinedRoles(self):
    self.assertEqual(
        (permissions.OWNER_ROLE, project_pb2.ProjectState.LIVE,
         project_pb2.ProjectAccess.ANYONE),
        permissions._GetPermissionKey(
            self.OWNER_USER_ID, self.live_project))
    self.assertEqual(
        (permissions.COMMITTER_ROLE, project_pb2.ProjectState.LIVE,
         project_pb2.ProjectAccess.ANYONE),
        permissions._GetPermissionKey(
            self.COMMITTER_USER_ID, self.live_project))
    self.assertEqual(
        (permissions.CONTRIBUTOR_ROLE, project_pb2.ProjectState.LIVE,
         project_pb2.ProjectAccess.ANYONE),
        permissions._GetPermissionKey(
            self.CONTRIB_USER_ID, self.live_project))

  def testGetPermissionKey_Nonmember(self):
    self.assertEqual(
        (permissions.USER_ROLE, project_pb2.ProjectState.LIVE,
         project_pb2.ProjectAccess.ANYONE),
        permissions._GetPermissionKey(
            999L, self.live_project))

  def testPermissionsImmutable(self):
    self.assertTrue(isinstance(
        permissions.EMPTY_PERMISSIONSET.perm_names, frozenset))
    self.assertTrue(isinstance(
        permissions.READ_ONLY_PERMISSIONSET.perm_names, frozenset))
    self.assertTrue(isinstance(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET.perm_names, frozenset))
    self.assertTrue(isinstance(
        permissions.OWNER_ACTIVE_PERMISSIONSET.perm_names, frozenset))

  def testGetExtraPerms(self):
    project = project_pb2.Project()
    project.committer_ids.append(222L)
    # User 1 is a former member with left-over extra perms that don't count.
    project.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=111L, perms=['a', 'b', 'c']))
    project.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=222L, perms=['a', 'b', 'c']))

    self.assertListEqual(
        [],
        permissions.GetExtraPerms(project, 111L))
    self.assertListEqual(
        ['a', 'b', 'c'],
        permissions.GetExtraPerms(project, 222L))
    self.assertListEqual(
        [],
        permissions.GetExtraPerms(project, 333L))

  def testAnonUsersCannotDelete(self):
    perms = permissions.PermissionSet([permissions.DELETE_ANY])
    # No logged in user, no perms specfied.
    self.assertFalse(permissions.CanDelete(
        framework_constants.NO_USER_SPECIFIED, set(), None, 0, 0, None, []))
    # No logged in user, even with perms from somewhere.
    self.assertFalse(permissions.CanDelete(
        framework_constants.NO_USER_SPECIFIED, set(), perms, 0, 0, None, []))
    # No logged in user, even if artifact was already deleted.
    self.assertFalse(permissions.CanDelete(
        framework_constants.NO_USER_SPECIFIED, set(), perms,
        111L, 111L, None, []))
    # No logged in user, even if artifact was already deleted by project owner.
    self.assertFalse(permissions.CanDelete(
        framework_constants.NO_USER_SPECIFIED, set(), perms,
        111L, 222L, None, []))

  def testProjectOwnerCanDeleteAnyArtifact(self):
    perms = permissions.PermissionSet([permissions.DELETE_ANY])
    # No artifact owner, and not already deleted.
    self.assertTrue(permissions.CanDelete(
        111L, {111L}, perms, 0, 0, None, []))
    # I already deleted, can undelete.
    self.assertTrue(permissions.CanDelete(
        111L, {111L}, perms, 111L, 0, None, []))
    # I can delete my own thing.
    self.assertTrue(permissions.CanDelete(
        111L, {111L}, perms, 0, 111L, None, []))
    # I can also delete another user's artifacts, because I have DELETE_ANY.
    self.assertTrue(permissions.CanDelete(
        111L, {111L}, perms, 0, 222L, None, []))
    # I can always undelete, even if another PO deleted it.
    self.assertTrue(permissions.CanDelete(
        111L, {111L}, perms, 333L, 222L, None, []))

  def testUserCanDeleteTheirOwnStuff(self):
    perms = permissions.PermissionSet([permissions.DELETE_OWN])
    # I can delete/withdraw my artifact or comment.
    self.assertTrue(permissions.CanDelete(
        111L, {111L}, perms, 0, 111L, None, []))
    # I can undelete what I deleted.
    self.assertTrue(permissions.CanDelete(
        111L, {111L}, perms, 111L, 111L, None, []))
    # I cannot undelete if someone else deleted my spam.
    self.assertFalse(permissions.CanDelete(
        111L, {111L}, perms, 222L, 111L, None, []))
    # I cannot delete other people's stuff.
    self.assertFalse(permissions.CanDelete(
        111L, {111L}, perms, 0, 222L, None, []))
    # I cannot undelete what other people withdrew.
    self.assertFalse(permissions.CanDelete(
        111L, {111L}, perms, 222L, 222L, None, []))

  def testCanViewNormalArifact(self):
    # Anyone can view a non-restricted artifact.
    self.assertTrue(permissions.CanView(
        {111L}, permissions.READ_ONLY_PERMISSIONSET,
        self.live_project, []))

  def testCanCreateProject_NoPerms(self):
    """Signed out users cannot create projects."""
    self.assertFalse(permissions.CanCreateProject(
        permissions.EMPTY_PERMISSIONSET))

    self.assertFalse(permissions.CanCreateProject(
        permissions.READ_ONLY_PERMISSIONSET))

  def testCanCreateProject_Admin(self):
    """Site admins can create projects."""
    self.assertTrue(permissions.CanCreateProject(
        permissions.ADMIN_PERMISSIONSET))

  def testCanCreateProject_RegularUser(self):
    """Signed in non-admins can create a project if settings allow ANYONE."""
    try:
      orig_restriction = settings.project_creation_restriction
      ANYONE = site_pb2.UserTypeRestriction.ANYONE
      ADMIN_ONLY = site_pb2.UserTypeRestriction.ADMIN_ONLY
      NO_ONE = site_pb2.UserTypeRestriction.NO_ONE
      perms = permissions.PermissionSet([permissions.CREATE_PROJECT])

      settings.project_creation_restriction = ANYONE
      self.assertTrue(permissions.CanCreateProject(perms))

      settings.project_creation_restriction = ADMIN_ONLY
      self.assertFalse(permissions.CanCreateProject(perms))

      settings.project_creation_restriction = NO_ONE
      self.assertFalse(permissions.CanCreateProject(perms))
      self.assertFalse(permissions.CanCreateProject(
          permissions.ADMIN_PERMISSIONSET))
    finally:
      settings.project_creation_restriction = orig_restriction

  def testCanCreateGroup_AnyoneWithCreateGroup(self):
    orig_setting = settings.group_creation_restriction
    try:
      settings.group_creation_restriction = site_pb2.UserTypeRestriction.ANYONE
      self.assertTrue(permissions.CanCreateGroup(
          permissions.PermissionSet([permissions.CREATE_GROUP])))
      self.assertFalse(permissions.CanCreateGroup(
          permissions.PermissionSet([])))
    finally:
      settings.group_creation_restriction = orig_setting

  def testCanCreateGroup_AdminOnly(self):
    orig_setting = settings.group_creation_restriction
    try:
      ADMIN_ONLY = site_pb2.UserTypeRestriction.ADMIN_ONLY
      settings.group_creation_restriction = ADMIN_ONLY
      self.assertTrue(permissions.CanCreateGroup(
          permissions.PermissionSet([permissions.ADMINISTER_SITE])))
      self.assertFalse(permissions.CanCreateGroup(
          permissions.PermissionSet([permissions.CREATE_GROUP])))
      self.assertFalse(permissions.CanCreateGroup(
          permissions.PermissionSet([])))
    finally:
      settings.group_creation_restriction = orig_setting

  def testCanCreateGroup_UnspecifiedSetting(self):
    orig_setting = settings.group_creation_restriction
    try:
      settings.group_creation_restriction = None
      self.assertFalse(permissions.CanCreateGroup(
          permissions.PermissionSet([permissions.ADMINISTER_SITE])))
      self.assertFalse(permissions.CanCreateGroup(
          permissions.PermissionSet([permissions.CREATE_GROUP])))
      self.assertFalse(permissions.CanCreateGroup(
          permissions.PermissionSet([])))
    finally:
      settings.group_creation_restriction = orig_setting

  def testCanEditGroup_HasPerm(self):
    self.assertTrue(permissions.CanEditGroup(
        permissions.PermissionSet([permissions.EDIT_GROUP]), None, None))

  def testCanEditGroup_IsOwner(self):
    self.assertTrue(permissions.CanEditGroup(
        permissions.PermissionSet([]), {111L}, {111L}))

  def testCanEditGroup_Otherwise(self):
    self.assertFalse(permissions.CanEditGroup(
        permissions.PermissionSet([]), {111L}, {222L}))

  def testCanViewGroupMembers_HasPerm(self):
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([permissions.VIEW_GROUP]),
        None, None, None, None, None))

  def testCanViewGroupMembers_IsMemberOfFriendProject(self):
    group_settings = usergroup_pb2.MakeSettings('owners', friend_projects=[890])
    self.assertFalse(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {111L}, group_settings, {222L}, {333L}, {789}))
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {111L}, group_settings, {222L}, {333L}, {789, 890}))

  def testCanViewGroupMembers_VisibleToOwner(self):
    group_settings = usergroup_pb2.MakeSettings('owners')
    self.assertFalse(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {111L}, group_settings, {222L}, {333L}, {789}))
    self.assertFalse(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {222L}, group_settings, {222L}, {333L}, {789}))
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {333L}, group_settings, {222L}, {333L}, {789}))

  def testCanViewGroupMembers_IsVisibleToMember(self):
    group_settings = usergroup_pb2.MakeSettings('members')
    self.assertFalse(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {111L}, group_settings, {222L}, {333L}, {789}))
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {222L}, group_settings, {222L}, {333L}, {789}))
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {333L}, group_settings, {222L}, {333L}, {789}))

  def testCanViewGroupMembers_AnyoneCanView(self):
    group_settings = usergroup_pb2.MakeSettings('anyone')
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {111L}, group_settings, {222L}, {333L}, {789}))

  def testIsBanned_AnonUser(self):
    user_view = framework_views.StuffUserView(None, None, True)
    self.assertFalse(permissions.IsBanned(None, user_view))

  def testIsBanned_NormalUser(self):
    user = user_pb2.User()
    user_view = framework_views.StuffUserView(None, None, True)
    self.assertFalse(permissions.IsBanned(user, user_view))

  def testIsBanned_BannedUser(self):
    user = user_pb2.User()
    user.banned = 'spammer'
    user_view = framework_views.StuffUserView(None, None, True)
    self.assertTrue(permissions.IsBanned(user, user_view))

  def testIsBanned_BadDomainUser(self):
    user = user_pb2.User()
    self.assertFalse(permissions.IsBanned(user, None))

    user_view = framework_views.StuffUserView(None, None, True)
    user_view.domain = 'spammer.com'
    self.assertFalse(permissions.IsBanned(user, user_view))

    orig_banned_user_domains = settings.banned_user_domains
    settings.banned_user_domains = ['spammer.com', 'phisher.com']
    self.assertTrue(permissions.IsBanned(user, user_view))
    settings.banned_user_domains = orig_banned_user_domains

  def testIsBanned_PlusAddressUser(self):
    """We don't allow users who have + in their email address."""
    user = user_pb2.User(email='user@example.com')
    self.assertFalse(permissions.IsBanned(user, None))

    user.email = 'user+shadystuff@example.com'
    self.assertTrue(permissions.IsBanned(user, None))

  def testGetCustomPermissions(self):
    project = project_pb2.Project()
    self.assertListEqual([], permissions.GetCustomPermissions(project))

    project.extra_perms.append(project_pb2.Project.ExtraPerms(
        perms=['Core', 'Elite', 'Gold']))
    self.assertListEqual(['Core', 'Elite', 'Gold'],
                         permissions.GetCustomPermissions(project))

    project.extra_perms.append(project_pb2.Project.ExtraPerms(
        perms=['Silver', 'Gold', 'Bronze']))
    self.assertListEqual(['Bronze', 'Core', 'Elite', 'Gold', 'Silver'],
                         permissions.GetCustomPermissions(project))

    # View is not returned because it is a starndard permission.
    project.extra_perms.append(project_pb2.Project.ExtraPerms(
        perms=['Bronze', permissions.VIEW]))
    self.assertListEqual(['Bronze', 'Core', 'Elite', 'Gold', 'Silver'],
                         permissions.GetCustomPermissions(project))

  def testUserCanViewProject(self):
    self.mox.StubOutWithMock(time, 'time')
    for _ in range(8):
      time.time().AndReturn(self.NOW)
    self.mox.ReplayAll()

    self.assertTrue(permissions.UserCanViewProject(
        self.member, {self.COMMITTER_USER_ID}, self.live_project))
    self.assertTrue(permissions.UserCanViewProject(
        None, None, self.live_project))

    self.archived_project.delete_time = self.NOW + 1
    self.assertFalse(permissions.UserCanViewProject(
        None, None, self.archived_project))
    self.assertTrue(permissions.UserCanViewProject(
        self.owner, {self.OWNER_USER_ID}, self.archived_project))
    self.assertTrue(permissions.UserCanViewProject(
        self.site_admin, {self.SITE_ADMIN_USER_ID},
        self.archived_project))

    self.archived_project.delete_time = self.NOW - 1
    self.assertFalse(permissions.UserCanViewProject(
        None, None, self.archived_project))
    self.assertFalse(permissions.UserCanViewProject(
        self.owner, {self.OWNER_USER_ID}, self.archived_project))
    self.assertTrue(permissions.UserCanViewProject(
        self.site_admin, {self.SITE_ADMIN_USER_ID},
        self.archived_project))

    self.mox.VerifyAll()

  def CheckExpired(self, state, expected_to_be_reapable):
    proj = project_pb2.Project()
    proj.state = state
    proj.delete_time = self.NOW + 1
    self.assertFalse(permissions.IsExpired(proj))

    proj.delete_time = self.NOW - 1
    self.assertEqual(expected_to_be_reapable, permissions.IsExpired(proj))

    proj.delete_time = self.NOW - 1
    self.assertFalse(permissions.IsExpired(proj, expired_before=self.NOW - 2))

  def testIsExpired_Live(self):
    self.CheckExpired(project_pb2.ProjectState.LIVE, False)

  def testIsExpired_Archived(self):
    self.mox.StubOutWithMock(time, 'time')
    for _ in range(2):
      time.time().AndReturn(self.NOW)
    self.mox.ReplayAll()

    self.CheckExpired(project_pb2.ProjectState.ARCHIVED, True)

    self.mox.VerifyAll()


class PermissionsCheckTest(unittest.TestCase):

  def setUp(self):
    self.perms = permissions.PermissionSet(['a', 'b', 'c'])

    self.proj = project_pb2.Project()
    self.proj.committer_ids.append(111L)
    self.proj.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=111L, perms=['d']))

    # Note: z is an example of a perm that the user does not have.
    # Note: q is an example of an irrelevant perm that the user does not have.

  def DoCanUsePerm(self, perm, project='default', user_id=None, restrict=''):
    """Wrapper function to call CanUsePerm()."""
    if project == 'default':
      project = self.proj
    return self.perms.CanUsePerm(
        perm, {user_id or 111L}, project, restrict.split())

  def testHasPermNoRestrictions(self):
    self.assertTrue(self.DoCanUsePerm('a'))
    self.assertTrue(self.DoCanUsePerm('A'))
    self.assertFalse(self.DoCanUsePerm('z'))
    self.assertTrue(self.DoCanUsePerm('d'))
    self.assertFalse(self.DoCanUsePerm('d', user_id=222L))
    self.assertFalse(self.DoCanUsePerm('d', project=project_pb2.Project()))

  def testHasPermOperationRestrictions(self):
    self.assertTrue(self.DoCanUsePerm('a', restrict='Restrict-a-b'))
    self.assertTrue(self.DoCanUsePerm('a', restrict='Restrict-b-z'))
    self.assertTrue(self.DoCanUsePerm('a', restrict='Restrict-a-d'))
    self.assertTrue(self.DoCanUsePerm('d', restrict='Restrict-d-a'))
    self.assertTrue(self.DoCanUsePerm(
        'd', restrict='Restrict-q-z Restrict-q-d Restrict-d-a'))

    self.assertFalse(self.DoCanUsePerm('a', restrict='Restrict-a-z'))
    self.assertFalse(self.DoCanUsePerm('d', restrict='Restrict-d-z'))
    self.assertFalse(self.DoCanUsePerm(
        'd', restrict='Restrict-d-a Restrict-d-z'))

  def testHasPermOutsideProjectScope(self):
    self.assertTrue(self.DoCanUsePerm('a', project=None))
    self.assertTrue(self.DoCanUsePerm(
        'a', project=None, restrict='Restrict-a-c'))
    self.assertTrue(self.DoCanUsePerm(
        'a', project=None, restrict='Restrict-q-z'))

    self.assertFalse(self.DoCanUsePerm('z', project=None))
    self.assertFalse(self.DoCanUsePerm(
        'a', project=None, restrict='Restrict-a-d'))


class CanViewProjectContributorListTest(unittest.TestCase):

  def testCanViewProjectContributorList_NoProject(self):
    mr = testing_helpers.MakeMonorailRequest(path='/')
    self.assertFalse(permissions.CanViewContributorList(mr, mr.project))

  def testCanViewProjectContributorList_NormalProject(self):
    project = project_pb2.Project()
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/', project=project)
    self.assertTrue(permissions.CanViewContributorList(mr, mr.project))

  def testCanViewProjectContributorList_ProjectWithOptionSet(self):
    project = project_pb2.Project()
    project.only_owners_see_contributors = True

    for perms in [permissions.READ_ONLY_PERMISSIONSET,
                  permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
                  permissions.CONTRIBUTOR_INACTIVE_PERMISSIONSET]:
      mr = testing_helpers.MakeMonorailRequest(
          path='/p/proj/', project=project, perms=perms)
      self.assertFalse(permissions.CanViewContributorList(mr, mr.project))

    for perms in [permissions.COMMITTER_ACTIVE_PERMISSIONSET,
                  permissions.COMMITTER_INACTIVE_PERMISSIONSET,
                  permissions.OWNER_ACTIVE_PERMISSIONSET,
                  permissions.OWNER_INACTIVE_PERMISSIONSET,
                  permissions.ADMIN_PERMISSIONSET]:
      mr = testing_helpers.MakeMonorailRequest(
          path='/p/proj/', project=project, perms=perms)
      self.assertTrue(permissions.CanViewContributorList(mr, mr.project))


class ShouldCheckForAbandonmentTest(unittest.TestCase):

  def setUp(self):
    self.mr = testing_helpers.Blank(
        project=project_pb2.Project(),
        auth=authdata.AuthData())

  def testOwner(self):
    self.mr.auth.effective_ids = {111L}
    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.assertTrue(permissions.ShouldCheckForAbandonment(self.mr))

  def testNonOwner(self):
    self.mr.auth.effective_ids = {222L}
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.assertFalse(permissions.ShouldCheckForAbandonment(self.mr))
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.assertFalse(permissions.ShouldCheckForAbandonment(self.mr))
    self.mr.perms = permissions.USER_PERMISSIONSET
    self.assertFalse(permissions.ShouldCheckForAbandonment(self.mr))
    self.mr.perms = permissions.EMPTY_PERMISSIONSET
    self.assertFalse(permissions.ShouldCheckForAbandonment(self.mr))

  def testSiteAdmin(self):
    self.mr.auth.effective_ids = {111L}
    self.mr.perms = permissions.ADMIN_PERMISSIONSET
    self.assertFalse(permissions.ShouldCheckForAbandonment(self.mr))


class RestrictionLabelsTest(unittest.TestCase):

  ORIG_SUMMARY = 'this is the orginal summary'
  ORIG_LABELS = ['one', 'two']

  def testIsRestrictLabel(self):
    self.assertFalse(permissions.IsRestrictLabel('Usability'))
    self.assertTrue(permissions.IsRestrictLabel('Restrict-View-CoreTeam'))
    # Doing it again will test the cached results.
    self.assertFalse(permissions.IsRestrictLabel('Usability'))
    self.assertTrue(permissions.IsRestrictLabel('Restrict-View-CoreTeam'))

    self.assertFalse(permissions.IsRestrictLabel('Usability', perm='View'))
    self.assertTrue(permissions.IsRestrictLabel(
        'Restrict-View-CoreTeam', perm='View'))

    # This one is a restriction label, but not the kind that we want.
    self.assertFalse(permissions.IsRestrictLabel(
        'Restrict-View-CoreTeam', perm='Delete'))

  def testGetRestrictions_NoIssue(self):
    self.assertEqual([], permissions.GetRestrictions(None))

  def testGetRestrictions(self):
    art = fake.MakeTestIssue(
        789, 1, self.ORIG_SUMMARY, 'New', 0L, labels=self.ORIG_LABELS)
    self.assertEquals([], permissions.GetRestrictions(art))

    art = fake.MakeTestIssue(
        789, 1, self.ORIG_SUMMARY, 'New', 0L,
        labels=['Restrict-MissingThirdPart', 'Hot'])
    self.assertEquals([], permissions.GetRestrictions(art))

    art = fake.MakeTestIssue(
        789, 1, self.ORIG_SUMMARY, 'New', 0L,
        labels=['Restrict-View-Core', 'Hot'])
    self.assertEquals(['restrict-view-core'], permissions.GetRestrictions(art))

    art = fake.MakeTestIssue(
        789, 1, self.ORIG_SUMMARY, 'New', 0L,
        labels=['Restrict-View-Core', 'Hot'],
        derived_labels=['Color-Red', 'Restrict-EditIssue-GoldMembers'])
    self.assertEquals(
        ['restrict-view-core', 'restrict-editissue-goldmembers'],
        permissions.GetRestrictions(art))

    art = fake.MakeTestIssue(
        789, 1, self.ORIG_SUMMARY, 'New', 0L,
        labels=['restrict-view-core', 'hot'],
        derived_labels=['Color-Red', 'RESTRICT-EDITISSUE-GOLDMEMBERS'])
    self.assertEquals(
        ['restrict-view-core', 'restrict-editissue-goldmembers'],
        permissions.GetRestrictions(art))


REPORTER_ID = 111L
OWNER_ID = 222L
CC_ID = 333L
OTHER_ID = 444L
APPROVER_ID = 555L


class IssuePermissionsTest(unittest.TestCase):

  REGULAR_ISSUE = tracker_pb2.Issue()
  REGULAR_ISSUE.reporter_id = REPORTER_ID

  DELETED_ISSUE = tracker_pb2.Issue()
  DELETED_ISSUE.deleted = True
  DELETED_ISSUE.reporter_id = REPORTER_ID

  RESTRICTED_ISSUE = tracker_pb2.Issue()
  RESTRICTED_ISSUE.reporter_id = REPORTER_ID
  RESTRICTED_ISSUE.owner_id = OWNER_ID
  RESTRICTED_ISSUE.cc_ids.append(CC_ID)
  RESTRICTED_ISSUE.approval_values.append(
      tracker_pb2.ApprovalValue(approver_ids=[APPROVER_ID])
  )
  RESTRICTED_ISSUE.labels.append('Restrict-View-Commit')

  RESTRICTED_ISSUE2 = tracker_pb2.Issue()
  RESTRICTED_ISSUE2.reporter_id = REPORTER_ID
  # RESTRICTED_ISSUE2 has no owner
  RESTRICTED_ISSUE2.cc_ids.append(CC_ID)
  RESTRICTED_ISSUE2.labels.append('Restrict-View-Commit')

  RESTRICTED_ISSUE3 = tracker_pb2.Issue()
  RESTRICTED_ISSUE3.reporter_id = REPORTER_ID
  RESTRICTED_ISSUE3.owner_id = OWNER_ID
  # Restrict to a permission that no one has.
  RESTRICTED_ISSUE3.labels.append('Restrict-EditIssue-Foo')

  PROJECT = project_pb2.Project()

  def testUpdateIssuePermissions_Normal(self):
    perms = permissions.UpdateIssuePermissions(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET, self.PROJECT,
        self.REGULAR_ISSUE, {})

    self.assertEqual(
        ['addissuecomment',
         'commit',
         'createissue',
         'deleteown',
         'editissue',
         'flagspam',
         'setstar',
         'verdictspam',
         'view',
         'viewcontributorlist',
         'viewinboundmessages',
         'viewquota'],
        sorted(perms.perm_names))

  def testUpdateIssuePermissions_Deleted(self):
    perms = permissions.UpdateIssuePermissions(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET, self.PROJECT,
        self.DELETED_ISSUE, {})
    self.assertEqual(['view'], sorted(perms.perm_names))

  def testUpdateIssuePermissions_ViewDeleted(self):
    perms = permissions.UpdateIssuePermissions(
        permissions.OWNER_ACTIVE_PERMISSIONSET, self.PROJECT,
        self.DELETED_ISSUE, {})
    self.assertEqual(['deleteissue', 'view'], sorted(perms.perm_names))

  def testUpdateIssuePermissions_ViewRestrictions(self):
    perms = permissions.UpdateIssuePermissions(
        permissions.USER_PERMISSIONSET, self.PROJECT, self.RESTRICTED_ISSUE, {})
    self.assertNotIn('view', perms.perm_names)

  def testUpdateIssuePermissions_RolesBypassViewRestrictions(self):
    for role in {OWNER_ID, REPORTER_ID, CC_ID, APPROVER_ID}:
      perms = permissions.UpdateIssuePermissions(
          permissions.USER_PERMISSIONSET, self.PROJECT, self.RESTRICTED_ISSUE,
          {role})
      self.assertIn('view', perms.perm_names)

  def testUpdateIssuePermissions_GrantedViewPermission(self):
    perms = permissions.UpdateIssuePermissions(
        permissions.USER_PERMISSIONSET, self.PROJECT, self.RESTRICTED_ISSUE,
        {}, ['commit'])
    self.assertIn('view', perms.perm_names)

  def testUpdateIssuePermissions_EditRestrictions(self):
    perms = permissions.UpdateIssuePermissions(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET, self.PROJECT,
        self.RESTRICTED_ISSUE3, {REPORTER_ID, CC_ID, APPROVER_ID})
    self.assertNotIn('editissue', perms.perm_names)

  def testUpdateIssuePermissions_OwnerBypassEditRestrictions(self):
    perms = permissions.UpdateIssuePermissions(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET, self.PROJECT,
        self.RESTRICTED_ISSUE3, {OWNER_ID})
    self.assertIn('editissue', perms.perm_names)

  def testUpdateIssuePermissions_CustomPermissionGrantsEditPermission(self):
    project = project_pb2.Project()
    project.committer_ids.append(999L)
    project.extra_perms.append(
        project_pb2.Project.ExtraPerms(member_id=999L, perms=['Foo']))
    perms = permissions.UpdateIssuePermissions(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET, project,
        self.RESTRICTED_ISSUE3, {999L})
    self.assertIn('editissue', perms.perm_names)

  def testCanViewIssue_Deleted(self):
    self.assertFalse(permissions.CanViewIssue(
        {REPORTER_ID}, permissions.OWNER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.DELETED_ISSUE))
    self.assertTrue(permissions.CanViewIssue(
        {REPORTER_ID}, permissions.OWNER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.DELETED_ISSUE, allow_viewing_deleted=True))
    self.assertTrue(permissions.CanViewIssue(
        {REPORTER_ID}, permissions.OWNER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))

  def testCanViewIssue_Regular(self):
    self.assertTrue(permissions.CanViewIssue(
        {REPORTER_ID}, permissions.OWNER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertTrue(permissions.CanViewIssue(
        {REPORTER_ID}, permissions.COMMITTER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertTrue(permissions.CanViewIssue(
        {REPORTER_ID},
        permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertTrue(permissions.CanViewIssue(
        {REPORTER_ID}, permissions.USER_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertTrue(permissions.CanViewIssue(
        {REPORTER_ID}, permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertTrue(permissions.CanViewIssue(
        set(), permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))

  def testCanViewIssue_Restricted(self):
    # Project owner can always view issue.
    self.assertTrue(permissions.CanViewIssue(
        {OTHER_ID}, permissions.OWNER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))
    # Member can view because they have Commit perm.
    self.assertTrue(permissions.CanViewIssue(
        {OTHER_ID}, permissions.COMMITTER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))
    # Contributors normally do not have Commit perm.
    self.assertFalse(permissions.CanViewIssue(
        {OTHER_ID}, permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))
    # Non-members do not have Commit perm.
    self.assertFalse(permissions.CanViewIssue(
        {OTHER_ID}, permissions.USER_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))
    # Anon user's do not have Commit perm.
    self.assertFalse(permissions.CanViewIssue(
        set(), permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))

  def testCanViewIssue_RestrictedParticipants(self):
    # Reporter can always view issue
    self.assertTrue(permissions.CanViewIssue(
        {REPORTER_ID}, permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))
    # Issue owner can always view issue
    self.assertTrue(permissions.CanViewIssue(
        {OWNER_ID}, permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))
    # CC'd user can always view issue
    self.assertTrue(permissions.CanViewIssue(
        {CC_ID}, permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))
    # Non-participants cannot view issue if they don't have the needed perm.
    self.assertFalse(permissions.CanViewIssue(
        {OTHER_ID}, permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))
    # Anon user's do not have Commit perm.
    self.assertFalse(permissions.CanViewIssue(
        set(), permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))
    # Anon user's cannot match owner 0.
    self.assertFalse(permissions.CanViewIssue(
        set(), permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE2))
    # Approvers can always view issue
    self.assertTrue(permissions.CanViewIssue(
        {APPROVER_ID}, permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE))

  def testCannotViewIssueIfCannotViewProject(self):
    """Cross-project search should not be a backdoor to viewing issues."""
    # Reporter cannot view issue if they not long have access to the project.
    self.assertFalse(permissions.CanViewIssue(
        {REPORTER_ID}, permissions.EMPTY_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    # Issue owner cannot always view issue
    self.assertFalse(permissions.CanViewIssue(
        {OWNER_ID}, permissions.EMPTY_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    # CC'd user cannot always view issue
    self.assertFalse(permissions.CanViewIssue(
        {CC_ID}, permissions.EMPTY_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    # Non-participants cannot view issue if they don't have the needed perm.
    self.assertFalse(permissions.CanViewIssue(
        {OTHER_ID}, permissions.EMPTY_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    # Anon user's do not have Commit perm.
    self.assertFalse(permissions.CanViewIssue(
        set(), permissions.EMPTY_PERMISSIONSET, self.PROJECT,
        self.REGULAR_ISSUE))
    # Anon user's cannot match owner 0.
    self.assertFalse(permissions.CanViewIssue(
        set(), permissions.EMPTY_PERMISSIONSET, self.PROJECT,
        self.REGULAR_ISSUE))

  def testCanEditIssue(self):
    # Anon users cannot edit issues.
    self.assertFalse(permissions.CanEditIssue(
        {}, permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))

    # Non-members and contributors cannot edit issues,
    # even if they reported them.
    self.assertFalse(permissions.CanEditIssue(
        {REPORTER_ID}, permissions.READ_ONLY_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertFalse(permissions.CanEditIssue(
        {REPORTER_ID}, permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))

    # Project committers and project owners can edit issues, regardless
    # of their role in the issue.
    self.assertTrue(permissions.CanEditIssue(
        {REPORTER_ID}, permissions.COMMITTER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertTrue(permissions.CanEditIssue(
        {REPORTER_ID}, permissions.OWNER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertTrue(permissions.CanEditIssue(
        {OWNER_ID}, permissions.COMMITTER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertTrue(permissions.CanEditIssue(
        {OWNER_ID}, permissions.OWNER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertTrue(permissions.CanEditIssue(
        {OTHER_ID}, permissions.COMMITTER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))
    self.assertTrue(permissions.CanEditIssue(
        {OTHER_ID}, permissions.OWNER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.REGULAR_ISSUE))

  def testCanEditIssue_Restricted(self):
    # Anon users cannot edit restricted issues.
    self.assertFalse(permissions.CanEditIssue(
        {}, permissions.COMMITTER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE3))

    # Project committers cannot edit issues with a restriction to a custom
    # permission that they don't have.
    self.assertFalse(permissions.CanEditIssue(
        {OTHER_ID}, permissions.COMMITTER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE3))

    # *Issue* owners can always edit the issues that they own, even if
    # those issues are restricted to perms that they don't have.
    self.assertTrue(permissions.CanEditIssue(
        {OWNER_ID}, permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE3))

    # Project owners can always edit, they cannot lock themselves out.
    self.assertTrue(permissions.CanEditIssue(
        {OTHER_ID}, permissions.OWNER_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE3))

    # A committer with edit permission but not view permission
    # should not be able to edit the issue.
    self.assertFalse(permissions.CanEditIssue(
        {OTHER_ID}, permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
        self.PROJECT, self.RESTRICTED_ISSUE2))

  def testCanCommentIssue_HasPerm(self):
    self.assertTrue(permissions.CanCommentIssue(
        {111L}, permissions.PermissionSet([permissions.ADD_ISSUE_COMMENT]),
        None, None))
    self.assertFalse(permissions.CanCommentIssue(
        {111L}, permissions.PermissionSet([]),
        None, None))

  def testCanCommentIssue_HasExtraPerm(self):
    project = project_pb2.Project()
    project.committer_ids.append(111L)
    extra_perm = project_pb2.Project.ExtraPerms(
        member_id=111L, perms=[permissions.ADD_ISSUE_COMMENT])
    project.extra_perms.append(extra_perm)
    self.assertTrue(permissions.CanCommentIssue(
        {111L}, permissions.PermissionSet([]),
        project, None))
    self.assertFalse(permissions.CanCommentIssue(
        {222L}, permissions.PermissionSet([]),
        project, None))

  def testCanCommentIssue_Restricted(self):
    issue = tracker_pb2.Issue(labels=['Restrict-AddIssueComment-CoreTeam'])
    # User is granted exactly the perm they need specifically in this issue.
    self.assertTrue(permissions.CanCommentIssue(
        {111L}, permissions.PermissionSet([]),
        None, issue, granted_perms=['addissuecomment']))
    # User is granted CoreTeam, which satifies the restriction, and allows
    # them to use the AddIssueComment permission that they have and would
    # normally be able to use in an unrestricted issue.
    self.assertTrue(permissions.CanCommentIssue(
        {111L}, permissions.PermissionSet([permissions.ADD_ISSUE_COMMENT]),
        None, issue, granted_perms=['coreteam']))
    # User was granted CoreTeam, but never had AddIssueComment.
    self.assertFalse(permissions.CanCommentIssue(
        {111L}, permissions.PermissionSet([]),
        None, issue, granted_perms=['coreteam']))
    # User has AddIssueComment, but cannot satisfy restriction.
    self.assertFalse(permissions.CanCommentIssue(
        {111L}, permissions.PermissionSet([permissions.ADD_ISSUE_COMMENT]),
        None, issue))

  def testCanCommentIssue_Granted(self):
    self.assertTrue(permissions.CanCommentIssue(
        {111L}, permissions.PermissionSet([]),
        None, None, granted_perms=['addissuecomment']))
    self.assertFalse(permissions.CanCommentIssue(
        {111L}, permissions.PermissionSet([]),
        None, None))

  def testCanUpdateApprovalStatus_Approver(self):
     self.assertTrue(permissions.CanUpdateApprovalStatus(
         {111L, 222L}, permissions.PermissionSet([]), self.PROJECT,
         [222L], tracker_pb2.ApprovalStatus.APPROVED,
         tracker_pb2.ApprovalStatus.NOT_APPROVED))

     self.assertTrue(permissions.CanUpdateApprovalStatus(
         {111L, 222L}, permissions.PermissionSet([]), self.PROJECT,
         [222L], tracker_pb2.ApprovalStatus.NEEDS_REVIEW,
         tracker_pb2.ApprovalStatus.NA))

  def testCanUpdateApprovalStatus_SiteAdmin(self):
      self.assertTrue(permissions.CanUpdateApprovalStatus(
          {444L}, permissions.PermissionSet([permissions.EDIT_ISSUE_APPROVAL]),
          self.PROJECT, [222L], tracker_pb2.ApprovalStatus.APPROVED,
          tracker_pb2.ApprovalStatus.NOT_APPROVED))

      self.assertTrue(permissions.CanUpdateApprovalStatus(
          {444L}, permissions.PermissionSet([permissions.EDIT_ISSUE_APPROVAL]),
          self.PROJECT, [222L], tracker_pb2.ApprovalStatus.NEEDS_REVIEW,
          tracker_pb2.ApprovalStatus.NA))

  def testCanUpdateApprovalStatus_NonApprover(self):
    self.assertTrue(permissions.CanUpdateApprovalStatus(
        {111L, 222L}, permissions.PermissionSet([]), self.PROJECT,
        [333L], tracker_pb2.ApprovalStatus.NEED_INFO,
        tracker_pb2.ApprovalStatus.REVIEW_REQUESTED))

    self.assertFalse(permissions.CanUpdateApprovalStatus(
        {111L, 222L}, permissions.PermissionSet([]), self.PROJECT,
        [333L], tracker_pb2.ApprovalStatus.NEEDS_REVIEW,
        tracker_pb2.ApprovalStatus.NA))

    self.assertFalse(permissions.CanUpdateApprovalStatus(
        {111L, 222L}, permissions.PermissionSet([]), self.PROJECT,
        [333L], tracker_pb2.ApprovalStatus.NOT_APPROVED,
        tracker_pb2.ApprovalStatus.APPROVED))

  def testCanUpdateApprovers_Approver(self):
    self.assertTrue(permissions.CanUpdateApprovers(
        {111L, 222L}, permissions.PermissionSet([]), self.PROJECT,
        [222L]))

  def testCanUpdateApprovers_SiteAdmins(self):
    self.assertTrue(permissions.CanUpdateApprovers(
        {444L}, permissions.PermissionSet([permissions.EDIT_ISSUE_APPROVAL]),
        self.PROJECT, [222L]))

  def testCanUpdateApprovers_NonApprover(self):
    self.assertFalse(permissions.CanUpdateApprovers(
        {111L, 222L}, permissions.PermissionSet([]), self.PROJECT,
        [333L]))

  def testCanViewComponentDef_ComponentAdmin(self):
    cd = tracker_pb2.ComponentDef(admin_ids=[111L])
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanViewComponentDef(
        {111L}, perms, None, cd))
    self.assertFalse(permissions.CanViewComponentDef(
        {999L}, perms, None, cd))

  def testCanViewComponentDef_NormalUser(self):
    cd = tracker_pb2.ComponentDef()
    self.assertTrue(permissions.CanViewComponentDef(
        {111L}, permissions.PermissionSet([permissions.VIEW]),
        None, cd))
    self.assertFalse(permissions.CanViewComponentDef(
        {111L}, permissions.PermissionSet([]),
        None, cd))

  def testCanEditComponentDef_ComponentAdmin(self):
    cd = tracker_pb2.ComponentDef(admin_ids=[111L], path='Whole')
    sub_cd = tracker_pb2.ComponentDef(admin_ids=[222L], path='Whole>Part')
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs.append(cd)
    config.component_defs.append(sub_cd)
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanEditComponentDef(
        {111L}, perms, None, cd, config))
    self.assertFalse(permissions.CanEditComponentDef(
        {222L}, perms, None, cd, config))
    self.assertFalse(permissions.CanEditComponentDef(
        {999L}, perms, None, cd, config))
    self.assertTrue(permissions.CanEditComponentDef(
        {111L}, perms, None, sub_cd, config))
    self.assertTrue(permissions.CanEditComponentDef(
        {222L}, perms, None, sub_cd, config))
    self.assertFalse(permissions.CanEditComponentDef(
        {999L}, perms, None, sub_cd, config))

  def testCanEditComponentDef_ProjectOwners(self):
    cd = tracker_pb2.ComponentDef(path='Whole')
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs.append(cd)
    self.assertTrue(permissions.CanEditComponentDef(
        {111L}, permissions.PermissionSet([permissions.EDIT_PROJECT]),
        None, cd, config))
    self.assertFalse(permissions.CanEditComponentDef(
        {111L}, permissions.PermissionSet([]),
        None, cd, config))

  def testCanViewFieldDef_FieldAdmin(self):
    fd = tracker_pb2.FieldDef(admin_ids=[111L])
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanViewFieldDef(
        {111L}, perms, None, fd))
    self.assertFalse(permissions.CanViewFieldDef(
        {999L}, perms, None, fd))

  def testCanViewFieldDef_NormalUser(self):
    fd = tracker_pb2.FieldDef()
    self.assertTrue(permissions.CanViewFieldDef(
        {111L}, permissions.PermissionSet([permissions.VIEW]),
        None, fd))
    self.assertFalse(permissions.CanViewFieldDef(
        {111L}, permissions.PermissionSet([]),
        None, fd))

  def testCanEditFieldDef_FieldAdmin(self):
    fd = tracker_pb2.FieldDef(admin_ids=[111L])
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanEditFieldDef(
        {111L}, perms, None, fd))
    self.assertFalse(permissions.CanEditFieldDef(
        {999L}, perms, None, fd))

  def testCanEditFieldDef_ProjectOwners(self):
    fd = tracker_pb2.FieldDef()
    self.assertTrue(permissions.CanEditFieldDef(
        {111L}, permissions.PermissionSet([permissions.EDIT_PROJECT]),
        None, fd))
    self.assertFalse(permissions.CanEditFieldDef(
        {111L}, permissions.PermissionSet([]),
        None, fd))

  def testCanViewTemplate_TemplateAdmin(self):
    td = tracker_pb2.TemplateDef(admin_ids=[111L])
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanViewTemplate(
        {111L}, perms, None, td))
    self.assertFalse(permissions.CanViewTemplate(
        {999L}, perms, None, td))

  def testCanViewTemplate_MembersOnly(self):
    td = tracker_pb2.TemplateDef(members_only=True)
    project = project_pb2.Project(committer_ids=[111L])
    self.assertTrue(permissions.CanViewTemplate(
        {111L}, permissions.PermissionSet([]),
        project, td))
    self.assertFalse(permissions.CanViewTemplate(
        {999L}, permissions.PermissionSet([]),
        project, td))

  def testCanViewTemplate_AnyoneWhoCanViewProject(self):
    td = tracker_pb2.TemplateDef()
    self.assertTrue(permissions.CanViewTemplate(
        {111L}, permissions.PermissionSet([permissions.VIEW]),
        None, td))
    self.assertFalse(permissions.CanViewTemplate(
        {111L}, permissions.PermissionSet([]),
        None, td))

  def testCanEditTemplate_TemplateAdmin(self):
    td = tracker_pb2.TemplateDef(admin_ids=[111L])
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanEditTemplate(
        {111L}, perms, None, td))
    self.assertFalse(permissions.CanEditTemplate(
        {999L}, perms, None, td))

  def testCanEditTemplate_ProjectOwners(self):
    td = tracker_pb2.TemplateDef()
    self.assertTrue(permissions.CanEditTemplate(
        {111L}, permissions.PermissionSet([permissions.EDIT_PROJECT]),
        None, td))
    self.assertFalse(permissions.CanEditTemplate(
        {111L}, permissions.PermissionSet([]),
        None, td))

  def testCanViewHotlist_Private(self):
    hotlist = features_pb2.Hotlist()
    hotlist.is_private = True
    hotlist.owner_ids.append(111L)
    hotlist.editor_ids.append(222L)

    self.assertTrue(permissions.CanViewHotlist({222L}, hotlist))
    self.assertTrue(permissions.CanViewHotlist({111L, 333L}, hotlist))
    self.assertFalse(permissions.CanViewHotlist({333L, 444L}, hotlist))

  def testCanViewHotlist_Public(self):
    hotlist = features_pb2.Hotlist()
    hotlist.is_private = False
    hotlist.owner_ids.append(111L)
    hotlist.editor_ids.append(222L)

    self.assertTrue(permissions.CanViewHotlist({222L}, hotlist))
    self.assertTrue(permissions.CanViewHotlist({111L, 333L}, hotlist))
    self.assertTrue(permissions.CanViewHotlist({333L, 444L}, hotlist))

  def testCanEditHotlist(self):
    hotlist = features_pb2.Hotlist()
    hotlist.owner_ids.append(111L)
    hotlist.editor_ids.append(222L)

    self.assertTrue(permissions.CanEditHotlist({222L}, hotlist))
    self.assertTrue(permissions.CanEditHotlist({111L, 333L}, hotlist))
    self.assertFalse(permissions.CanEditHotlist({333L, 444L}, hotlist))

  def testCanAdministerHotlist(self):
    hotlist = features_pb2.Hotlist()
    hotlist.owner_ids.append(111L)
    hotlist.editor_ids.append(222L)

    self.assertFalse(permissions.CanAdministerHotlist({222L}, hotlist))
    self.assertTrue(permissions.CanAdministerHotlist({111L, 333L}, hotlist))
    self.assertFalse(permissions.CanAdministerHotlist({333L, 444L}, hotlist))
