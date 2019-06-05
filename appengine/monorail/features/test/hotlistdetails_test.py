# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for hotlistdetails page."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import mox
import unittest

from third_party import ezt

from framework import permissions
from features import features_constants
from services import service_manager
from features import hotlistdetails
from proto import features_pb2
from testing import fake
from testing import testing_helpers

class HotlistDetailsTest(unittest.TestCase):
  """Unit tests for the HotlistDetails servlet class."""

  def setUp(self):
    self.user_service = fake.UserService()
    self.user_service.TestAddUser('111@test.com', 111)
    services = service_manager.Services(
        features=fake.FeaturesService(), user=self.user_service)
    self.servlet = hotlistdetails.HotlistDetails(
        'req', 'res', services=services)
    self.hotlist = self.servlet.services.features.TestAddHotlist(
        'hotlist', summary='hotlist summary', description='hotlist description',
        owner_ids=[111], editor_ids=[222])
    self.request, self.mr = testing_helpers.GetRequestObjects(
        hotlist=self.hotlist)
    self.mr.auth.user_id = 111
    self.private_hotlist = services.features.TestAddHotlist(
        'private_hotlist', owner_ids=[111], editor_ids=[222], is_private=True)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testAssertBasePermission(self):
    # non-members cannot view private hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.private_hotlist, perms=permissions.EMPTY_PERMISSIONSET)
    mr.auth.effective_ids = {333}
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    # members can view private hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.private_hotlist)
    mr.auth.effective_ids = {222, 444}
    self.servlet.AssertBasePermission(mr)

    # non-members can view public hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.hotlist)
    mr.auth.effective_ids = {333, 444}
    self.servlet.AssertBasePermission(mr)

    # members can view public hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.hotlist)
    mr.auth.effective_ids = {111, 333}
    self.servlet.AssertBasePermission(mr)

  def testGatherPageData(self):
    self.mr.auth.effective_ids = [222]
    self.mr.perms = permissions.EMPTY_PERMISSIONSET
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual('hotlist summary', page_data['initial_summary'])
    self.assertEqual('hotlist description', page_data['initial_description'])
    self.assertEqual('hotlist', page_data['initial_name'])
    self.assertEqual(features_constants.DEFAULT_COL_SPEC,
                     page_data['initial_default_col_spec'])
    self.assertEqual(ezt.boolean(False), page_data['initial_is_private'])

    # editor is viewing, so cant_administer_hotlist is True
    self.assertEqual(ezt.boolean(True), page_data['cant_administer_hotlist'])

    # owner is veiwing, so cant_administer_hotlist is False
    self.mr.auth.effective_ids = [111]
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(ezt.boolean(False), page_data['cant_administer_hotlist'])

  def testProcessFormData(self):
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.hotlist,
        path='/u/111/hotlists/%s/details' % self.hotlist.hotlist_id,
        services=service_manager.Services(user=self.user_service),
        perms=permissions.EMPTY_PERMISSIONSET)
    mr.auth.user_id = 111
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
        hotlist=self.hotlist,
        path='/u/111/hotlists/%s/details' % self.hotlist.hotlist_id,
        services=service_manager.Services(user=self.user_service))
    mr.auth.user_id = 111
    post_data = fake.PostData(
        summary = [''],
        name = [''],
        description = ['fake description'],
        default_col_spec = ['test default col spec'])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, initial_summary='',
        initial_description='fake description', initial_name = '',
        initial_default_col_spec = 'test default col spec')
    self.mox.ReplayAll()

    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual(hotlistdetails._MSG_NAME_MISSING, mr.errors.name)
    self.assertEqual(hotlistdetails._MSG_SUMMARY_MISSING,
                     mr.errors.summary)
    self.assertIsNone(url)

  def testProcessFormData_DuplicateName(self):
    self.servlet.services.features.TestAddHotlist(
        'FirstHotlist', summary='hotlist summary', description='description',
        owner_ids=[111], editor_ids=[])
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.hotlist,
        path='/u/111/hotlists/%s/details' % (self.hotlist.hotlist_id),
        services=service_manager.Services(user=self.user_service))
    mr.auth.user_id = 111
    post_data = fake.PostData(
        summary = ['hotlist summary'],
        name = ['FirstHotlist'],
        description = ['description'],
        default_col_spec = ['test default col spec'])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, initial_summary='hotlist summary',
        initial_description='description', initial_name = 'FirstHotlist',
        initial_default_col_spec = 'test default col spec')
    self.mox.ReplayAll()

    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual(hotlistdetails._MSG_HOTLIST_NAME_NOT_AVAIL,
                     mr.errors.name)
    self.assertIsNone(url)

  def testProcessFormData_Bad(self):
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.hotlist,
        path='/u/111/hotlists/%s/details' % (self.hotlist.hotlist_id),
        services=service_manager.Services(user=self.user_service))
    post_data = fake.PostData(
        summary = ['hotlist summary'],
        name = ['2badName'],
        description = ['fake description'],
        default_col_spec = ['test default col spec'])
    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        mr, initial_summary='hotlist summary',
        initial_description='fake description', initial_name = '2badName',
        initial_default_col_spec = 'test default col spec')
    self.mox.ReplayAll()

    url = self.servlet.ProcessFormData(mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual(hotlistdetails._MSG_INVALID_HOTLIST_NAME,
                     mr.errors.name)
    self.assertIsNone(url)
