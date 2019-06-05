# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for projectadmin module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import permissions
from project import projectadmin
from proto import project_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class ProjectAdminTest(unittest.TestCase):
  """Unit tests for the ProjectAdmin servlet class."""

  def setUp(self):
    services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService())
    self.servlet = projectadmin.ProjectAdmin('req', 'res', services=services)
    self.project = services.project.TestAddProject(
        'proj', summary='a summary', description='a description')
    self.request, self.mr = testing_helpers.GetRequestObjects(
        project=self.project)

  def testAssertBasePermission(self):
    # Contributors cannot edit the project
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    # Signed-out users cannot edit the project
    mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    # Non-member users cannot edit the project
    mr.perms = permissions.USER_PERMISSIONSET
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    # Owners can edit the project
    mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(mr)

  def testGatherPageData(self):
    # Project has all default values.
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual('a summary', page_data['initial_summary'])
    self.assertEqual('a description', page_data['initial_description'])
    self.assertEqual(
        int(project_pb2.ProjectAccess.ANYONE), page_data['initial_access'].key)

    self.assertFalse(page_data['process_inbound_email'])
    self.assertFalse(page_data['only_owners_remove_restrictions'])
    self.assertFalse(page_data['only_owners_see_contributors'])

    # Now try some alternate Project field values.
    self.project.only_owners_remove_restrictions = True
    self.project.only_owners_see_contributors = True
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertTrue(page_data['only_owners_remove_restrictions'])
    self.assertTrue(page_data['only_owners_see_contributors'])

    # TODO(jrobbins): many more tests needed.
