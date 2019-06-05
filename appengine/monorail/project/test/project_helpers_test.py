# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for helpers module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

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
    self.services.user.TestAddUser('a@example.com', 111)
    self.services.user.TestAddUser('b@example.com', 222)
    self.services.user.TestAddUser('c@example.com', 333)
    self.users_by_id = framework_views.MakeAllUserViews(
        'cnxn', self.services.user, [111, 222, 333])
    self.effective_ids_by_user = {user: set() for user in {111, 222, 333}}

  def testBuildProjectMembers(self):
    project = project_pb2.MakeProject(
        'proj', owner_ids=[111], committer_ids=[222],
        contributor_ids=[333])
    page_data = project_helpers.BuildProjectMembers(
        self.cnxn, project, self.services.user)
    self.assertEqual(111, page_data['owners'][0].user_id)
    self.assertEqual(222, page_data['committers'][0].user_id)
    self.assertEqual(333, page_data['contributors'][0].user_id)
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
    self.assertEqual({111, 333}, id_set)

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
    project = project_pb2.MakeProject('proj', committer_ids=[111])
    perms_needed = {permissions.VIEW, permissions.EDIT_ISSUE}
    actual = project_helpers.UsersWithPermsInProject(
        project, perms_needed, self.users_by_id, self.effective_ids_by_user)
    self.assertEqual(
        {permissions.VIEW: {111, 222, 333},
         permissions.EDIT_ISSUE: {111}},
        actual)

  def testUsersWithPermsInProject_IndirectPermission(self):
    perms_needed = {permissions.EDIT_ISSUE}
    # User 111 has the EDIT_ISSUE permission.
    project = project_pb2.MakeProject('proj', committer_ids=[111])
    # User 222 has the EDIT_ISSUE permission, because 111 is included in its
    # effective IDs.
    self.effective_ids_by_user[222] = {111}
    # User 333 doesn't have the EDIT_ISSUE permission, since only direct
    # effective IDs are taken into account.
    self.effective_ids_by_user[333] = {222}
    actual = project_helpers.UsersWithPermsInProject(
        project, perms_needed, self.users_by_id, self.effective_ids_by_user)
    self.assertEqual(
        {permissions.EDIT_ISSUE: {111, 222}},
        actual)

  def testUsersWithPermsInProject_CustomPermission(self):
    project = project_pb2.MakeProject('proj')
    project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111,
            perms=['FooPerm', 'BarPerm']),
        project_pb2.Project.ExtraPerms(
            member_id=222,
            perms=['BarPerm'])]
    perms_needed = {'FooPerm', 'BarPerm'}
    actual = project_helpers.UsersWithPermsInProject(
        project, perms_needed, self.users_by_id, self.effective_ids_by_user)
    self.assertEqual(
        {'FooPerm': {111},
         'BarPerm': {111, 222}},
        actual)
