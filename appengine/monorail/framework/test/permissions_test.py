# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for permissions.py."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

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
    self.proj.contributor_ids.append(111)
    self.proj.contributor_ids.append(222)
    self.proj.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=111, perms=['Cc', 'D', 'e', 'Ff']))
    self.proj.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=222, perms=['G', 'H']))
    # user 3 used to be a member and had extra perms, but no longer in project.
    self.proj.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=333, perms=['G', 'H']))

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
    effective_ids = {111}
    self.assertTrue(self.perms.CanUsePerm('A', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm('D', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm(
        'D', effective_ids, self.proj, ['Restrict-D-A']))
    self.assertFalse(self.perms.CanUsePerm('G', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('Z', effective_ids, self.proj, []))

    effective_ids = {222}
    self.assertTrue(self.perms.CanUsePerm('A', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('D', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm('G', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm('Z', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm(
        'Z', effective_ids, self.proj, ['Restrict-Z-A']))

  def testCanUsePerm_SignedInWithGroups(self):
    effective_ids = {111, 222, 333}
    self.assertTrue(self.perms.CanUsePerm('A', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm('D', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm('G', effective_ids, self.proj, []))
    self.assertTrue(self.perms.CanUsePerm(
        'G', effective_ids, self.proj, ['Restrict-G-D']))
    self.assertFalse(self.perms.CanUsePerm('Z', effective_ids, self.proj, []))
    self.assertFalse(self.perms.CanUsePerm(
        'G', effective_ids, self.proj, ['Restrict-G-Z']))

  def testCanUsePerm_FormerMember(self):
    effective_ids = {333}
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
    self.assertTrue(self.perms.HasPerm('d', 111, self.proj))
    self.assertTrue(self.perms.HasPerm('D', 111, self.proj))
    self.assertTrue(self.perms.HasPerm('Cc', 111, self.proj))
    self.assertTrue(self.perms.HasPerm('CC', 111, self.proj))
    self.assertFalse(self.perms.HasPerm('Z', 111, self.proj))

    self.assertFalse(self.perms.HasPerm('d', 222, self.proj))
    self.assertFalse(self.perms.HasPerm('D', 222, self.proj))

    # Only current members can have extra permissions
    self.proj.contributor_ids = []
    self.assertFalse(self.perms.HasPerm('d', 111, self.proj))

    # TODO(jrobbins): also test consider_restrictions=False and
    # restriction labels directly in this class.

  def testHasPerm_OverrideExtraPerms(self):
    # D is an extra perm for 111...
    self.assertTrue(self.perms.HasPerm('d', 111, self.proj))
    self.assertTrue(self.perms.HasPerm('D', 111, self.proj))
    # ...unless we tell HasPerm it isn't.
    self.assertFalse(self.perms.HasPerm('d', 111, self.proj, []))
    self.assertFalse(self.perms.HasPerm('D', 111, self.proj, []))
    # Perms in self.perms are still considered
    self.assertTrue(self.perms.HasPerm('Cc', 111, self.proj, []))
    self.assertTrue(self.perms.HasPerm('CC', 111, self.proj, []))
    # Z is not an extra perm...
    self.assertFalse(self.perms.HasPerm('Z', 111, self.proj))
    # ...unless we tell HasPerm it is.
    self.assertTrue(self.perms.HasPerm('Z', 111, self.proj, ['z']))

  def testHasPerm_GrantedPerms(self):
    self.assertTrue(self.perms.CanUsePerm(
        'A', {111}, self.proj, [], granted_perms=['z']))
    self.assertTrue(self.perms.CanUsePerm(
        'a', {111}, self.proj, [], granted_perms=['z']))
    self.assertTrue(self.perms.CanUsePerm(
        'a', {111}, self.proj, [], granted_perms=['a']))
    self.assertTrue(self.perms.CanUsePerm(
        'Z', {111}, self.proj, [], granted_perms=['y', 'z']))
    self.assertTrue(self.perms.CanUsePerm(
        'z', {111}, self.proj, [], granted_perms=['y', 'z']))
    self.assertFalse(self.perms.CanUsePerm(
        'z', {111}, self.proj, [], granted_perms=['y']))

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
  COMMITTER_USER_ID = 111
  OWNER_USER_ID = 222
  CONTRIB_USER_ID = 333
  SITE_ADMIN_USER_ID = 444

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
    self.normal_artifact.reporter_id = 111

    # Two PermissionSets w/ permissions outside of any project.
    self.normal_user_perms = permissions.GetPermissions(
        None, {111}, None)
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
            999, self.live_project))

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
    project.committer_ids.append(222)
    # User 1 is a former member with left-over extra perms that don't count.
    project.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=111, perms=['a', 'b', 'c']))
    project.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=222, perms=['a', 'b', 'c']))

    self.assertListEqual(
        [],
        permissions.GetExtraPerms(project, 111))
    self.assertListEqual(
        ['a', 'b', 'c'],
        permissions.GetExtraPerms(project, 222))
    self.assertListEqual(
        [],
        permissions.GetExtraPerms(project, 333))

  def testCanDeleteComment_NoPermissionSet(self):
    """Test that if no PermissionSet is given, we can't delete comments."""
    comment = tracker_pb2.IssueComment()
    commenter = user_pb2.User()
    # If no PermissionSet is given, the user cannot delete the comment.
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 111, None))
    # Same, with no user specified.
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, framework_constants.NO_USER_SPECIFIED, None))

  def testCanDeleteComment_AnonUsersCannotDelete(self):
    """Test that anon users can't delete comments."""
    comment = tracker_pb2.IssueComment()
    commenter = user_pb2.User()
    perms = permissions.PermissionSet([permissions.DELETE_ANY])

    # No logged in user, even with perms from somewhere.
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, framework_constants.NO_USER_SPECIFIED, perms))

    # No logged in user, even if artifact was already deleted.
    comment.deleted_by = 111
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, framework_constants.NO_USER_SPECIFIED, perms))

  def testCanDeleteComment_DeleteAny(self):
    """Test that users with DeleteAny permission can delete any comment.

    Except for spam comments or comments by banned users.
    """
    comment = tracker_pb2.IssueComment(user_id=111)
    commenter = user_pb2.User()
    perms = permissions.PermissionSet([permissions.DELETE_ANY])

    # Users with DeleteAny permission can delete their own comments.
    self.assertTrue(permissions.CanDeleteComment(
        comment, commenter, 111, perms))

    # And also comments by other users
    comment.user_id = 999
    self.assertTrue(permissions.CanDeleteComment(
        comment, commenter, 111, perms))

    # As well as undelete comments they deleted.
    comment.deleted_by = 111
    self.assertTrue(permissions.CanDeleteComment(
        comment, commenter, 111, perms))

    # Or that other users deleted.
    comment.deleted_by = 222
    self.assertTrue(permissions.CanDeleteComment(
        comment, commenter, 111, perms))

  def testCanDeleteComment_DeleteOwn(self):
    """Test that users with DeleteOwn permission can delete any comment.

    Except for spam comments or comments by banned users.
    """
    comment = tracker_pb2.IssueComment(user_id=111)
    commenter = user_pb2.User()
    perms = permissions.PermissionSet([permissions.DELETE_OWN])

    # Users with DeleteOwn permission can delete their own comments.
    self.assertTrue(permissions.CanDeleteComment(
        comment, commenter, 111, perms))

    # But not comments by other users
    comment.user_id = 999
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 111, perms))

    # They can undelete comments they deleted.
    comment.user_id = 111
    comment.deleted_by = 111
    self.assertTrue(permissions.CanDeleteComment(
        comment, commenter, 111, perms))

    # But not comments that other users deleted.
    comment.deleted_by = 222
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 111, perms))

  def testCanDeleteComment_CannotDeleteSpamComments(self):
    """Test that nobody can (un)delete comments marked as spam."""
    comment = tracker_pb2.IssueComment(user_id=111, is_spam=True)
    commenter = user_pb2.User()

    # Nobody can delete comments marked as spam.
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 111,
        permissions.PermissionSet([permissions.DELETE_OWN])))
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 222,
        permissions.PermissionSet([permissions.DELETE_ANY])))

    # Nobody can undelete comments marked as spam.
    comment.deleted_by = 222
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 111,
        permissions.PermissionSet([permissions.DELETE_OWN])))
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 222,
        permissions.PermissionSet([permissions.DELETE_ANY])))

  def testCanDeleteComment_CannotDeleteCommentsByBannedUser(self):
    """Test that nobody can (un)delete comments by banned users."""
    comment = tracker_pb2.IssueComment(user_id=111)
    commenter = user_pb2.User(banned='Some reason')

    # Nobody can delete comments by banned users.
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 111,
        permissions.PermissionSet([permissions.DELETE_OWN])))
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 222,
        permissions.PermissionSet([permissions.DELETE_ANY])))

    # Nobody can undelete comments by banned users.
    comment.deleted_by = 222
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 111,
        permissions.PermissionSet([permissions.DELETE_OWN])))
    self.assertFalse(permissions.CanDeleteComment(
        comment, commenter, 222,
        permissions.PermissionSet([permissions.DELETE_ANY])))

  def testCanFlagComment_FlagSpamCanReport(self):
    """Test that users with FlagSpam permissions can report comments."""
    comment = tracker_pb2.IssueComment()
    commenter = user_pb2.User()

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [], 111,
        permissions.PermissionSet([permissions.FLAG_SPAM]))

    self.assertTrue(can_flag)
    self.assertFalse(is_flagged)

  def testCanFlagComment_FlagSpamCanUnReportOwn(self):
    """Test that users with FlagSpam permission can un-report comments they
    previously reported."""
    comment = tracker_pb2.IssueComment()
    commenter = user_pb2.User()

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [111], 111,
        permissions.PermissionSet([permissions.FLAG_SPAM]))

    self.assertTrue(can_flag)
    self.assertTrue(is_flagged)

  def testCanFlagComment_FlagSpamCannotUnReportOthers(self):
    """Test that users with FlagSpam permission doesn't know if other users have
    reported a comment as spam."""
    comment = tracker_pb2.IssueComment()
    commenter = user_pb2.User()

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [222], 111,
        permissions.PermissionSet([permissions.FLAG_SPAM]))

    self.assertTrue(can_flag)
    self.assertFalse(is_flagged)

  def testCanFlagComment_FlagSpamCannotUnFlag(self):
    comment = tracker_pb2.IssueComment(is_spam=True)
    commenter = user_pb2.User()

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [111], 111,
        permissions.PermissionSet([permissions.FLAG_SPAM]))

    self.assertFalse(can_flag)
    self.assertTrue(is_flagged)

  def testCanFlagComment_VerdictSpamCanFlag(self):
    """Test that users with FlagSpam permissions can flag comments."""
    comment = tracker_pb2.IssueComment()
    commenter = user_pb2.User()

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [], 111,
        permissions.PermissionSet([permissions.VERDICT_SPAM]))

    self.assertTrue(can_flag)
    self.assertFalse(is_flagged)

  def testCanFlagComment_VerdictSpamCanUnFlag(self):
    """Test that users with FlagSpam permissions can un-flag comments."""
    comment = tracker_pb2.IssueComment(is_spam=True)
    commenter = user_pb2.User()

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [], 111,
        permissions.PermissionSet([permissions.VERDICT_SPAM]))

    self.assertTrue(can_flag)
    self.assertTrue(is_flagged)

  def testCanFlagComment_CannotFlagNoPermission(self):
    """Test that users without permission cannot flag comments."""
    comment = tracker_pb2.IssueComment()
    commenter = user_pb2.User()

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [], 111,
        permissions.PermissionSet([permissions.DELETE_ANY]))

    self.assertFalse(can_flag)
    self.assertFalse(is_flagged)

  def testCanFlagComment_CannotUnFlagNoPermission(self):
    """Test that users without permission cannot un-flag comments."""
    comment = tracker_pb2.IssueComment(is_spam=True)
    commenter = user_pb2.User()

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [], 111,
        # Users need the VerdictSpam permission to be able to un-flag comments.
        permissions.PermissionSet([
            permissions.DELETE_ANY, permissions.FLAG_SPAM]))

    self.assertFalse(can_flag)
    self.assertTrue(is_flagged)

  def testCanFlagComment_CannotFlagCommentByBannedUser(self):
    """Test that nobady can flag comments by banned users."""
    comment = tracker_pb2.IssueComment()
    commenter = user_pb2.User(banned='Some reason')

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [], 111,
        permissions.PermissionSet([
            permissions.FLAG_SPAM, permissions.VERDICT_SPAM]))

    self.assertFalse(can_flag)
    self.assertFalse(is_flagged)

  def testCanFlagComment_CannotUnFlagCommentByBannedUser(self):
    """Test that nobady can un-flag comments by banned users."""
    comment = tracker_pb2.IssueComment(is_spam=True)
    commenter = user_pb2.User(banned='Some reason')

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [], 111,
        permissions.PermissionSet([
            permissions.FLAG_SPAM, permissions.VERDICT_SPAM]))

    self.assertFalse(can_flag)
    self.assertTrue(is_flagged)

  def testCanFlagComment_CanUnFlagDeletedSpamComment(self):
    """Test that we can un-flag a deleted comment that is spam."""
    comment = tracker_pb2.IssueComment(is_spam=True, deleted_by=111)
    commenter = user_pb2.User()

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [], 222,
        permissions.PermissionSet([permissions.VERDICT_SPAM]))

    self.assertTrue(can_flag)
    self.assertTrue(is_flagged)

  def testCanFlagComment_CannotFlagDeletedComment(self):
    """Test that nobody can flag a deleted comment that is not spam."""
    comment = tracker_pb2.IssueComment(deleted_by=111)
    commenter = user_pb2.User()

    can_flag, is_flagged = permissions.CanFlagComment(
        comment, commenter, [], 111,
        permissions.PermissionSet([
            permissions.FLAG_SPAM, permissions.VERDICT_SPAM,
            permissions.DELETE_ANY, permissions.DELETE_OWN]))

    self.assertFalse(can_flag)
    self.assertFalse(is_flagged)

  def testCanViewComment_Normal(self):
    """Test that we can view comments."""
    comment = tracker_pb2.IssueComment()
    commenter = user_pb2.User()
    # We assume that CanViewIssue was already called. There are no further
    # restrictions to view this comment.
    self.assertTrue(permissions.CanViewComment(
        comment, commenter, 111, None))

  def testCanViewComment_CannotViewCommentsByBannedUser(self):
    """Test that nobody can view comments by banned users."""
    comment = tracker_pb2.IssueComment(user_id=111)
    commenter = user_pb2.User(banned='Some reason')

    # Nobody can view comments by banned users.
    self.assertFalse(permissions.CanViewComment(
        comment, commenter, 111, permissions.ADMIN_PERMISSIONSET))

  def testCanViewComment_OnlyModeratorsCanViewSpamComments(self):
    """Test that only users with VerdictSpam can view spam comments."""
    comment = tracker_pb2.IssueComment(user_id=111, is_spam=True)
    commenter = user_pb2.User()

    # Users with VerdictSpam permission can view comments marked as spam.
    self.assertTrue(permissions.CanViewComment(
        comment, commenter, 222,
        permissions.PermissionSet([permissions.VERDICT_SPAM])))

    # Other users cannot view comments marked as spam, even if it is their own
    # comment.
    self.assertFalse(permissions.CanViewComment(
        comment, commenter, 111,
        permissions.PermissionSet([
            permissions.FLAG_SPAM, permissions.DELETE_ANY,
            permissions.DELETE_OWN])))

  def testCanViewComment_DeletedComment(self):
    """Test that for deleted comments, only the users that can undelete it can
    view it.
    """
    comment = tracker_pb2.IssueComment(user_id=111, deleted_by=222)
    commenter = user_pb2.User()

    # Users with DeleteAny permission can view all deleted comments.
    self.assertTrue(permissions.CanViewComment(
        comment, commenter, 333,
        permissions.PermissionSet([permissions.DELETE_ANY])))

    # Users with DeleteOwn permissions can only see their own comments if they
    # deleted them.
    comment.user_id = comment.deleted_by = 333
    self.assertTrue(permissions.CanViewComment(
        comment, commenter, 333,
        permissions.PermissionSet([permissions.DELETE_OWN])))

    # But not comments they didn't delete.
    comment.deleted_by = 111
    self.assertFalse(permissions.CanViewComment(
        comment, commenter, 333,
        permissions.PermissionSet([permissions.DELETE_OWN])))

  def testCanViewInboundMessage(self):
    comment = tracker_pb2.IssueComment(user_id=111)

    # Users can view their own inbound messages
    self.assertTrue(permissions.CanViewInboundMessage(
        comment, 111, permissions.EMPTY_PERMISSIONSET))

    # Users with the ViewInboundMessages permissions can view inbound messages.
    self.assertTrue(permissions.CanViewInboundMessage(
        comment, 333,
        permissions.PermissionSet([permissions.VIEW_INBOUND_MESSAGES])))

    # Other users cannot view inbound messages.
    self.assertFalse(permissions.CanViewInboundMessage(
        comment, 333,
        permissions.PermissionSet([permissions.VIEW])))

  def testCanViewNormalArifact(self):
    # Anyone can view a non-restricted artifact.
    self.assertTrue(permissions.CanView(
        {111}, permissions.READ_ONLY_PERMISSIONSET,
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
        permissions.PermissionSet([]), {111}, {111}))

  def testCanEditGroup_Otherwise(self):
    self.assertFalse(permissions.CanEditGroup(
        permissions.PermissionSet([]), {111}, {222}))

  def testCanViewGroupMembers_HasPerm(self):
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([permissions.VIEW_GROUP]),
        None, None, None, None, None))

  def testCanViewGroupMembers_IsMemberOfFriendProject(self):
    group_settings = usergroup_pb2.MakeSettings('owners', friend_projects=[890])
    self.assertFalse(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {111}, group_settings, {222}, {333}, {789}))
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {111}, group_settings, {222}, {333}, {789, 890}))

  def testCanViewGroupMembers_VisibleToOwner(self):
    group_settings = usergroup_pb2.MakeSettings('owners')
    self.assertFalse(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {111}, group_settings, {222}, {333}, {789}))
    self.assertFalse(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {222}, group_settings, {222}, {333}, {789}))
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {333}, group_settings, {222}, {333}, {789}))

  def testCanViewGroupMembers_IsVisibleToMember(self):
    group_settings = usergroup_pb2.MakeSettings('members')
    self.assertFalse(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {111}, group_settings, {222}, {333}, {789}))
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {222}, group_settings, {222}, {333}, {789}))
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {333}, group_settings, {222}, {333}, {789}))

  def testCanViewGroupMembers_AnyoneCanView(self):
    group_settings = usergroup_pb2.MakeSettings('anyone')
    self.assertTrue(permissions.CanViewGroupMembers(
        permissions.PermissionSet([]),
        {111}, group_settings, {222}, {333}, {789}))

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
    self.proj.committer_ids.append(111)
    self.proj.extra_perms.append(project_pb2.Project.ExtraPerms(
        member_id=111, perms=['d']))

    # Note: z is an example of a perm that the user does not have.
    # Note: q is an example of an irrelevant perm that the user does not have.

  def DoCanUsePerm(self, perm, project='default', user_id=None, restrict=''):
    """Wrapper function to call CanUsePerm()."""
    if project == 'default':
      project = self.proj
    return self.perms.CanUsePerm(
        perm, {user_id or 111}, project, restrict.split())

  def testHasPermNoRestrictions(self):
    self.assertTrue(self.DoCanUsePerm('a'))
    self.assertTrue(self.DoCanUsePerm('A'))
    self.assertFalse(self.DoCanUsePerm('z'))
    self.assertTrue(self.DoCanUsePerm('d'))
    self.assertFalse(self.DoCanUsePerm('d', user_id=222))
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
    self.mr.auth.effective_ids = {111}
    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.assertTrue(permissions.ShouldCheckForAbandonment(self.mr))

  def testNonOwner(self):
    self.mr.auth.effective_ids = {222}
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.assertFalse(permissions.ShouldCheckForAbandonment(self.mr))
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.assertFalse(permissions.ShouldCheckForAbandonment(self.mr))
    self.mr.perms = permissions.USER_PERMISSIONSET
    self.assertFalse(permissions.ShouldCheckForAbandonment(self.mr))
    self.mr.perms = permissions.EMPTY_PERMISSIONSET
    self.assertFalse(permissions.ShouldCheckForAbandonment(self.mr))

  def testSiteAdmin(self):
    self.mr.auth.effective_ids = {111}
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


