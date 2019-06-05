# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for projectadminadvanced module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import time
import unittest
from mock import patch

from framework import permissions
from project import projectadminadvanced
from proto import project_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers

NOW = 1277762224


class ProjectAdminAdvancedTest(unittest.TestCase):
  """Unit tests for the ProjectAdminAdvanced servlet class."""

  def setUp(self):
    services = service_manager.Services(
        project=fake.ProjectService())
    self.servlet = projectadminadvanced.ProjectAdminAdvanced(
        'req', 'res', services=services)
    self.project = services.project.TestAddProject('proj', owner_ids=[111])
    self.mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        user_info={'user_id':111})

  def testAssertBasePermission(self):
    # Signed-out users cannot edit the project
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, self.mr)

    # Non-member users cannot edit the project
    self.mr.perms = permissions.USER_PERMISSIONSET
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, self.mr)

    # Contributors cannot edit the project
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

  def testGatherPageData(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.ADMIN_TAB_ADVANCED,
                     page_data['admin_tab_mode'])

  def testGatherPublishingOptions_Live(self):
    pub_data = self.servlet._GatherPublishingOptions(self.mr)
    self.assertTrue(pub_data['offer_archive'])
    self.assertTrue(pub_data['offer_move'])
    self.assertFalse(pub_data['offer_publish'])
    self.assertFalse(pub_data['offer_delete'])
    self.assertEqual('http://', pub_data['moved_to'])

  def testGatherPublishingOptions_Moved(self):
    self.project.moved_to = 'other location'
    pub_data = self.servlet._GatherPublishingOptions(self.mr)
    self.assertTrue(pub_data['offer_archive'])
    self.assertTrue(pub_data['offer_move'])
    self.assertFalse(pub_data['offer_publish'])
    self.assertFalse(pub_data['offer_delete'])
    self.assertEqual('other location', pub_data['moved_to'])

  def testGatherPublishingOptions_Archived(self):
    self.project.state = project_pb2.ProjectState.ARCHIVED
    pub_data = self.servlet._GatherPublishingOptions(self.mr)
    self.assertFalse(pub_data['offer_archive'])
    self.assertFalse(pub_data['offer_move'])
    self.assertTrue(pub_data['offer_publish'])
    self.assertTrue(pub_data['offer_delete'])

  def testGatherPublishingOptions_Doomed(self):
    self.project.state = project_pb2.ProjectState.ARCHIVED
    self.project.state_reason = 'you are a spammer'
    pub_data = self.servlet._GatherPublishingOptions(self.mr)
    self.assertFalse(pub_data['offer_archive'])
    self.assertFalse(pub_data['offer_move'])
    self.assertFalse(pub_data['offer_publish'])
    self.assertTrue(pub_data['offer_delete'])

  def testGatherQuotaData(self):
    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    quota_data = self.servlet._GatherQuotaData(self.mr)
    self.assertFalse(quota_data['offer_quota_editing'])

    self.mr.perms = permissions.ADMIN_PERMISSIONSET
    quota_data = self.servlet._GatherQuotaData(self.mr)
    self.assertTrue(quota_data['offer_quota_editing'])

  def testBuildComponentQuota(self):
    ezt_item = self.servlet._BuildComponentQuota(
        5000, 10000, 'attachments')
    self.assertEqual(50, ezt_item.used_percent)
    self.assertEqual('attachments', ezt_item.field_name)

  @patch('time.time')
  def testProcessFormData_NotDeleted(self, mock_time):
    mock_time.return_value = NOW
    self.mr.project_name = 'proj'
    post_data = fake.PostData()
    next_url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertEqual(
        'http://127.0.0.1/p/proj/adminAdvanced?saved=1&ts=%s' % NOW,
        next_url)

  def testProcessFormData_AfterDeletion(self):
    self.mr.project_name = 'proj'
    self.project.state = project_pb2.ProjectState.ARCHIVED
    post_data = fake.PostData(deletebtn='1')
    next_url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertEqual('http://127.0.0.1/hosting/', next_url)
