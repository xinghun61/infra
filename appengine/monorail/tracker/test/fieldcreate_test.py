# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the fieldcreate servlet."""

import unittest

from framework import permissions
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import fieldcreate
from tracker import tracker_bizobj


class FieldCreateTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        config=fake.ConfigService(),
        project=fake.ProjectService())
    self.servlet = fieldcreate.FieldCreate(
        'req', 'res', services=self.services)
    self.project = self.services.project.TestAddProject('proj')
    self.mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET)

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
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_LABELS,
                     page_data['admin_tab_mode'])
    self.assertItemsEqual(
        ['Defect', 'Enhancement', 'Task', 'Other'],
        page_data['well_known_issue_types'])

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


class CheckFieldNameJSONTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        user=fake.UserService(),
        config=fake.ConfigService(),
        project=fake.ProjectService())
    self.servlet = fieldcreate.CheckFieldNameJSON(
        'req', 'res', services=self.services)
    self.project = self.services.project.TestAddProject('proj')
    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', self.project.project_id)
    self.services.config.StoreConfig('fake cnxn', self.config)

  def testHandleRequest_NewField(self):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        path='/p/proj/fields/checkname?field=somefield')
    page_data = self.servlet.HandleRequest(mr)
    self.assertItemsEqual(
        ['error_message', 'choices'], page_data.keys())
    self.assertIsNone(page_data['error_message'])
    self.assertItemsEqual([], page_data['choices'])

  def testHandleRequest_FieldNameAlreadyUsed(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'doc', False)
    self.config.field_defs.append(fd)
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        path='/p/proj/fields/checkname?field=CPU')
    page_data = self.servlet.HandleRequest(mr)
    self.assertItemsEqual(
        ['error_message', 'choices'], page_data.keys())
    self.assertEqual('That name is already in use.',
                     page_data['error_message'])
    self.assertItemsEqual([], page_data['choices'])

  def testHandleRequest_ReservedField(self):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        path='/p/proj/fields/checkname?field=summary')
    page_data = self.servlet.HandleRequest(mr)
    self.assertItemsEqual(
        ['error_message', 'choices'], page_data.keys())
    self.assertEqual('That name is reserved.', page_data['error_message'])
    self.assertItemsEqual([], page_data['choices'])

  def testHandleRequest_LabelsToField(self):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET,
        path='/p/proj/fields/checkname?field=type')
    page_data = self.servlet.HandleRequest(mr)
    self.assertItemsEqual(
        ['error_message', 'choices'], page_data.keys())
    self.assertIsNone(page_data['error_message'])
    self.assertEqual(4, len(page_data['choices']))


class FieldCreateMethodsTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

  def testFieldNameErrorMessage_NoConflict(self):
    self.assertIsNone(fieldcreate.FieldNameErrorMessage(
        'somefield', self.config))

  def testFieldNameErrorMessage_Reserved(self):
    self.assertEqual(
        'That name is reserved.',
        fieldcreate.FieldNameErrorMessage('owner', self.config))

  def testFieldNameErrorMessage_AlreadyInUse(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'doc', False)
    self.config.field_defs.append(fd)
    self.assertEqual(
        'That name is already in use.',
        fieldcreate.FieldNameErrorMessage('CPU', self.config))

  def testFieldNameErrorMessage_PrefixOfExisting(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'sign-off', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'doc', False)
    self.config.field_defs.append(fd)
    self.assertEqual(
        'That name is a prefix of an existing field name.',
        fieldcreate.FieldNameErrorMessage('sign', self.config))

  def testFieldNameErrorMessage_IncludesExisting(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'opt', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'doc', False)
    self.config.field_defs.append(fd)
    self.assertEqual(
        'An existing field name is a prefix of that name.',
        fieldcreate.FieldNameErrorMessage('opt-in', self.config))

  def testExistingEnumChoices_NewEnum(self):
    self.assertItemsEqual(
        [],
        fieldcreate.ExistingEnumChoices('Theme', self.config))

  def testExistingEnumChoices_ConvertLabelsToEnum(self):
    label_doc_list = fieldcreate.ExistingEnumChoices('Priority', self.config)
    self.assertItemsEqual(
        ['Critical', 'High', 'Medium', 'Low'],
        [item.name for item in label_doc_list])
