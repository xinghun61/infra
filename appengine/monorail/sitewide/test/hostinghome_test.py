# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the Monorail home page."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest

from third_party import ezt

import settings
from framework import permissions
from proto import project_pb2
from proto import site_pb2
from services import service_manager
from sitewide import hostinghome
from sitewide import projectsearch
from testing import fake
from testing import testing_helpers


class MockProjectSearchPipeline(object):

  def __init__(self, _mr, services):
    self.visible_results = services.mock_visible_results
    self.pagination = None

  def SearchForIDs(self, domain=None):
    pass

  def GetProjectsAndPaginate(self, cnxn, list_page_url):
    pass


class HostingHomeTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        project_star=fake.ProjectStarService())
    self.services.mock_visible_results = []
    self.project_a = self.services.project.TestAddProject('a', project_id=1)
    self.project_b = self.services.project.TestAddProject('b', project_id=2)

    self.servlet = hostinghome.HostingHome('req', 'res', services=self.services)
    self.mr = testing_helpers.MakeMonorailRequest(user_info={'user_id': 111})

    self.orig_pipeline_class = projectsearch.ProjectSearchPipeline
    projectsearch.ProjectSearchPipeline = MockProjectSearchPipeline

  def tearDown(self):
    projectsearch.ProjectSearchPipeline = self.orig_pipeline_class

  def testSearch_ZeroResults(self):
    self.services.mock_visible_results = []
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual([], page_data['projects'])

  def testSearch_NonzeroResults(self):
    self.services.mock_visible_results = [self.project_a, self.project_b]
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(['a', 'b'],
                     [pv.project_name for pv in page_data['projects']])

  def testStarCounts(self):
    """Test the display of star counts on each displayed project."""
    self.services.mock_visible_results = [self.project_a, self.project_b]
    # We go straight to the services layer because this is a test set up
    # rather than an actual user request.
    self.services.project_star.SetStar('fake cnxn', 1, 111, True)
    self.services.project_star.SetStar('fake cnxn', 1, 222, True)
    page_data = self.servlet.GatherPageData(self.mr)
    project_view_a, project_view_b = page_data['projects']
    self.assertEqual(2, project_view_a.num_stars)
    self.assertEqual(0, project_view_b.num_stars)

  def testStarredProjects(self):
    self.services.mock_visible_results = [self.project_a, self.project_b]
    self.services.project_star.SetStar('fake cnxn', 1, 111, True)
    page_data = self.servlet.GatherPageData(self.mr)
    project_view_a, project_view_b = page_data['projects']
    self.assertTrue(project_view_a.starred)
    self.assertFalse(project_view_b.starred)

  def testGatherPageData(self):
    mr = testing_helpers.MakeMonorailRequest()
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(settings.learn_more_link, page_data['learn_more_link'])

  def testGatherPageData_CanCreateProject(self):
    mr = testing_helpers.MakeMonorailRequest()
    mr.perms = permissions.PermissionSet([permissions.CREATE_PROJECT])
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(
      ezt.boolean(settings.project_creation_restriction ==
                  site_pb2.UserTypeRestriction.ANYONE),
      page_data['can_create_project'])

    mr.perms = permissions.PermissionSet([])
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual(ezt.boolean(False), page_data['can_create_project'])

  @mock.patch('settings.domain_to_default_project', {})
  def testMaybeRedirectToDomainDefaultProject_NoMatch(self):
    """No redirect if the user is not accessing via a configured domain."""
    mr = testing_helpers.MakeMonorailRequest()
    mr.request.host = 'example.com'
    msg = self.servlet._MaybeRedirectToDomainDefaultProject(mr)
    print('msg: ' + msg)
    self.assertTrue(msg.startswith('No configured'))

  @mock.patch('settings.domain_to_default_project', {'example.com': 'huh'})
  def testMaybeRedirectToDomainDefaultProject_NoSuchProject(self):
    """No redirect if the configured project does not exist."""
    mr = testing_helpers.MakeMonorailRequest()
    mr.request.host = 'example.com'
    print('host is %r' % mr.request.host)
    msg = self.servlet._MaybeRedirectToDomainDefaultProject(mr)
    print('msg: ' + msg)
    self.assertTrue(msg.endswith('not found'))

  @mock.patch('settings.domain_to_default_project', {'example.com': 'a'})
  def testMaybeRedirectToDomainDefaultProject_CantView(self):
    """No redirect if the user can't view the configured project."""
    self.project_a.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    mr = testing_helpers.MakeMonorailRequest()
    mr.request.host = 'example.com'
    msg = self.servlet._MaybeRedirectToDomainDefaultProject(mr)
    print('msg: ' + msg)
    self.assertTrue(msg.startswith('User cannot'))

  @mock.patch('settings.domain_to_default_project', {'example.com': 'a'})
  def testMaybeRedirectToDomainDefaultProject_Redirect(self):
    """We redirect if there's a configured project that the user can view."""
    mr = testing_helpers.MakeMonorailRequest()
    mr.request.host = 'example.com'
    self.servlet.redirect = mock.Mock()
    msg = self.servlet._MaybeRedirectToDomainDefaultProject(mr)
    print('msg: ' + msg)
    self.assertTrue(msg.startswith('Redirected'))
    self.servlet.redirect.assert_called_once()
