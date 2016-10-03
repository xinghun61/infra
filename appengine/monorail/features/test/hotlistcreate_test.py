# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit test for Hotlist creation servlet."""

import unittest

import settings
from framework import permissions
from features import hotlistcreate
from proto import site_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class HotlistCreateTest(unittest.TestCase):
  """Tests for the HotlistCreate servlet."""

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.mr = testing_helpers.MakeMonorailRequest()
    self.services = service_manager.Services(project=fake.ProjectService(),
                                        user=fake.UserService(),
                                        issue=fake.IssueService())
    self.servlet = hotlistcreate.HotlistCreate('req', 'res',
                                               services=self.services)
    self.project = self.services.project.TestAddProject('projectname',
                                                        project_id=123)
    self.issue1_local_id = self.services.issue.CreateIssue(self.cnxn,
                                                           self.services,
                                                      self.project.project_id,
                                                           'issue1_summary',
                                                      'status', 111L, [], [],
                                                           [], [], 111L,
                                                           'issue1_description')
    self.issue2_local_id = self.services.issue.CreateIssue(self.cnxn,
                                                           self.services,
                                                      self.project.project_id,
                                                           'issue2_summary',
                                                      'status', 111L, [], [],
                                                           [], [], 111L,
                                                      'issue2_description')
    self.issue1 = self.services.issue.issues_by_project[
        self.project.project_id][self.issue1_local_id]
    self.issue2 = self.services.issue.issues_by_project[
        self.project.project_id][self.issue2_local_id]

  def testParseIssueRefs(self):
    issue_refs_string = "projectname: %d, projectname: %d" % (
        self.issue1_local_id, self.issue2_local_id)
    self.mr.project_name = 'projectname'
    # list of global issue_ids
    issue_ids = self.servlet.ParseIssueRefs(self.mr, issue_refs_string)
    self.assertIn(self.issue2.issue_id, issue_ids)
    self.assertIn(self.issue1.issue_id, issue_ids)

  def CheckAssertBasePermissions(
      self, restriction, expect_admin_ok, expect_nonadmin_ok):
    old_hotlist_creation_restriction = settings.hotlist_creation_restriction
    settings.hotlist_creation_restriction = restriction

    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.GetPermissions(None, {}, None))
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, mr)

    mr = testing_helpers.MakeMonorailRequest()
    if expect_admin_ok:
      self.servlet.AssertBasePermission(mr)
    else:
      self.assertRaises(
          permissions.PermissionException,
          self.servlet.AssertBasePermission, mr)

    mr = testing_helpers.MakeMonorailRequest(
        perms=permissions.GetPermissions(mr.auth.user_pb, {111L}, None))
    if expect_nonadmin_ok:
      self.servlet.AssertBasePermission(mr)
    else:
      self.assertRaises(
          permissions.PermissionException,
          self.servlet.AssertBasePermission, mr)

    settings.hotlist_creation_restriction = old_hotlist_creation_restriction

  def testAssertBasePermission(self):
    self.CheckAssertBasePermissions(
        site_pb2.UserTypeRestriction.ANYONE, True, True)
    self.CheckAssertBasePermissions(
        site_pb2.UserTypeRestriction.ADMIN_ONLY, True, False)
    self.CheckAssertBasePermissions(
        site_pb2.UserTypeRestriction.NO_ONE, False, False)

  def testGatherPageData(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual('st6', page_data['user_tab_mode'])
    self.assertEqual('', page_data['initial_name'])
    self.assertEqual('', page_data['initial_summary'])
    self.assertEqual('', page_data['initial_description'])
    self.assertEqual('', page_data['initial_issues'])
    self.assertEqual('', page_data['initial_editors'])
    self.assertEqual('no', page_data['initial_privacy'])

  def testProcessFormData(self):
    pass
  # TODO(jojwang): implement this test after adding CreateHotlist and
  # other functions to Features Services in testing/fake.py
