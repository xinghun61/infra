# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.sitewide.userupdates."""

import unittest

import mox

from features import activities
from services import service_manager
from sitewide import sitewide_helpers
from sitewide import userupdates
from testing import fake
from testing import testing_helpers


class ProjectUpdatesTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        user_star=fake.UserStarService())

    self.user_id = 2
    self.project_id = 987
    self.project = self.services.project.TestAddProject(
        'proj', project_id=self.project_id)

    self.mr = testing_helpers.MakeMonorailRequest(
        services=self.services, project=self.project)
    self.mr.cnxn = 'fake cnxn'
    self.mr.viewed_user_auth.user_id = 100

    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testUserUpdatesProjects(self):
    uup = userupdates.UserUpdatesProjects(None, None, self.services)

    self.mox.StubOutWithMock(sitewide_helpers, 'GetViewableStarredProjects')
    sitewide_helpers.GetViewableStarredProjects(
        self.mr.cnxn, self.services, self.mr.viewed_user_auth.user_id,
        self.mr.auth.effective_ids, self.mr.auth.user_pb).AndReturn(
            [self.project])

    self.mox.StubOutWithMock(activities, 'GatherUpdatesData')
    activities.GatherUpdatesData(
        self.services, self.mr, user_ids=None,
        project_ids=[self.project_id],
        ending=uup._ENDING,
        updates_page_url=uup._UPDATES_PAGE_URL,
        highlight=uup._HIGHLIGHT).AndReturn({})

    self.mox.ReplayAll()

    page_data = uup.GatherPageData(self.mr)
    self.mox.VerifyAll()
    self.assertEqual(3, len(page_data))
    self.assertEqual('st5', page_data['user_tab_mode'])
    self.assertEqual('yes', page_data['viewing_user_page'])
    self.assertEqual(uup._TAB_MODE, page_data['user_updates_tab_mode'])

  def testUserUpdatesDevelopers(self):
    uud = userupdates.UserUpdatesDevelopers(None, None, self.services)

    self.mox.StubOutWithMock(self.services.user_star, 'LookupStarredItemIDs')
    self.services.user_star.LookupStarredItemIDs(
        self.mr.cnxn, self.mr.viewed_user_auth.user_id).AndReturn(
            [self.user_id])

    self.mox.StubOutWithMock(activities, 'GatherUpdatesData')
    activities.GatherUpdatesData(
        self.services, self.mr, user_ids=[self.user_id],
        project_ids=None, ending=uud._ENDING,
        updates_page_url=uud._UPDATES_PAGE_URL,
        highlight=uud._HIGHLIGHT).AndReturn({})

    self.mox.ReplayAll()

    page_data = uud.GatherPageData(self.mr)
    self.mox.VerifyAll()
    self.assertEqual(3, len(page_data))
    self.assertEqual('st5', page_data['user_tab_mode'])
    self.assertEqual('yes', page_data['viewing_user_page'])
    self.assertEqual(uud._TAB_MODE, page_data['user_updates_tab_mode'])

  def testUserUpdatesIndividual(self):
    uui = userupdates.UserUpdatesIndividual(None, None, self.services)

    self.mox.StubOutWithMock(activities, 'GatherUpdatesData')
    activities.GatherUpdatesData(
        self.services, self.mr,
        user_ids=[self.mr.viewed_user_auth.user_id],
        project_ids=None, ending=uui._ENDING,
        updates_page_url=uui._UPDATES_PAGE_URL,
        highlight=uui._HIGHLIGHT).AndReturn({})

    self.mox.ReplayAll()

    page_data = uui.GatherPageData(self.mr)
    self.mox.VerifyAll()
    self.assertEqual(3, len(page_data))
    self.assertEqual('st5', page_data['user_tab_mode'])
    self.assertEqual('yes', page_data['viewing_user_page'])
    self.assertEqual(uui._TAB_MODE, page_data['user_updates_tab_mode'])

