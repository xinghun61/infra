# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the Project Creation servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

import settings
from framework import permissions
from proto import project_pb2
from proto import site_pb2
from services import service_manager
from sitewide import projectcreate
from testing import fake
from testing import testing_helpers


class ProjectCreateTest(unittest.TestCase):

  def setUp(self):
    services = service_manager.Services()
    self.servlet = projectcreate.ProjectCreate('req', 'res', services=services)

  def CheckAssertBasePermissions(
      self, restriction, expect_admin_ok, expect_nonadmin_ok):
    old_project_creation_restriction = settings.project_creation_restriction
    settings.project_creation_restriction = restriction

    # Anon users can never do it
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
        perms=permissions.GetPermissions(mr.auth.user_pb, {111}, None))
    if expect_nonadmin_ok:
      self.servlet.AssertBasePermission(mr)
    else:
      self.assertRaises(
          permissions.PermissionException,
          self.servlet.AssertBasePermission, mr)

    settings.project_creation_restriction = old_project_creation_restriction

  def testAssertBasePermission(self):
    self.CheckAssertBasePermissions(
        site_pb2.UserTypeRestriction.ANYONE, True, True)
    self.CheckAssertBasePermissions(
        site_pb2.UserTypeRestriction.ADMIN_ONLY, True, False)
    self.CheckAssertBasePermissions(
        site_pb2.UserTypeRestriction.NO_ONE, False, False)

  def testGatherPageData(self):
    mr = testing_helpers.MakeMonorailRequest()
    page_data = self.servlet.GatherPageData(mr)
    self.assertEqual('', page_data['initial_name'])
    self.assertEqual('', page_data['initial_summary'])
    self.assertEqual('', page_data['initial_description'])
    self.assertEqual([], page_data['labels'])
