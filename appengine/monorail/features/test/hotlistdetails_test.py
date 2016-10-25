# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for hotlistdetails page."""

import mox
import unittest

from third_party import ezt

from framework import permissions
from services import service_manager
from features import hotlistdetails
from proto import features_pb2
from testing import fake
from testing import testing_helpers

class HotlistDetailsTest(unittest.TestCase):
  """Unit tests for the HotlistDetails servlet class."""

  def setUp(self):
    services = service_manager.Services(
        features=fake.FeaturesService(), user=fake.UserService())
    self.servlet = hotlistdetails.HotlistDetails(
        'req', 'res', services=services)
    self.hotlist = services.features.TestAddHotlist(
        'hotlist', summary='hotlist summary', description='hotlist description',
        owner_ids=[111L], editor_ids=[222L])
    self.request, self.mr = testing_helpers.GetRequestObjects(
        hotlist=self.hotlist)
    self.mr.auth.user_id = 111L
    self.private_hotlist = services.features.TestAddHotlist(
        'private_hotlist', owner_ids=[111L], editor_ids=[222L], is_private=True)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testAssertBasePermission(self):
    # non-members cannot view private hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.private_hotlist)
    mr.auth.effective_ids = {333L}
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    # members can view private hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.private_hotlist)
    mr.auth.effective_ids = {222L, 444L}
    self.servlet.AssertBasePermission(mr)

    # non-members can view public hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.hotlist)
    mr.auth.effective_ids = {333L, 444L}
    self.servlet.AssertBasePermission(mr)

    # members can view public hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.hotlist)
    mr.auth.effective_ids = {111L, 333L}
    self.servlet.AssertBasePermission(mr)

  def testGatherPageData(self):
    self.mr.auth.effective_ids = [222L]
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual('hotlist summary', page_data['initial_summary'])
    self.assertEqual('hotlist description', page_data['initial_description'])
    self.assertEqual('hotlist', page_data['initial_name'])
    self.assertEqual('', page_data['initial_default_col_spec'])
    self.assertEqual(ezt.boolean(False), page_data['initial_is_private'])

    # editor is viewing, so cant_administer_hotlist is True
    self.assertEqual(ezt.boolean(True), page_data['cant_administer_hotlist'])

    # owner is veiwing, so cant_administer_hotlist is False
    self.mr.auth.effective_ids = [111L]
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(ezt.boolean(False), page_data['cant_administer_hotlist'])

  def testProcessFormData(self):
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.hotlist,
        path='/u/111L/hotlists/%s/details' % self.hotlist.hotlist_id)
    mr.auth.user_id = 111L
    post_data = fake.PostData(
        name=['hotlist'],
        summary = ['hotlist summary'],
        description = ['hotlist description'],
        default_col_spec = ['test default col spec'])
    url = self.servlet.ProcessFormData(mr, post_data)
    self.assertTrue((
        '/u/111/hotlists/%d/details?saved=' % self.hotlist.hotlist_id) in url)

  def testProcessFormData_RejectTemplate(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/111L/hotlists/%s/details' % (self.hotlist.hotlist_id))
    post_data = fake.PostData(
        summary = ['fake summary'],
        name = [''],
        description = ['fake description'],
        default_col_spec = ['test default col spec'])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, initial_summary='fake summary',
        initial_description='fake description', initial_name = '',
        initial_default_col_spec = 'test default col spec')
    self.mox.ReplayAll()

    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Hotlist name is missing.', mr.errors.name)
    self.assertIsNone(url)
