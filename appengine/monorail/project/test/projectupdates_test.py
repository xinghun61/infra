# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.project.projectupdates."""

import unittest

import mox

from features import activities
from project import projectupdates
from services import service_manager
from testing import fake
from testing import testing_helpers


class ProjectUpdatesTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(project=fake.ProjectService())

    self.project_name = 'proj'
    self.project_id = 987
    self.project = self.services.project.TestAddProject(
        self.project_name, project_id=self.project_id,
        process_inbound_email=True)

    self.mr = testing_helpers.MakeMonorailRequest(
        services=self.services, project=self.project)
    self.mr.project_name = self.project_name
    self.project_updates = projectupdates.ProjectUpdates(
        None, None, self.services)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testGatherPageData(self):
    self.mox.StubOutWithMock(activities, 'GatherUpdatesData')
    activities.GatherUpdatesData(
        self.services, self.mr, project_ids=[self.project_id],
        ending='by_user',
        updates_page_url='/p/%s/updates/list' % self.project_name,
        autolink=self.services.autolink).AndReturn({'test': 'testing'})
    self.mox.ReplayAll()

    page_data = self.project_updates.GatherPageData(self.mr)
    self.mox.VerifyAll()
    self.assertEquals(
        {'subtab_mode': None, 'user_updates_tab_mode': None, 'test': 'testing'},
        page_data)