REPORTER_ID = 111
OWNER_ID = 222
CC_ID = 333
OTHER_ID = 444
APPROVER_ID = 555


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

  ADMIN_PERMS = permissions.ADMIN_PERMISSIONSET
  PERMS = permissions.EMPTY_PERMISSIONSET

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

  def testUpdateIssuePermissions_FromConfig(self):
    config = tracker_pb2.ProjectIssueConfig(
        field_defs=[tracker_pb2.FieldDef(field_id=123, grants_perm='Granted')])
    issue = tracker_pb2.Issue(
        field_values=[tracker_pb2.FieldValue(field_id=123, user_id=111)])
    perms = permissions.UpdateIssuePermissions(
        permissions.USER_PERMISSIONSET, self.PROJECT, issue, {111},
        config=config)
    self.assertIn('granted', perms.perm_names)

  def testUpdateIssuePermissions_ExtraPerms(self):
    project = project_pb2.Project()
    project.committer_ids.append(999)
    project.extra_perms.append(
        project_pb2.Project.ExtraPerms(member_id=999, perms=['EditIssue']))
    perms = permissions.UpdateIssuePermissions(
        permissions.USER_PERMISSIONSET, project,
        self.REGULAR_ISSUE, {999})
    self.assertIn('editissue', perms.perm_names)

  def testUpdateIssuePermissions_ExtraPermsAreSubjectToRestrictions(self):
    project = project_pb2.Project()
    project.committer_ids.append(999)
    project.extra_perms.append(
        project_pb2.Project.ExtraPerms(member_id=999, perms=['EditIssue']))
    perms = permissions.UpdateIssuePermissions(
        permissions.USER_PERMISSIONSET, project,
        self.RESTRICTED_ISSUE3, {999})
    self.assertNotIn('editissue', perms.perm_names)

  def testUpdateIssuePermissions_GrantedPermsAreNotSubjectToRestrictions(self):
    perms = permissions.UpdateIssuePermissions(
        permissions.USER_PERMISSIONSET, self.PROJECT, self.RESTRICTED_ISSUE3,
        {}, granted_perms=['EditIssue'])
    self.assertIn('editissue', perms.perm_names)

  def testUpdateIssuePermissions_RespectConsiderRestrictions(self):
    perms = permissions.UpdateIssuePermissions(
        permissions.ADMIN_PERMISSIONSET, self.PROJECT, self.RESTRICTED_ISSUE3,
        {})
    self.assertIn('editissue', perms.perm_names)

  def testUpdateIssuePermissions_RestrictionsAreConsideredIndividually(self):
    issue = tracker_pb2.Issue(
        labels=[
            'Restrict-Perm1-Perm2',
            'Restrict-Perm2-Perm3'])
    perms = permissions.UpdateIssuePermissions(
        permissions.PermissionSet(['Perm1', 'Perm2', 'View']),
        self.PROJECT, issue, {})
    self.assertIn('perm1', perms.perm_names)
    self.assertNotIn('perm2', perms.perm_names)

  def testUpdateIssuePermissions_DeletedNoPermissions(self):
    issue = tracker_pb2.Issue(
        labels=['Restrict-View-Foo'],
        deleted=True)
    perms = permissions.UpdateIssuePermissions(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET, self.PROJECT, issue, {})
    self.assertEqual([], sorted(perms.perm_names))

  def testUpdateIssuePermissions_ViewDeleted(self):
    perms = permissions.UpdateIssuePermissions(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET, self.PROJECT,
        self.DELETED_ISSUE, {})
    self.assertEqual(['view'], sorted(perms.perm_names))

  def testUpdateIssuePermissions_ViewAndDeleteDeleted(self):
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

  def testUpdateIssuePermissions_RolesAllowViewingDeleted(self):
    issue = tracker_pb2.Issue(
        reporter_id=REPORTER_ID,
        owner_id=OWNER_ID,
        cc_ids=[CC_ID],
        approval_values=[tracker_pb2.ApprovalValue(approver_ids=[APPROVER_ID])],
        labels=['Restrict-View-Foo'],
        deleted=True)
    for role in {OWNER_ID, REPORTER_ID, CC_ID, APPROVER_ID}:
      perms = permissions.UpdateIssuePermissions(
          permissions.USER_PERMISSIONSET, self.PROJECT, issue, {role})
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
    project.committer_ids.append(999)
    project.extra_perms.append(
        project_pb2.Project.ExtraPerms(member_id=999, perms=['Foo']))
    perms = permissions.UpdateIssuePermissions(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET, project,
        self.RESTRICTED_ISSUE3, {999})
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
        {111}, permissions.PermissionSet([permissions.ADD_ISSUE_COMMENT]),
        None, None))
    self.assertFalse(permissions.CanCommentIssue(
        {111}, permissions.PermissionSet([]),
        None, None))

  def testCanCommentIssue_HasExtraPerm(self):
    project = project_pb2.Project()
    project.committer_ids.append(111)
    extra_perm = project_pb2.Project.ExtraPerms(
        member_id=111, perms=[permissions.ADD_ISSUE_COMMENT])
    project.extra_perms.append(extra_perm)
    self.assertTrue(permissions.CanCommentIssue(
        {111}, permissions.PermissionSet([]),
        project, None))
    self.assertFalse(permissions.CanCommentIssue(
        {222}, permissions.PermissionSet([]),
        project, None))

  def testCanCommentIssue_Restricted(self):
    issue = tracker_pb2.Issue(labels=['Restrict-AddIssueComment-CoreTeam'])
    # User is granted exactly the perm they need specifically in this issue.
    self.assertTrue(permissions.CanCommentIssue(
        {111}, permissions.PermissionSet([]),
        None, issue, granted_perms=['addissuecomment']))
    # User is granted CoreTeam, which satifies the restriction, and allows
    # them to use the AddIssueComment permission that they have and would
    # normally be able to use in an unrestricted issue.
    self.assertTrue(permissions.CanCommentIssue(
        {111}, permissions.PermissionSet([permissions.ADD_ISSUE_COMMENT]),
        None, issue, granted_perms=['coreteam']))
    # User was granted CoreTeam, but never had AddIssueComment.
    self.assertFalse(permissions.CanCommentIssue(
        {111}, permissions.PermissionSet([]),
        None, issue, granted_perms=['coreteam']))
    # User has AddIssueComment, but cannot satisfy restriction.
    self.assertFalse(permissions.CanCommentIssue(
        {111}, permissions.PermissionSet([permissions.ADD_ISSUE_COMMENT]),
        None, issue))

  def testCanCommentIssue_Granted(self):
    self.assertTrue(permissions.CanCommentIssue(
        {111}, permissions.PermissionSet([]),
        None, None, granted_perms=['addissuecomment']))
    self.assertFalse(permissions.CanCommentIssue(
        {111}, permissions.PermissionSet([]),
        None, None))

  def testCanUpdateApprovalStatus_Approver(self):
    # restricted status
    self.assertTrue(permissions.CanUpdateApprovalStatus(
        {111, 222}, permissions.PermissionSet([]), self.PROJECT,
        [222], tracker_pb2.ApprovalStatus.APPROVED))

    # non-restricted status
    self.assertTrue(permissions.CanUpdateApprovalStatus(
        {111, 222}, permissions.PermissionSet([]), self.PROJECT,
        [222], tracker_pb2.ApprovalStatus.NEEDS_REVIEW))

  def testCanUpdateApprovalStatus_SiteAdmin(self):
    # restricted status
    self.assertTrue(permissions.CanUpdateApprovalStatus(
        {444}, permissions.PermissionSet([permissions.EDIT_ISSUE_APPROVAL]),
        self.PROJECT, [222], tracker_pb2.ApprovalStatus.NOT_APPROVED))

    # non-restricted status
    self.assertTrue(permissions.CanUpdateApprovalStatus(
        {444}, permissions.PermissionSet([permissions.EDIT_ISSUE_APPROVAL]),
        self.PROJECT, [222], tracker_pb2.ApprovalStatus.NEEDS_REVIEW))

  def testCanUpdateApprovalStatus_NonApprover(self):
    # non-restricted status
    self.assertTrue(permissions.CanUpdateApprovalStatus(
        {111, 222}, permissions.PermissionSet([]), self.PROJECT,
        [333], tracker_pb2.ApprovalStatus.NEED_INFO))

    # restricted status
    self.assertFalse(permissions.CanUpdateApprovalStatus(
        {111, 222}, permissions.PermissionSet([]), self.PROJECT,
        [333], tracker_pb2.ApprovalStatus.NA))

  def testCanUpdateApprovers_Approver(self):
    self.assertTrue(permissions.CanUpdateApprovers(
        {111, 222}, permissions.PermissionSet([]), self.PROJECT,
        [222]))

  def testCanUpdateApprovers_SiteAdmins(self):
    self.assertTrue(permissions.CanUpdateApprovers(
        {444}, permissions.PermissionSet([permissions.EDIT_ISSUE_APPROVAL]),
        self.PROJECT, [222]))

  def testCanUpdateApprovers_NonApprover(self):
    self.assertFalse(permissions.CanUpdateApprovers(
        {111, 222}, permissions.PermissionSet([]), self.PROJECT,
        [333]))

  def testCanViewComponentDef_ComponentAdmin(self):
    cd = tracker_pb2.ComponentDef(admin_ids=[111])
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanViewComponentDef(
        {111}, perms, None, cd))
    self.assertFalse(permissions.CanViewComponentDef(
        {999}, perms, None, cd))

  def testCanViewComponentDef_NormalUser(self):
    cd = tracker_pb2.ComponentDef()
    self.assertTrue(permissions.CanViewComponentDef(
        {111}, permissions.PermissionSet([permissions.VIEW]),
        None, cd))
    self.assertFalse(permissions.CanViewComponentDef(
        {111}, permissions.PermissionSet([]),
        None, cd))

  def testCanEditComponentDef_ComponentAdmin(self):
    cd = tracker_pb2.ComponentDef(admin_ids=[111], path='Whole')
    sub_cd = tracker_pb2.ComponentDef(admin_ids=[222], path='Whole>Part')
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs.append(cd)
    config.component_defs.append(sub_cd)
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanEditComponentDef(
        {111}, perms, None, cd, config))
    self.assertFalse(permissions.CanEditComponentDef(
        {222}, perms, None, cd, config))
    self.assertFalse(permissions.CanEditComponentDef(
        {999}, perms, None, cd, config))
    self.assertTrue(permissions.CanEditComponentDef(
        {111}, perms, None, sub_cd, config))
    self.assertTrue(permissions.CanEditComponentDef(
        {222}, perms, None, sub_cd, config))
    self.assertFalse(permissions.CanEditComponentDef(
        {999}, perms, None, sub_cd, config))

  def testCanEditComponentDef_ProjectOwners(self):
    cd = tracker_pb2.ComponentDef(path='Whole')
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs.append(cd)
    self.assertTrue(permissions.CanEditComponentDef(
        {111}, permissions.PermissionSet([permissions.EDIT_PROJECT]),
        None, cd, config))
    self.assertFalse(permissions.CanEditComponentDef(
        {111}, permissions.PermissionSet([]),
        None, cd, config))

  def testCanViewFieldDef_FieldAdmin(self):
    fd = tracker_pb2.FieldDef(admin_ids=[111])
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanViewFieldDef(
        {111}, perms, None, fd))
    self.assertFalse(permissions.CanViewFieldDef(
        {999}, perms, None, fd))

  def testCanViewFieldDef_NormalUser(self):
    fd = tracker_pb2.FieldDef()
    self.assertTrue(permissions.CanViewFieldDef(
        {111}, permissions.PermissionSet([permissions.VIEW]),
        None, fd))
    self.assertFalse(permissions.CanViewFieldDef(
        {111}, permissions.PermissionSet([]),
        None, fd))

  def testCanEditFieldDef_FieldAdmin(self):
    fd = tracker_pb2.FieldDef(admin_ids=[111])
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanEditFieldDef(
        {111}, perms, None, fd))
    self.assertFalse(permissions.CanEditFieldDef(
        {999}, perms, None, fd))

  def testCanEditFieldDef_ProjectOwners(self):
    fd = tracker_pb2.FieldDef()
    self.assertTrue(permissions.CanEditFieldDef(
        {111}, permissions.PermissionSet([permissions.EDIT_PROJECT]),
        None, fd))
    self.assertFalse(permissions.CanEditFieldDef(
        {111}, permissions.PermissionSet([]),
        None, fd))

  def testCanViewTemplate_TemplateAdmin(self):
    td = tracker_pb2.TemplateDef(admin_ids=[111])
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanViewTemplate(
        {111}, perms, None, td))
    self.assertFalse(permissions.CanViewTemplate(
        {999}, perms, None, td))

  def testCanViewTemplate_MembersOnly(self):
    td = tracker_pb2.TemplateDef(members_only=True)
    project = project_pb2.Project(committer_ids=[111])
    self.assertTrue(permissions.CanViewTemplate(
        {111}, permissions.PermissionSet([]),
        project, td))
    self.assertFalse(permissions.CanViewTemplate(
        {999}, permissions.PermissionSet([]),
        project, td))

  def testCanViewTemplate_AnyoneWhoCanViewProject(self):
    td = tracker_pb2.TemplateDef()
    self.assertTrue(permissions.CanViewTemplate(
        {111}, permissions.PermissionSet([permissions.VIEW]),
        None, td))
    self.assertFalse(permissions.CanViewTemplate(
        {111}, permissions.PermissionSet([]),
        None, td))

  def testCanEditTemplate_TemplateAdmin(self):
    td = tracker_pb2.TemplateDef(admin_ids=[111])
    perms = permissions.PermissionSet([])
    self.assertTrue(permissions.CanEditTemplate(
        {111}, perms, None, td))
    self.assertFalse(permissions.CanEditTemplate(
        {999}, perms, None, td))

  def testCanEditTemplate_ProjectOwners(self):
    td = tracker_pb2.TemplateDef()
    self.assertTrue(permissions.CanEditTemplate(
        {111}, permissions.PermissionSet([permissions.EDIT_PROJECT]),
        None, td))
    self.assertFalse(permissions.CanEditTemplate(
        {111}, permissions.PermissionSet([]),
        None, td))

  def testCanViewHotlist_Private(self):
    hotlist = features_pb2.Hotlist()
    hotlist.is_private = True
    hotlist.owner_ids.append(111)
    hotlist.editor_ids.append(222)

    self.assertTrue(permissions.CanViewHotlist({222}, self.PERMS, hotlist))
    self.assertTrue(permissions.CanViewHotlist({111, 333}, self.PERMS, hotlist))
    self.assertTrue(
        permissions.CanViewHotlist({111, 333}, self.ADMIN_PERMS, hotlist))
    self.assertFalse(
        permissions.CanViewHotlist({333, 444}, self.PERMS, hotlist))
    self.assertTrue(
        permissions.CanViewHotlist({333, 444}, self.ADMIN_PERMS, hotlist))

  def testCanViewHotlist_Public(self):
    hotlist = features_pb2.Hotlist()
    hotlist.is_private = False
    hotlist.owner_ids.append(111)
    hotlist.editor_ids.append(222)

    self.assertTrue(permissions.CanViewHotlist({222}, self.PERMS, hotlist))
    self.assertTrue(permissions.CanViewHotlist({111, 333}, self.PERMS, hotlist))
    self.assertTrue(permissions.CanViewHotlist({333, 444}, self.PERMS, hotlist))
    self.assertTrue(
        permissions.CanViewHotlist({333, 444}, self.ADMIN_PERMS, hotlist))

  def testCanEditHotlist(self):
    hotlist = features_pb2.Hotlist()
    hotlist.owner_ids.append(111)
    hotlist.editor_ids.append(222)

    self.assertTrue(permissions.CanEditHotlist({222}, self.PERMS, hotlist))
    self.assertTrue(permissions.CanEditHotlist({111, 333}, self.PERMS, hotlist))
    self.assertTrue(
        permissions.CanEditHotlist({111, 333}, self.ADMIN_PERMS, hotlist))
    self.assertFalse(
        permissions.CanEditHotlist({333, 444}, self.PERMS, hotlist))
    self.assertTrue(
        permissions.CanEditHotlist({333, 444}, self.ADMIN_PERMS, hotlist))

  def testCanAdministerHotlist(self):
    hotlist = features_pb2.Hotlist()
    hotlist.owner_ids.append(111)
    hotlist.editor_ids.append(222)

    self.assertFalse(
        permissions.CanAdministerHotlist({222}, self.PERMS, hotlist))
    self.assertTrue(
        permissions.CanAdministerHotlist({111, 333}, self.PERMS, hotlist))
    self.assertTrue(
        permissions.CanAdministerHotlist({111, 333}, self.ADMIN_PERMS, hotlist))
    self.assertFalse(
        permissions.CanAdministerHotlist({333, 444}, self.PERMS, hotlist))
    self.assertTrue(
        permissions.CanAdministerHotlist({333, 444}, self.ADMIN_PERMS, hotlist))
