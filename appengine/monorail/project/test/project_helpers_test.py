# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for helpers module."""

import unittest

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
