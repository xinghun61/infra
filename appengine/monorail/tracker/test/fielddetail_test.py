# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the fielddetail servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mox
import unittest
import logging

import webapp2

from third_party import ezt

from framework import permissions
from proto import project_pb2
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import fielddetail
from tracker import tracker_bizobj
from tracker import tracker_views


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
    self.services.user.TestAddUser('gatsby@example.com', 111)
    self.services.user.TestAddUser('sport@example.com', 222)
    self.mr.field_name = 'CPU'

    # Approvals
    self.approval_def = tracker_pb2.ApprovalDef(
        approval_id=234, approver_ids=[111], survey='Question 1?')
    self.sub_fd = tracker_pb2.FieldDef(
        field_name='UIMocks', approval_id=234, applicable_type='')
    self.sub_fd_deleted = tracker_pb2.FieldDef(
        field_name='UIMocksDeleted', approval_id=234, applicable_type='',
        is_deleted=True)
    self.config.field_defs.extend([self.sub_fd, self.sub_fd_deleted])
    self.config.approval_defs.append(self.approval_def)
    self.approval_fd = tracker_bizobj.MakeFieldDef(
        234, 789, 'UIReview', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.config.field_defs.append(self.approval_fd)

    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

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
    self.assertEqual(page_data['approval_subfields'], [])
    self.assertEqual(page_data['initial_approvers'], '')

  def testGatherPageData_ReadOnly(self):
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_LABELS,
                     page_data['admin_tab_mode'])
    self.assertFalse(page_data['allow_edit'])
    self.assertEqual('', page_data['initial_admins'])
    field_def_view = page_data['field_def']
    self.assertEqual('CPU', field_def_view.field_name)
    self.assertEqual(page_data['approval_subfields'], [])
    self.assertEqual(page_data['initial_approvers'], '')

  def testGatherPageData_Approval(self):
    self.mr.field_name = 'UIReview'
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(page_data['approval_subfields'], [self.sub_fd])
    self.assertEqual(page_data['initial_approvers'], 'gatsby@example.com')
    field_def_view = page_data['field_def']
    self.assertEqual(field_def_view.field_name, 'UIReview')
    self.assertEqual(field_def_view.survey, 'Question 1?')

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

  def testProcessFormData_Cancel(self):
    post_data = fake.PostData(
        name=['CPU'],
        cancel=['Submit'],
        max_value=['200'])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    logging.info(url)
    self.assertTrue('/adminLabels?ts=' in url)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)

    fd = tracker_bizobj.FindFieldDef('CPU', config)
    self.assertIsNone(fd.max_value)
    self.assertIsNone(fd.min_value)

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
    self.servlet._ProcessDeleteField(self.mr, self.config, self.fd)
    self.assertTrue(self.fd.is_deleted)

  def testProcessDeleteField_subfields(self):
    approval_fd = tracker_bizobj.MakeFieldDef(
        3, 789, 'Legal', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.fd.approval_id=3
    self.config.field_defs.append(approval_fd)
    self.servlet._ProcessDeleteField(self.mr, self.config, approval_fd)
    self.assertTrue(self.fd.is_deleted)
    self.assertTrue(approval_fd.is_deleted)

  def testProcessEditField_Normal(self):
    post_data = fake.PostData(
        name=['CPU'], field_type=['INT_TYPE'], min_value=['2'],
        admin_names=[''])
    self.servlet._ProcessEditField(
        self.mr, post_data, self.config, self.fd)
    fd = tracker_bizobj.FindFieldDef('CPU', self.config)
    self.assertEqual('CPU', fd.field_name)
    self.assertEqual(2, fd.min_value)

  def testProcessEditField_Reject(self):
    post_data = fake.PostData(
        name=['CPU'], field_type=['INT_TYPE'], min_value=['4'],
        max_value=['1'], admin_names=[''])

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        self.mr, field_def=mox.IgnoreArg(),
        initial_applicable_type='',
        initial_choices='',
        initial_admins='',
        initial_approvers='')
    self.mox.ReplayAll()

    url = self.servlet._ProcessEditField(
        self.mr, post_data, self.config, self.fd)
    self.assertEqual('Minimum value must be less than maximum.',
                     self.mr.errors.min_value)
    self.assertIsNone(url)

    fd = tracker_bizobj.FindFieldDef('CPU', self.config)
    self.assertIsNone(fd.min_value)
    self.assertIsNone(fd.max_value)

  def testProcessEditField_RejectApproval(self):
    self.mr.field_name = 'UIReview'
    post_data = fake.PostData(
        name=['UIReview'], admin_names=[''],
        survey=['WIll there be UI changes?'],
        approver_names=[''])

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        self.mr, field_def=mox.IgnoreArg(),
        initial_applicable_type='',
        initial_choices='',
        initial_admins='',
        initial_approvers='')
    self.mox.ReplayAll()

    url = self.servlet._ProcessEditField(
        self.mr, post_data, self.config, self.approval_fd)
    self.assertEqual('Please provide at least one default approver.',
                     self.mr.errors.approvers)
    self.assertIsNone(url)

  def testProcessEditField_Approval(self):
    self.mr.field_name = 'UIReview'
    post_data = fake.PostData(
        name=['UIReview'], admin_names=[''],
        survey=['WIll there be UI changes?'],
        approver_names=['sport@example.com, gatsby@example.com'])


    url = self.servlet._ProcessEditField(
        self.mr, post_data, self.config, self.approval_fd)
    self.assertTrue('/fields/detail?field=UIReview&saved=1&' in url)

    approval_def = tracker_bizobj.FindApprovalDef('UIReview', self.config)
    self.assertEqual(len(approval_def.approver_ids), 2)
    self.assertEqual(sorted(approval_def.approver_ids), sorted([111, 222]))
