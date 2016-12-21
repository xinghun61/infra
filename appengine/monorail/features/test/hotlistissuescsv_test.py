# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for issuelistcsv module."""

import unittest

from framework import permissions
from services import service_manager
from testing import testing_helpers
from features import hotlistissuescsv


class HotlistIssuesCsvTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services()
    self.servlet = hotlistissuescsv.HotlistIssuesCsv(
        'req', 'res', services=self.services)

  def testGatherPageData_AnonUsers(self):
    """Anonymous users cannot download the issue list."""
    mr = testing_helpers.MakeMonorailRequest()
    mr.auth.user_id = 0
    self.assertRaises(permissions.PermissionException,
                      self.servlet.GatherPageData, mr)
