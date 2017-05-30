# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.tracker.issuepresubmit."""

import unittest

from framework import permissions
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issuepresubmit


class IssuePresubmitTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        spam=fake.SpamService())
    self.proj = self.services.project.TestAddProject('proj', project_id=789)
    self.cnxn = 'fake cnxn'
    self.servlet = issuepresubmit.IssuePresubmitJSON(
        'req', 'res', services=self.services)
    self.local_id_1 = self.services.issue.CreateIssue(
        self.cnxn, self.services,
        789, 'summary', 'status', 111L, [], [], [], [], 111L,
        'The screen is just dark when I press power on')

  def testAssertBasePermission_NormalNewIssue(self):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.proj,
        perms=permissions.EMPTY_PERMISSIONSET)
    # Note: mr.issue_id is None
    self.servlet.AssertBasePermission(mr)

  def testAssertBasePermission_NormalExistingIssue(self):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.proj,
        perms=permissions.USER_PERMISSIONSET)
    mr.local_id = self.local_id_1
    self.servlet.AssertBasePermission(mr)

  def testAssertBasePermission_NoPermsExistingIssue(self):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.proj,
        perms=permissions.EMPTY_PERMISSIONSET)
    mr.local_id = self.local_id_1
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

