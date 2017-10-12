# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the user projects feed."""

import unittest

from sitewide import userprojects
from services import service_manager
from testing import fake
from testing import testing_helpers


class UserProjectsTest(unittest.TestCase): 

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService(),
        project_star=fake.ProjectStarService())
    self.projects_json_feed = userprojects.ProjectsJsonFeed(
        'req', 'res', services=self.services)

  def testGatherProjects(self):
    self.services.user.TestAddUser('testuser', 1L)
    self.services.user.TestAddUser('otheruser', 2L)
    self.services.project.TestAddProject(
        'memberof-proj', project_id=1, owner_ids=[2], committer_ids=[1])
    self.services.project.TestAddProject(
        'ownerof-proj', project_id=2, owner_ids=[1])
    self.services.project.TestAddProject(
        'contributorto-proj', project_id=3, owner_ids=[2], contrib_ids=[1])
    self.services.project.TestAddProject(
        'starred-proj', project_id=4)
    # We go straight to the services layer because this is a test set up
    # rather than an actual user request.
    self.services.project_star.SetStar(None, 4, 1, True)

    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 1L}, services=self.services)
    result = self.projects_json_feed.HandleRequest(mr)
    self.assertEqual(['memberof-proj'], result['memberof'])
    self.assertEqual(['contributorto-proj'], result['contributorto'])
    self.assertEqual(['starred-proj'], result['starred_projects'])
    self.assertEqual(['ownerof-proj'], result['ownerof'])
