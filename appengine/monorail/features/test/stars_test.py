# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the project and user stars feature."""

import unittest

from features import stars
from services import service_manager
from testing import fake
from testing import testing_helpers


class StarsTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService(),
        project_star=fake.ProjectStarService(),
        user_star=fake.UserStarService())
    self.services.project.TestAddProject('proj', project_id=123)
    self.services.user.TestAddUser('testuser', 111L)
    self.set_stars_feed = stars.SetStarsFeed(
        'req', 'res', services=self.services)

  def SetAndVerifyStarredItems(self, scope, item, item_id, get_star_count):
    self.assertEqual(0, get_star_count('fake cnxn', item_id))

    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 111L}, services=self.services, method='POST',
        params={'scope': scope, 'item': item, 'starred': 1, 'token': 'x'})
    result = self.set_stars_feed.HandleRequest(mr)

    self.assertEqual({'starred': True}, result)
    self.assertEqual(1, get_star_count('fake cnxn', item_id))

    # The same starrer doing it again does not drive up the count more.
    result = self.set_stars_feed.HandleRequest(mr)
    self.assertEqual({'starred': True}, result)
    self.assertEqual(1, get_star_count('fake cnxn', item_id))

    mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 111L}, services=self.services, method='POST',
        params={'scope': scope, 'item': item, 'starred': 0, 'token': 'x'})
    result = self.set_stars_feed.HandleRequest(mr)
    self.assertEqual({'starred': False}, result)
    self.assertEqual(0, get_star_count('fake cnxn', item_id))

    # The same starrer doing it again does not drive down the count more.
    result = self.set_stars_feed.HandleRequest(mr)
    self.assertEqual({'starred': False}, result)
    self.assertEqual(0, get_star_count('fake cnxn', item_id))

  def testSetAndGetStarredItems_User(self):
    """Tests SetStarsFeed.HandleRequest method."""
    self.SetAndVerifyStarredItems(
        'users', '111', 111L, self.services.user_star.CountItemStars)

  def testSetAndGetStarredItems_Project(self):
    self.SetAndVerifyStarredItems(
        'projects', 'proj', 123, self.services.project_star.CountItemStars)
