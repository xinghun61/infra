# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for Project Summary servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import permissions
from project import projectsummary
from proto import project_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class ProjectSummaryTest(unittest.TestCase):

  def setUp(self):
    services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService(),
        project_star=fake.ProjectStarService())
    self.project = services.project.TestAddProject(
        'proj', project_id=123, summary='sum',
        description='desc')
    self.servlet = projectsummary.ProjectSummary(
        'req', 'res', services=services)

  def testGatherPageData(self):
    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(
        '<p>desc</p>', page_data['formatted_project_description'])
    self.assertEqual(
        int(project_pb2.ProjectAccess.ANYONE), page_data['access_level'].key)
    self.assertEqual(0, page_data['num_stars'])
    self.assertEqual('s', page_data['plural'])

  def testGatherHelpData(self):
    mr = testing_helpers.MakeMonorailRequest(project=self.project)

    # Non-members cannot edit project, so cue is not relevant.
    mr.perms = permissions.READ_ONLY_PERMISSIONSET
    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(None, help_data['cue'])

    # Members (not owners) cannot edit project, so cue is not relevant.
    mr.perms = permissions.READ_ONLY_PERMISSIONSET
    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(None, help_data['cue'])

    # This is a project member who has set up mailing lists and added
    # members, but has not noted any duties.
    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    self.project.issue_notify_address = 'example@domain.com'
    self.project.committer_ids.extend([111, 222])
    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual('document_team_duties', help_data['cue'])

    # Now he set up notes too.
    project_commitments = project_pb2.ProjectCommitments()
    project_commitments.project_id = self.project.project_id
    project_commitments.commitments.append(
        project_pb2.ProjectCommitments.MemberCommitment())
    self.servlet.services.project.TestStoreProjectCommitments(
        project_commitments)
    help_data = self.servlet.GatherHelpData(mr, {})
    self.assertEqual(None, help_data['cue'])
