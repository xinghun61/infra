# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for helpers module."""

import unittest

from framework import framework_views
from framework import permissions
from project import project_helpers
from proto import project_pb2
from services import service_manager
from testing import fake


class HelpersUnitTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake sql connection'
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService())
    self.services.user.TestAddUser('a@example.com', 111L)
    self.services.user.TestAddUser('b@example.com', 222L)
    self.services.user.TestAddUser('c@example.com', 333L)
    self.users_by_id = framework_views.MakeAllUserViews(
        'cnxn', self.services.user, [111L, 222L, 333L])
    self.effective_ids_by_user = {user: set() for user in {111L, 222L, 333L}}

  def testBuildProjectMembers(self):
    project = project_pb2.MakeProject(
        'proj', owner_ids=[111L], committer_ids=[222L],
        contributor_ids=[333L])
    page_data = project_helpers.BuildProjectMembers(
        self.cnxn, project, self.services.user)
    self.assertEqual(111L, page_data['owners'][0].user_id)
    self.assertEqual(222L, page_data['committers'][0].user_id)
    self.assertEqual(333L, page_data['contributors'][0].user_id)
    self.assertEqual(3, len(page_data['all_members']))

  def testParseUsernames(self):
    # Form field was not present in post data.
    id_set = project_helpers.ParseUsernames(
        self.cnxn, self.services.user, None)
    self.assertEqual(set(), id_set)

    # Form field was present, but empty.
    id_set = project_helpers.ParseUsernames(
        self.cnxn, self.services.user, '')
    self.assertEqual(set(), id_set)

    # Parsing valid user names.
    id_set = project_helpers.ParseUsernames(
        self.cnxn, self.services.user, 'a@example.com, c@example.com')
    self.assertEqual({111L, 333L}, id_set)

  def testParseProjectAccess_NotOffered(self):
    project = project_pb2.MakeProject('proj')
    access = project_helpers.ParseProjectAccess(project, None)
    self.assertEqual(None, access)

  def testParseProjectAccess_AllowedChoice(self):
    project = project_pb2.MakeProject('proj')
    access = project_helpers.ParseProjectAccess(project, '1')
    self.assertEqual(project_pb2.ProjectAccess.ANYONE, access)

    access = project_helpers.ParseProjectAccess(project, '3')
    self.assertEqual(project_pb2.ProjectAccess.MEMBERS_ONLY, access)

  def testParseProjectAccess_BogusChoice(self):
    project = project_pb2.MakeProject('proj')
    access = project_helpers.ParseProjectAccess(project, '9')
    self.assertEqual(None, access)

  def testUsersWithPermsInProject_StandardPermission(self):
    project = project_pb2.MakeProject('proj', committer_ids=[111L])
    perms_needed = {permissions.VIEW, permissions.EDIT_ISSUE}
    actual = project_helpers.UsersWithPermsInProject(
        project, perms_needed, self.users_by_id, self.effective_ids_by_user)
    self.assertEqual(
        {permissions.VIEW: {111L, 222L, 333L},
         permissions.EDIT_ISSUE: {111L}},
        actual)

  def testUsersWithPermsInProject_IndirectPermission(self):
    perms_needed = {permissions.EDIT_ISSUE}
    # User 111L has the EDIT_ISSUE permission.
    project = project_pb2.MakeProject('proj', committer_ids=[111L])
    # User 222L has the EDIT_ISSUE permission, because 111L is included in its
    # effective IDs.
    self.effective_ids_by_user[222L] = {111L}
    # User 333L doesn't have the EDIT_ISSUE permission, since only direct
    # effective IDs are taken into account.
    self.effective_ids_by_user[333L] = {222L}
    actual = project_helpers.UsersWithPermsInProject(
        project, perms_needed, self.users_by_id, self.effective_ids_by_user)
    self.assertEqual(
        {permissions.EDIT_ISSUE: {111L, 222L}},
        actual)

  def testUsersWithPermsInProject_CustomPermission(self):
    project = project_pb2.MakeProject('proj')
    project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111L,
            perms=['FooPerm', 'BarPerm']),
        project_pb2.Project.ExtraPerms(
            member_id=222L,
            perms=['BarPerm'])]
    perms_needed = {'FooPerm', 'BarPerm'}
    actual = project_helpers.UsersWithPermsInProject(
        project, perms_needed, self.users_by_id, self.effective_ids_by_user)
    self.assertEqual(
        {'FooPerm': {111L},
         'BarPerm': {111L, 222L}},
        actual)
