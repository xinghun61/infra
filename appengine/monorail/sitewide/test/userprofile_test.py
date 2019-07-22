# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the user profile page."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest
import logging
import webapp2
from third_party import ezt

from framework import framework_helpers
from framework import framework_views
from framework import permissions
from proto import project_pb2
from proto import user_pb2
from services import service_manager
from sitewide import userprofile
from testing import fake
from testing import testing_helpers

from google.appengine.ext import testbed

REGULAR_USER_ID = 111
ADMIN_USER_ID = 222
OTHER_USER_ID = 333
STATES = {
    'live': project_pb2.ProjectState.LIVE,
    'archived': project_pb2.ProjectState.ARCHIVED,
}


def MakeReqInfo(
    user_pb, user_id, viewed_user_pb, viewed_user_id, viewed_user_name,
    perms=permissions.USER_PERMISSIONSET):
  mr = fake.MonorailRequest(None, perms=perms)
  mr.auth.user_pb = user_pb
  mr.auth.user_id = user_id
  mr.auth.effective_ids = {user_id}
  mr.viewed_user_auth.email = viewed_user_name
  mr.viewed_user_auth.user_pb = viewed_user_pb
  mr.viewed_user_auth.user_id = viewed_user_id
  mr.viewed_user_auth.effective_ids = {viewed_user_id}
  mr.viewed_user_auth.user_view = framework_views.UserView(viewed_user_pb)
  mr.viewed_user_name = viewed_user_name
  mr.request = webapp2.Request.blank("/")
  return mr


