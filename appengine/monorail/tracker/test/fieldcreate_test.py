# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the fieldcreate servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mox
import unittest
import logging

from third_party import ezt

from framework import permissions
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import fieldcreate
from tracker import tracker_bizobj


class FieldCreateTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        user=fake.UserService(),
        config=fake.ConfigService(),
        project=fake.ProjectService())
    self.servlet = fieldcreate.FieldCreate(
        'req', 'res', services=self.services)
    self.project = self.services.project.TestAddProject('proj')
    self.mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET)

    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

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

  def testGatherPageData(self):
    approval_fd = tracker_bizobj.MakeFieldDef(
        1, self.mr.project_id, 'LaunchApproval',
        tracker_pb2.FieldTypes.APPROVAL_TYPE, None, '', False,
        False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'some approval thing', False)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)
    config.field_defs.append(approval_fd)
    self.services.config.StoreConfig(self.cnxn, config)
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_LABELS,
                     page_data['admin_tab_mode'])
    self.assertItemsEqual(
        ['Defect', 'Enhancement', 'Task', 'Other'],
        page_data['well_known_issue_types'])
    self.assertEqual(['LaunchApproval'], page_data['approval_names'])

  def testProcessFormData(self):
    post_data = fake.PostData(
        name=['somefield'],
        field_type=['INT_TYPE'],
        min_value=['1'],
        max_value=['99'],
        notify_on=['any_comment'],
        importance=['required'],
        is_multivalued=['Yes'],
        docstring=['It is just some field'],
        applicable_type=['Defect'],
        date_action=['no_action'],
        admin_names=[''])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue('/adminLabels?saved=1&' in url)
    config = self.services.config.GetProjectConfig(
        self.mr.cnxn, self.mr.project_id)

    fd = tracker_bizobj.FindFieldDef('somefield', config)
    self.assertEqual('somefield', fd.field_name)
    self.assertEqual(tracker_pb2.FieldTypes.INT_TYPE, fd.field_type)
    self.assertEqual(1, fd.min_value)
    self.assertEqual(99, fd.max_value)
    self.assertEqual(tracker_pb2.NotifyTriggers.ANY_COMMENT, fd.notify_on)
    self.assertTrue(fd.is_required)
    self.assertFalse(fd.is_niche)
    self.assertTrue(fd.is_multivalued)
    self.assertEqual('It is just some field', fd.docstring)
    self.assertEqual('Defect', fd.applicable_type)
    self.assertEqual('', fd.applicable_predicate)
    self.assertEqual([], fd.admin_ids)

  def testProcessFormData_RejectNoApprover(self):
    post_data = fake.PostData(
        name=['approvalField'],
        field_type=['approval_type'],
        approver_names=[''],
        admin_names=[''],
        parent_approval_name=['UIApproval'],
        is_phase_field=['on'])

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        self.mr, initial_field_name=post_data.get('name'),
        initial_type=post_data.get('field_type'),
        initial_field_docstring=post_data.get('docstring', ''),
        initial_applicable_type=post_data.get('applical_type', ''),
        initial_applicable_predicate='',
        initial_needs_member=ezt.boolean('needs_member' in post_data),
        initial_needs_perm=post_data.get('needs_perm', '').strip(),
        initial_importance=post_data.get('importance'),
        initial_is_multivalued=ezt.boolean('is_multivalued' in post_data),
        initial_grants_perm=post_data.get('grants_perm', '').strip(),
        initial_notify_on=0,
        initial_date_action= post_data.get('date_action'),
        initial_choices=post_data.get('choices', ''),
        initial_approvers=post_data.get('approver_names'),
        initial_parent_approval_name=post_data.get('parent_approval_name', ''),
        initial_survey=post_data.get('survey', ''),
        initial_is_phase_field=False,
        initial_admins=post_data.get('admin_names')
    )
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual(
        'Please provide at least one default approver.',
        self.mr.errors.approvers)
    self.assertIsNone(url)


class FieldCreateMethodsTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

  def testFieldNameErrorMessage_NoConflict(self):
    self.assertIsNone(fieldcreate.FieldNameErrorMessage(
        'somefield', self.config))

  def testFieldNameErrorMessage_PrefixReserved(self):
    self.assertEqual(
        'That name is reserved.',
        fieldcreate.FieldNameErrorMessage('owner', self.config))

  def testFieldNameErrorMessage_SuffixReserved(self):
    self.assertEqual(
        'That suffix is reserved.',
        fieldcreate.FieldNameErrorMessage('doh-approver', self.config))

  def testFieldNameErrorMessage_AlreadyInUse(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.config.field_defs.append(fd)
    self.assertEqual(
        'That name is already in use.',
        fieldcreate.FieldNameErrorMessage('CPU', self.config))

  def testFieldNameErrorMessage_PrefixOfExisting(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'sign-off', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.config.field_defs.append(fd)
    self.assertEqual(
        'That name is a prefix of an existing field name.',
        fieldcreate.FieldNameErrorMessage('sign', self.config))

  def testFieldNameErrorMessage_IncludesExisting(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'opt', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.config.field_defs.append(fd)
    self.assertEqual(
        'An existing field name is a prefix of that name.',
        fieldcreate.FieldNameErrorMessage('opt-in', self.config))
