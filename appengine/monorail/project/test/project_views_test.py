# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for project_views module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import framework_views
from project import project_views
from proto import project_pb2
from services import service_manager
from testing import fake


class ProjectAccessViewTest(unittest.TestCase):

  def testAccessViews(self):
    anyone_view = project_views.ProjectAccessView(
        project_pb2.ProjectAccess.ANYONE)
    self.assertEqual(anyone_view.key, int(project_pb2.ProjectAccess.ANYONE))

    members_only_view = project_views.ProjectAccessView(
        project_pb2.ProjectAccess.MEMBERS_ONLY)
    self.assertEqual(members_only_view.key,
                     int(project_pb2.ProjectAccess.MEMBERS_ONLY))


class ProjectViewTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService())
    self.services.project.TestAddProject('test')

  def testNormalProject(self):
    project = self.services.project.GetProjectByName('fake cnxn', 'test')
    project_view = project_views.ProjectView(project)
    self.assertEqual('test', project_view.project_name)
    self.assertEqual('/p/test', project_view.relative_home_url)
    self.assertEqual('LIVE', project_view.state_name)

  def testCachedContentTimestamp(self):
    project = self.services.project.GetProjectByName('fake cnxn', 'test')

    # Project was never updated since we added cached_content_timestamp.
    project.cached_content_timestamp = 0
    view = project_views.ProjectView(project, now=1 * 60 * 60 + 234)
    self.assertEqual(1 * 60 * 60, view.cached_content_timestamp)

    # Project was updated within the last hour, use that timestamp.
    project.cached_content_timestamp = 1 * 60 * 60 + 123
    view = project_views.ProjectView(project, now=1 * 60 * 60 + 234)
    self.assertEqual(1 * 60 * 60 + 123, view.cached_content_timestamp)

    # Project was not updated within the last hour, but user groups
    # could have been updated on groups.google.com without any
    # notification to us, so the client will ask for an updated feed
    # at least once an hour.
    project.cached_content_timestamp = 1 * 60 * 60 + 123
    view = project_views.ProjectView(project, now=2 * 60 * 60 + 234)
    self.assertEqual(2 * 60 * 60, view.cached_content_timestamp)


class MemberViewTest(unittest.TestCase):

  def setUp(self):
    self.alice_view = framework_views.StuffUserView(111, 'alice', True)
    self.bob_view = framework_views.StuffUserView(222, 'bob', True)
    self.carol_view = framework_views.StuffUserView(333, 'carol', True)

    self.project = project_pb2.Project()
    self.project.project_name = 'proj'
    self.project.owner_ids.append(111)
    self.project.committer_ids.append(222)
    self.project.contributor_ids.append(333)

  def testViewingSelf(self):
    member_view = project_views.MemberView(
        0, 111, self.alice_view, self.project, None)
    self.assertFalse(member_view.viewing_self)
    member_view = project_views.MemberView(
        222, 111, self.alice_view, self.project, None)
    self.assertFalse(member_view.viewing_self)

    member_view = project_views.MemberView(
        111, 111, self.alice_view, self.project, None)
    self.assertTrue(member_view.viewing_self)

  def testRoles(self):
    member_view = project_views.MemberView(
        0, 111, self.alice_view, self.project, None)
    self.assertEqual('Owner', member_view.role)
    self.assertEqual('/p/proj/people/detail?u=111',
                     member_view.detail_url)

    member_view = project_views.MemberView(
        0, 222, self.bob_view, self.project, None)
    self.assertEqual('Committer', member_view.role)
    self.assertEqual('/p/proj/people/detail?u=222',
                     member_view.detail_url)

    member_view = project_views.MemberView(
        0, 333, self.carol_view, self.project, None)
    self.assertEqual('Contributor', member_view.role)
    self.assertEqual('/p/proj/people/detail?u=333',
                     member_view.detail_url)
