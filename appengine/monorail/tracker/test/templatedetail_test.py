# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for Template editing/viewing servlet."""

import logging
import unittest

import settings

from framework import permissions
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import templatedetail
from tracker import tracker_bizobj


class TemplateDetailTest(unittest.TestCase):
  """Tests for the TemplateDetail servlet."""

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(project=fake.ProjectService(),
                                             config=fake.ConfigService(),
                                             user=fake.UserService())
    self.servlet = templatedetail.TemplateDetail('req', 'res',
                                               services=self.services)

    self.services.user.TestAddUser('gatsby@example.com', 111L)
    self.services.user.TestAddUser('sport@example.com', 222L)
    self.services.user.TestAddUser('gatsby@example.com', 111L)
    self.services.user.TestAddUser('daisy@example.com', 333L)

    self.project = self.services.project.TestAddProject('proj')
    self.services.project.TestAddProjectMembers(
        [333L], self.project, 'CONTRIBUTOR_ROLE')

    self.template = self.test_template = tracker_bizobj.MakeIssueTemplate(
        'TestTemplate', 'sum', 'New', 111L, 'content', ['label1', 'label2'],
        [], [222L], [], summary_must_be_edited=False,
        owner_defaults_to_member=False, component_required=False,
        members_only=False)
    self.template.template_id = 12345

    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', self.project.project_id)
    self.config.templates.append(self.template)
    self.services.config.StoreConfig(None, self.config)

    self.mr = testing_helpers.MakeMonorailRequest(project=self.project)
    self.mr.template_name = 'TestTemplate'

  def testAssertBasePermission_Anyone(self):
    self.mr.auth.effective_ids = {222L}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.auth.effective_ids = {333L}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

  def testAssertBasePermision_MembersOnly(self):
    self.template.members_only = True
    self.mr.auth.effective_ids = {222L}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.auth.effective_ids = {333L}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.auth.effective_ids = {444L}
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

  def testGatherPageData(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_TEMPLATES,
                     page_data['admin_tab_mode'])
    self.assertTrue(page_data['allow_edit'])
    self.assertFalse(page_data['new_template_form'])
    self.assertItemsEqual(page_data['labels'], ['label1', 'label2'])
    self.assertEqual(page_data['initial_admins'], 'sport@example.com')
    self.assertEqual(page_data['initial_owner'], 'gatsby@example.com')
    # TODO(jojwang): test fields, components, and template_view

  def testProcessFormData(self):
    pass
