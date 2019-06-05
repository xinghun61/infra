# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for issuetips module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issuetips


class IssueTipsTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService())
    self.servlet = issuetips.IssueSearchTips(
        'req', 'res', services=self.services)

  def testGatherPageData(self):
    mr = testing_helpers.MakeMonorailRequest(path='/p/proj/issues/tips')
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual('issueSearchTips', page_data['issue_tab_mode'])
