# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the flt launch issues conversion task."""

import unittest
import settings

from framework import exceptions
from framework import permissions
from services import service_manager
from testing import testing_helpers
from tracker import fltconversion

class FLTConvertTask(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services()
    self.mr = testing_helpers.MakeMonorailRequest()
    self.task = fltconversion.FLTConvertTask(
        'req', 'res', services=self.services)

  def testAssertBasePermission(self):
    self.mr.auth.user_pb.is_site_admin = True
    settings.app_id = 'monorail-staging'
    self.task.AssertBasePermission(self.mr)

    self.mr.auth.user_pb.is_site_admin = False
    self.assertRaises(permissions.PermissionException,
                      self.task.AssertBasePermission, self.mr)

    self.mr.auth.user_pb.is_site_admin = True
    settings.app_id = 'monorail-prod'
    self.assertRaises(exceptions.ActionNotSupported,
                      self.task.AssertBasePermission, self.mr)
