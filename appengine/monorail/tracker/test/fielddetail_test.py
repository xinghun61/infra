# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the fielddetail servlet."""

import unittest

import webapp2

from framework import permissions
from proto import project_pb2
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import fielddetail
from tracker import tracker_bizobj


class FieldDetailTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        config=fake.ConfigService(),
        project=fake.ProjectService())
    self.servlet = fielddetail.FieldDetail(
        'req', 'res', services=self.services)
    self.project = self.services.project.TestAddProject('proj')
    self.mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', self.project.project_id)
    self.services.config.StoreConfig('fake cnxn', self.config)
    self.fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.config.field_defs.append(self.fd)
    self.mr.field_name = 'CPU'

  def testGetFieldDef_NotFound(self):
    self.mr.field_name = 'NeverHeardOfIt'
    self.assertRaises(
        webapp2.HTTPException,
        self.servlet._GetFieldDef, self.mr)

  def testGetFieldDef_Normal(self):
    actual_config, actual_fd = self.servlet._GetFieldDef(self.mr)
    self.assertEqual(self.config, actual_config)
    self.assertEqual(self.fd, actual_fd)

  def testAssertBasePermission_AnyoneCanView(self):
    self.servlet.AssertBasePermission(self.mr)
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

  def testAssertBasePermission_MembersOnly(self):
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    # The project members can view the field definition.
    self.servlet.AssertBasePermission(self.mr)
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)
    # Non-member is not allowed to view anything in the project.
    self.mr.perms = permissions.EMPTY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

  def testGatherPageData_ReadWrite(self):
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_LABELS,
                     page_data['admin_tab_mode'])
    self.assertTrue(page_data['allow_edit'])
    self.assertEqual('', page_data['initial_admins'])
    field_def_view = page_data['field_def']
    self.assertEqual('CPU', field_def_view.field_name)

  def testGatherPageData_ReadOnly(self):
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_LABELS,
                     page_data['admin_tab_mode'])
    self.assertFalse(page_data['allow_edit'])
    self.assertEqual('', page_data['initial_admins'])
    field_def_view = page_data['field_def']
    self.assertEqual('CPU', field_def_view.field_name)

  def testProcessFormData_Permission(self):
    """Only owners can edit fields."""
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project,
        perms=permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    mr.field_name = 'CPU'
    post_data = fake.PostData(
        name=['CPU'],
        deletefield=['Submit'])
    self.assertRaises(permissions.PermissionException,
                      self.servlet.ProcessFormData, mr, post_data)

    self.servlet.ProcessFormData(self.mr, post_data)

  def testProcessFormData_Delete(self):
    post_data = fake.PostData(
        name=['CPU'],
        deletefield=['Submit'])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue('/adminLabels?deleted=1&' in url)
    fd = tracker_bizobj.FindFieldDef('CPU', self.config)
    self.assertEqual('CPU', fd.field_name)
    self.assertTrue(fd.is_deleted)

  def testProcessFormData_Edit(self):
    post_data = fake.PostData(
        name=['CPU'],
        field_type=['INT_TYPE'],
        min_value=['2'],
        max_value=['98'],
        notify_on=['never'],
        is_required=[],
        is_multivalued=[],
        docstring=['It is just some field'],
        applicable_type=['Defect'],
        admin_names=[''])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue('/fields/detail?field=CPU&saved=1&' in url)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)

    fd = tracker_bizobj.FindFieldDef('CPU', config)
    self.assertEqual('CPU', fd.field_name)
    self.assertEqual(2, fd.min_value)
    self.assertEqual(98, fd.max_value)

  def testProcessDeleteField(self):
    self.servlet._ProcessDeleteField(self.mr, self.fd)
    self.assertTrue(self.fd.is_deleted)

  def testProcessEditField(self):
    post_data = fake.PostData(
        name=['CPU'], field_type=['INT_TYPE'], min_value=['2'],
        admin_names=[''])
    self.servlet._ProcessEditField(
        self.mr, post_data, self.config, self.fd)
    fd = tracker_bizobj.FindFieldDef('CPU', self.config)
    self.assertEqual('CPU', fd.field_name)
    self.assertEqual(2, fd.min_value)
