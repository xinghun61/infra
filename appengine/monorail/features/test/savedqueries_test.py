# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for savedqueries feature."""

import unittest

from features import savedqueries
from framework import monorailrequest
from framework import permissions
from services import service_manager
from testing import fake


class SavedQueriesTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService())
    self.servlet = savedqueries.SavedQueries(
        'req', 'res', services=self.services)
    self.services.user.TestAddUser('a@example.com', 111L)

  def testAssertBasePermission(self):
    """Only permit site admins and users viewing themselves."""
    mr = monorailrequest.MonorailRequest(self.services)
    mr.viewed_user_auth.user_id = 111L
    mr.auth.user_id = 222L

    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    mr.auth.user_id = 111L
    self.servlet.AssertBasePermission(mr)

    mr.auth.user_id = 222L
    mr.auth.user_pb.is_site_admin = True
    self.servlet.AssertBasePermission(mr)
