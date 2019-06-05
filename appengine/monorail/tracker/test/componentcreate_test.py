# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the componentcreate servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import permissions
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import componentcreate
from tracker import tracker_bizobj

import webapp2


class ComponentCreateTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        config=fake.ConfigService(),
        project=fake.ProjectService())
    self.servlet = componentcreate.ComponentCreate(
        'req', 'res', services=self.services)
    self.project = self.services.project.TestAddProject('proj')
    self.mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.mr.auth.email = 'b@example.com'
    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', self.project.project_id)
    self.services.config.StoreConfig('fake cnxn', self.config)
    self.cd = tracker_bizobj.MakeComponentDef(
        1, self.project.project_id, 'BackEnd', 'doc', False, [], [111], 0,
        122)
    self.config.component_defs = [self.cd]
    self.services.user.TestAddUser('a@example.com', 111)
    self.services.user.TestAddUser('b@example.com', 122)

  def testAssertBasePermission(self):
    # Anon users can never do it
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

    # Project owner can do it.
    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

    # Project member cannot do it
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

  def testGatherPageData_CreatingAtTopLevel(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_COMPONENTS,
                     page_data['admin_tab_mode'])
    self.assertIsNone(page_data['parent_path'])

  def testGatherPageData_CreatingASubComponent(self):
    self.mr.component_path = 'BackEnd'
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_COMPONENTS,
                     page_data['admin_tab_mode'])
    self.assertEqual('BackEnd', page_data['parent_path'])

  def testProcessFormData_NotFound(self):
    post_data = fake.PostData(
        parent_path=['Monitoring'],
        leaf_name=['Rules'],
        docstring=['Detecting outages'],
        deprecated=[False],
        admins=[''],
        cc=[''],
        labels=[''])
    self.assertRaises(
        webapp2.HTTPException,
        self.servlet.ProcessFormData, self.mr, post_data)

  def testProcessFormData_Normal(self):
    post_data = fake.PostData(
        parent_path=['BackEnd'],
        leaf_name=['DB'],
        docstring=['A database'],
        deprecated=[False],
        admins=[''],
        cc=[''],
        labels=[''])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue('/adminComponents?saved=1&' in url)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)

    cd = tracker_bizobj.FindComponentDef('BackEnd>DB', config)
    self.assertEqual('BackEnd>DB', cd.path)
    self.assertEqual('A database', cd.docstring)
    self.assertEqual([], cd.admin_ids)
    self.assertEqual([], cd.cc_ids)
    self.assertTrue(cd.created > 0)
    self.assertEqual(122, cd.creator_id)


class ComponentCreateMethodsTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd1 = tracker_bizobj.MakeComponentDef(
        1, 789, 'BackEnd', 'doc', False, [], [111], 0, 122)
    cd2 = tracker_bizobj.MakeComponentDef(
        2, 789, 'BackEnd>DB', 'doc', True, [], [111], 0, 122)
    self.config.component_defs = [cd1, cd2]

  def testLeafNameErrorMessage_Invalid(self):
    self.assertEqual(
        'Invalid component name',
        componentcreate.LeafNameErrorMessage('', 'bad name', self.config))

  def testLeafNameErrorMessage_AlreadyInUse(self):
    self.assertEqual(
        'That name is already in use.',
        componentcreate.LeafNameErrorMessage('', 'BackEnd', self.config))
    self.assertEqual(
        'That name is already in use.',
        componentcreate.LeafNameErrorMessage('BackEnd', 'DB', self.config))

  def testLeafNameErrorMessage_OK(self):
    self.assertIsNone(
        componentcreate.LeafNameErrorMessage('', 'FrontEnd', self.config))
    self.assertIsNone(
        componentcreate.LeafNameErrorMessage('BackEnd', 'Search', self.config))