class UserProfileTest(unittest.TestCase):

  def setUp(self):
    self.patcher_1 = mock.patch(
      'framework.framework_helpers.UserSettings.GatherUnifiedSettingsPageData')
    self.mock_guspd = self.patcher_1.start()
    self.mock_guspd.return_value = {'unified': None}

    services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project_star=fake.ProjectStarService(),
        user_star=fake.UserStarService())
    self.servlet = userprofile.UserProfile('req', 'res', services=services)

    for user_id in (
        REGULAR_USER_ID, ADMIN_USER_ID, OTHER_USER_ID):
      services.user.TestAddUser('%s@gmail.com' % user_id, user_id)

    for user in ['regular', 'other']:
      for relation in ['owner', 'member']:
        for state_name, state in STATES.items():
          services.project.TestAddProject(
              '%s-%s-%s' % (user, relation, state_name), state=state)

    # Add projects
    for state_name, state in STATES.items():
      services.project.TestAddProject(
          'regular-owner-%s' % state_name, state=state,
          owner_ids=[REGULAR_USER_ID])
      services.project.TestAddProject(
          'regular-member-%s' % state_name, state=state,
          committer_ids=[REGULAR_USER_ID])
      services.project.TestAddProject(
          'other-owner-%s' % state_name, state=state,
          owner_ids=[OTHER_USER_ID])
      services.project.TestAddProject(
          'other-member-%s' % state_name, state=state,
          committer_ids=[OTHER_USER_ID])

    self.regular_user = services.user.GetUser('fake cnxn', REGULAR_USER_ID)
    self.admin_user = services.user.GetUser('fake cnxn', ADMIN_USER_ID)
    self.admin_user.is_site_admin = True
    self.other_user = services.user.GetUser('fake cnxn', OTHER_USER_ID)

    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()
    mock.patch.stopall()

  def assertProjectsAnyOrder(self, value_to_test, *expected_project_names):
    actual_project_names = [project_view.project_name
                            for project_view in value_to_test]
    self.assertItemsEqual(expected_project_names, actual_project_names)

  def testGatherPageData_RegularUserViewingOtherUserProjects(self):
    """A user can see the other users' live projects, but not archived ones."""
    mr = MakeReqInfo(
        self.regular_user, REGULAR_USER_ID, self.other_user,
        OTHER_USER_ID, 'other@xyz.com')

    page_data = self.servlet.GatherPageData(mr)

    self.assertProjectsAnyOrder(page_data['owner_of_projects'],
                                'other-owner-live')
    self.assertProjectsAnyOrder(page_data['committer_of_projects'],
                                'other-member-live')
    self.assertFalse(page_data['owner_of_archived_projects'])
    self.assertEqual('ot...@xyz.com', page_data['viewed_user_display_name'])
    self.assertEqual(ezt.boolean(False), page_data['can_delete_user'])
    self.mock_guspd.assert_called_once_with(
        111, mr.viewed_user_auth.user_view, mr.viewed_user_auth.user_pb,
        None)

  def testGatherPageData_RegularUserViewingOwnProjects(self):
    """A user can see all their own projects: live or archived."""
    mr = MakeReqInfo(
        self.regular_user, REGULAR_USER_ID, self.regular_user,
        REGULAR_USER_ID, 'self@xyz.com')

    page_data = self.servlet.GatherPageData(mr)

    self.assertEqual('self@xyz.com', page_data['viewed_user_display_name'])
    self.assertEqual(ezt.boolean(False), page_data['can_delete_user'])
    self.assertProjectsAnyOrder(page_data['owner_of_projects'],
                                'regular-owner-live')
    self.assertProjectsAnyOrder(page_data['committer_of_projects'],
                                'regular-member-live')
    self.assertProjectsAnyOrder(
        page_data['owner_of_archived_projects'],
        'regular-owner-archived')
    self.mock_guspd.assert_called_once_with(
        111, mr.viewed_user_auth.user_view, mr.viewed_user_auth.user_pb,
        None)

  def testGatherPageData_RegularUserViewingStarredUsers(self):
    """A user can see display names of other users that they starred."""
    mr = MakeReqInfo(
        self.regular_user, REGULAR_USER_ID, self.regular_user,
        REGULAR_USER_ID, 'self@xyz.com')
    self.servlet.services.user_star.SetStar(
        'cnxn', OTHER_USER_ID, REGULAR_USER_ID, True)

    page_data = self.servlet.GatherPageData(mr)

    starred_users = page_data['starred_users']
    self.assertEquals(1, len(starred_users))
    self.assertEquals('333@gmail.com', starred_users[0].email)
    self.assertEquals('["3...@gmail.com"]', page_data['starred_users_json'])
    self.mock_guspd.assert_called_once_with(
        111, mr.viewed_user_auth.user_view, mr.viewed_user_auth.user_pb,
        None)

  def testGatherPageData_AdminViewingOtherUserAddress(self):
    """Site admins always see full email addresses of other users."""
    mr = MakeReqInfo(
        self.admin_user, ADMIN_USER_ID, self.other_user,
        OTHER_USER_ID, 'other@xyz.com',
        perms=permissions.ADMIN_PERMISSIONSET)

    page_data = self.servlet.GatherPageData(mr)

    self.assertEqual('other@xyz.com', page_data['viewed_user_display_name'])
    self.assertEqual(ezt.boolean(True), page_data['can_delete_user'])
    self.mock_guspd.assert_called_once_with(
        222, mr.viewed_user_auth.user_view, mr.viewed_user_auth.user_pb,
        mock.ANY)

  def testGatherPageData_RegularUserViewingOtherUserAddressUnobscured(self):
    """Email should be revealed to others depending on obscure_email."""
    mr = MakeReqInfo(
        self.regular_user, REGULAR_USER_ID, self.other_user,
        OTHER_USER_ID, 'other@xyz.com')
    mr.viewed_user_auth.user_view.obscure_email = False

    page_data = self.servlet.GatherPageData(mr)

    self.assertEquals('other@xyz.com', page_data['viewed_user_display_name'])
    self.mock_guspd.assert_called_once_with(
        111, mr.viewed_user_auth.user_view, mr.viewed_user_auth.user_pb,
        None)

  def testGatherPageData_RegularUserViewingOtherUserAddressObscured(self):
    """Email should be revealed to others depending on obscure_email."""
    mr = MakeReqInfo(
        self.regular_user, REGULAR_USER_ID, self.other_user,
        OTHER_USER_ID, 'other@xyz.com')
    mr.viewed_user_auth.user_view.obscure_email = True

    page_data = self.servlet.GatherPageData(mr)

    self.assertEqual('ot...@xyz.com', page_data['viewed_user_display_name'])
    self.assertEqual(ezt.boolean(False), page_data['can_delete_user'])
    self.mock_guspd.assert_called_once_with(
        111, mr.viewed_user_auth.user_view, mr.viewed_user_auth.user_pb,
        None)

  def testGatherPageData_NoLinkedAccounts(self):
    """An account with no linked accounts should not show anything linked."""
    mr = MakeReqInfo(
        self.regular_user, REGULAR_USER_ID, self.other_user,
        OTHER_USER_ID, 'other@xyz.com')

    page_data = self.servlet.GatherPageData(mr)

    self.assertIsNone(page_data['linked_parent'])
    self.assertEquals([], page_data['linked_children'])

  def testGatherPageData_ParentAccounts(self):
    """An account with a parent linked account should show it."""
    self.other_user.linked_parent_id = REGULAR_USER_ID
    mr = MakeReqInfo(
        self.regular_user, REGULAR_USER_ID, self.other_user,
        OTHER_USER_ID, 'other@xyz.com')

    page_data = self.servlet.GatherPageData(mr)

    self.assertEquals('111@gmail.com', page_data['linked_parent'].email)
    self.assertEquals([], page_data['linked_children'])

  def testGatherPageData_ChildAccounts(self):
    """An account with a child linked account should show them."""
    self.other_user.linked_child_ids = [REGULAR_USER_ID, ADMIN_USER_ID]
    mr = MakeReqInfo(
        self.regular_user, REGULAR_USER_ID, self.other_user,
        OTHER_USER_ID, 'other@xyz.com')

    page_data = self.servlet.GatherPageData(mr)

    self.assertEquals(None, page_data['linked_parent'])
    self.assertEquals(
        ['111@gmail.com', '222@gmail.com'],
        [uv.email for uv in page_data['linked_children']])
