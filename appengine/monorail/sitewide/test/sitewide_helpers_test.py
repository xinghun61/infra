# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the sitewide_helpers module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import project_pb2
from services import service_manager
from sitewide import sitewide_helpers
from testing import fake


REGULAR_USER_ID = 111
ADMIN_USER_ID = 222
OTHER_USER_ID = 333

# Test project IDs
REGULAR_OWNER_LIVE = 1001
REGULAR_OWNER_ARCHIVED = 1002
REGULAR_OWNER_DELETABLE = 1003
REGULAR_COMMITTER_LIVE = 2001
REGULAR_COMMITTER_ARCHIVED = 2002
REGULAR_COMMITTER_DELETABLE = 2003
OTHER_OWNER_LIVE = 3001
OTHER_OWNER_ARCHIVED = 3002
OTHER_OWNER_DELETABLE = 3003
OTHER_COMMITTER_LIVE = 4001
MEMBERS_ONLY = 5001


class HelperFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService(),
        project_star=fake.ProjectStarService())
    self.cnxn = 'fake cnxn'

    for user_id in (ADMIN_USER_ID, REGULAR_USER_ID, OTHER_USER_ID):
      self.services.user.TestAddUser('ignored_%s@gmail.com' % user_id, user_id)

    self.regular_owner_live = self.services.project.TestAddProject(
        'regular-owner-live', state=project_pb2.ProjectState.LIVE,
        owner_ids=[REGULAR_USER_ID], project_id=REGULAR_OWNER_LIVE)
    self.regular_owner_archived = self.services.project.TestAddProject(
        'regular-owner-archived', state=project_pb2.ProjectState.ARCHIVED,
        owner_ids=[REGULAR_USER_ID], project_id=REGULAR_OWNER_ARCHIVED)
    self.regular_owner_deletable = self.services.project.TestAddProject(
        'regular-owner-deletable', state=project_pb2.ProjectState.DELETABLE,
        owner_ids=[REGULAR_USER_ID], project_id=REGULAR_OWNER_DELETABLE)
    self.regular_committer_live = self.services.project.TestAddProject(
        'regular-committer-live', state=project_pb2.ProjectState.LIVE,
        committer_ids=[REGULAR_USER_ID], project_id=REGULAR_COMMITTER_LIVE)
    self.regular_committer_archived = self.services.project.TestAddProject(
        'regular-committer-archived', state=project_pb2.ProjectState.ARCHIVED,
        committer_ids=[REGULAR_USER_ID], project_id=REGULAR_COMMITTER_ARCHIVED)
    self.regular_committer_deletable = self.services.project.TestAddProject(
        'regular-committer-deletable', state=project_pb2.ProjectState.DELETABLE,
        committer_ids=[REGULAR_USER_ID], project_id=REGULAR_COMMITTER_DELETABLE)
    self.other_owner_live = self.services.project.TestAddProject(
        'other-owner-live', state=project_pb2.ProjectState.LIVE,
        owner_ids=[OTHER_USER_ID], project_id=OTHER_OWNER_LIVE)
    self.other_owner_archived = self.services.project.TestAddProject(
        'other-owner-archived', state=project_pb2.ProjectState.ARCHIVED,
        owner_ids=[OTHER_USER_ID], project_id=OTHER_OWNER_ARCHIVED)
    self.other_owner_deletable = self.services.project.TestAddProject(
        'other-owner-deletable', state=project_pb2.ProjectState.DELETABLE,
        owner_ids=[OTHER_USER_ID], project_id=OTHER_OWNER_DELETABLE)
    self.other_committer_live = self.services.project.TestAddProject(
        'other-committer-live', state=project_pb2.ProjectState.LIVE,
        committer_ids=[OTHER_USER_ID], project_id=OTHER_COMMITTER_LIVE)

    self.regular_user = self.services.user.GetUser(self.cnxn, REGULAR_USER_ID)

    self.admin_user = self.services.user.TestAddUser(
        'administrator@chromium.org', ADMIN_USER_ID)
    self.admin_user.is_site_admin = True

    self.other_user = self.services.user.GetUser(self.cnxn, OTHER_USER_ID)

    self.members_only_project = self.services.project.TestAddProject(
        'members-only', owner_ids=[REGULAR_USER_ID], project_id=MEMBERS_ONLY)
    self.members_only_project.access = project_pb2.ProjectAccess.MEMBERS_ONLY

  def assertProjectsAnyOrder(self, actual_projects, *expected_projects):
    # Check names rather than Project objects so that output is easier to read.
    actual_names = [p.project_name for p in actual_projects]
    expected_names = [p.project_name for p in expected_projects]
    self.assertItemsEqual(expected_names, actual_names)

  def testFilterViewableProjects_CantViewArchived(self):
    projects = list(sitewide_helpers.FilterViewableProjects(
        list(self.services.project.test_projects.values()),
        self.regular_user, {REGULAR_USER_ID}))
    self.assertProjectsAnyOrder(
        projects, self.regular_owner_live, self.regular_committer_live,
        self.other_owner_live, self.other_committer_live,
        self.members_only_project)

  def testFilterViewableProjects_NonMemberCantViewMembersOnly(self):
    projects = list(sitewide_helpers.FilterViewableProjects(
        list(self.services.project.test_projects.values()),
        self.other_user, {OTHER_USER_ID}))
    self.assertProjectsAnyOrder(
        projects, self.regular_owner_live, self.regular_committer_live,
        self.other_owner_live, self.other_committer_live)

  def testFilterViewableProjects_AdminCanViewAny(self):
    projects = list(sitewide_helpers.FilterViewableProjects(
        list(self.services.project.test_projects.values()),
        self.admin_user, {ADMIN_USER_ID}))
    self.assertProjectsAnyOrder(
        projects, self.regular_owner_live, self.regular_committer_live,
        self.other_owner_live, self.other_committer_live,
        self.members_only_project)

  def testGetStarredProjects_OnlyViewableLiveStarred(self):
    viewed_user_id = 123
    for p in self.services.project.test_projects.values():
      # We go straight to the services layer because this is a test set up
      # rather than an actual user request.
      self.services.project_star.SetStar(
          self.cnxn, p.project_id, viewed_user_id, True)

    self.assertProjectsAnyOrder(
        sitewide_helpers.GetViewableStarredProjects(
            self.cnxn, self.services, viewed_user_id,
            {REGULAR_USER_ID}, self.regular_user),
        self.regular_owner_live, self.regular_committer_live,
        self.other_owner_live, self.other_committer_live,
        self.members_only_project)

  def testGetStarredProjects_MembersOnly(self):
    # Both users were able to star the project in the past.  The stars do not
    # go away even if access to the project changes.
    self.services.project_star.SetStar(
        self.cnxn, self.members_only_project.project_id, REGULAR_USER_ID, True)
    self.services.project_star.SetStar(
        self.cnxn, self.members_only_project.project_id, OTHER_USER_ID, True)

    # But now, only one of them is currently a member, so only regular_user
    # can see the starred project in the lists.
    self.assertProjectsAnyOrder(
        sitewide_helpers.GetViewableStarredProjects(
            self.cnxn, self.services, REGULAR_USER_ID, {REGULAR_USER_ID},
            self.regular_user),
        self.members_only_project)
    self.assertProjectsAnyOrder(
        sitewide_helpers.GetViewableStarredProjects(
            self.cnxn, self.services, OTHER_USER_ID, {REGULAR_USER_ID},
            self.regular_user),
        self.members_only_project)

    # The other user cannot see the project, so he does not see it in either
    # list of starred projects.
    self.assertProjectsAnyOrder(
        sitewide_helpers.GetViewableStarredProjects(
            self.cnxn, self.services, REGULAR_USER_ID, {OTHER_USER_ID},
            self.other_user))  # No expected projects listed.
    self.assertProjectsAnyOrder(
        sitewide_helpers.GetViewableStarredProjects(
            self.cnxn, self.services, OTHER_USER_ID, {OTHER_USER_ID},
            self.other_user))  # No expected projects listed.
