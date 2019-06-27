# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the user settings page."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

import mox

from framework import framework_helpers
from framework import permissions
from framework import template_helpers
from proto import user_pb2
from services import service_manager
from sitewide import usersettings
from testing import fake
from testing import testing_helpers


class UserSettingsTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.services = service_manager.Services(user=fake.UserService())
    self.servlet = usersettings.UserSettings(
        'req', 'res', services=self.services)

  def tearDown(self):
    self.mox.UnsetStubs()

  def testAssertBasePermission(self):
    mr = testing_helpers.MakeMonorailRequest()
    mr.auth.user_id = 111

    # The following should return without exception.
    self.servlet.AssertBasePermission(mr)

    # No logged in user means anonymous access, should raise error.
    mr.auth.user_id = 0
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

  def testGatherPageData(self):
    self.mox.StubOutWithMock(
        framework_helpers.UserSettings, 'GatherUnifiedSettingsPageData')
    framework_helpers.UserSettings.GatherUnifiedSettingsPageData(
        0, None, mox.IsA(user_pb2.User), mox.IsA(user_pb2.UserPrefs)
        ).AndReturn({'unified': None})
    self.mox.ReplayAll()

    mr = testing_helpers.MakeMonorailRequest()
    page_data = self.servlet.GatherPageData(mr)

    self.assertItemsEqual(
        ['logged_in_user_pb', 'unified', 'user_tab_mode',
         'viewed_user', 'offer_saved_queries_subtab', 'viewing_self'],
        list(page_data.keys()))
    self.assertEqual(template_helpers.PBProxy(mr.auth.user_pb),
                     page_data['logged_in_user_pb'])

    self.mox.VerifyAll()
