# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the issueexport servlet."""

import unittest

from framework import permissions
from services import service_manager
from testing import testing_helpers
from tracker import issueexport


class IssueExportTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services()
    self.servlet = issueexport.IssueExport(
        'req', 'res', services=self.services)

  def testAssertBasePermission(self):
    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)
    mr.auth.user_pb.is_site_admin = True
    self.servlet.AssertBasePermission(mr)
