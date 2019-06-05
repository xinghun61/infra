# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for issuelistcsv module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import permissions
from framework import xsrf
from services import service_manager
from testing import testing_helpers
from tracker import issuelistcsv


class IssueListCSVTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services()
    self.servlet = issuelistcsv.IssueListCsv(
        'req', 'res', services=self.services)

  def testGatherPageData_AnonUsers(self):
    """Anonymous users cannot download the issue list."""
    mr = testing_helpers.MakeMonorailRequest()
    mr.auth.user_id = 0
    self.assertRaises(permissions.PermissionException,
                      self.servlet.GatherPageData, mr)

  def testGatherPageData_XSRFToken(self):
    """Users cannot download the issue list without a valid token."""
    mr = testing_helpers.MakeMonorailRequest()
    mr.auth.user_id = 111
    self.assertRaises(xsrf.TokenIncorrect,
                      self.servlet.GatherPageData, mr)
