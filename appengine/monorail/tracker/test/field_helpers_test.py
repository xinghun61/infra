# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the field_helpers module."""

import time
import unittest

from framework import template_helpers
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import field_helpers
from tracker import tracker_bizobj


class FieldHelpersTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.services = service_manager.Services(
        user=fake.UserService())
    self.mr = testing_helpers.MakeMonorailRequest(
        project=fake.Project(), services=self.services)
    self.mr.cnxn = fake.MonorailConnection()
    self.errors = template_helpers.EZTError()

  def testParseFieldDefRequest_Empty(self):
    post_data = fake.PostData()
    parsed = field_helpers.ParseFieldDefRequest(post_data, self.config)
    self.assertEqual('', parsed.field_name)
    self.assertEqual(None, parsed.field_type_str)
    self.assertEqual(None, parsed.min_value)
    self.assertEqual(None, parsed.max_value)
    self.assertEqual(None, parsed.regex)
    self.assertFalse(parsed.needs_member)
    self.assertEqual('', parsed.needs_perm)
    self.assertEqual('', parsed.grants_perm)
    self.assertEqual(0, parsed.notify_on)
    self.assertFalse(parsed.is_required)
    self.assertFalse(parsed.is_niche)
    self.assertFalse(parsed.is_multivalued)
    self.assertEqual('', parsed.field_docstring)
    self.assertEqual('', parsed.choices_text)
    self.assertEqual('', parsed.applicable_type)
    self.assertEqual('', parsed.applicable_predicate)
    unchanged_labels = [
        (label_def.label, label_def.label_docstring, False)
        for label_def in self.config.well_known_labels]
    self.assertEqual(unchanged_labels, parsed.revised_labels)

  def testParseFieldDefRequest_Normal(self):
    post_data = fake.PostData(
        name=['somefield'],
        field_type=['INT_TYPE'],
        min_value=['11'],
        max_value=['99'],
        regex=['.*'],
        needs_member=['Yes'],
        needs_perm=['Commit'],
        grants_perm=['View'],
        notify_on=['any_comment'],
        importance=['required'],
        is_multivalued=['Yes'],
        docstring=['It is just some field'],
        choices=['Hot = Lots of activity\nCold = Not much activity'],
        applicable_type=['Defect'])
    parsed = field_helpers.ParseFieldDefRequest(post_data, self.config)
    self.assertEqual('somefield', parsed.field_name)
    self.assertEqual('INT_TYPE', parsed.field_type_str)
    self.assertEqual(11, parsed.min_value)
    self.assertEqual(99, parsed.max_value)
    self.assertEqual('.*', parsed.regex)
    self.assertTrue(parsed.needs_member)
    self.assertEqual('Commit', parsed.needs_perm)
    self.assertEqual('View', parsed.grants_perm)
    self.assertEqual(1, parsed.notify_on)
    self.assertTrue(parsed.is_required)
    self.assertFalse(parsed.is_niche)
    self.assertTrue(parsed.is_multivalued)
    self.assertEqual('It is just some field', parsed.field_docstring)
    self.assertEqual('Hot = Lots of activity\nCold = Not much activity',
                     parsed.choices_text)
    self.assertEqual('Defect', parsed.applicable_type)
    self.assertEqual('', parsed.applicable_predicate)
    unchanged_labels = [
        (label_def.label, label_def.label_docstring, False)
        for label_def in self.config.well_known_labels]
    new_labels = [
        ('somefield-Hot', 'Lots of activity', False),
        ('somefield-Cold', 'Not much activity', False)]
    self.assertEqual(unchanged_labels + new_labels, parsed.revised_labels)

  def testParseChoicesIntoWellKnownLabels_NewFieldDef(self):
    choices_text = 'Hot = Lots of activity\nCold = Not much activity'
    field_name = 'somefield'
    revised_labels = field_helpers._ParseChoicesIntoWellKnownLabels(
        choices_text, field_name, self.config)
    unchanged_labels = [
        (label_def.label, label_def.label_docstring, False)
        for label_def in self.config.well_known_labels]
    new_labels = [
        ('somefield-Hot', 'Lots of activity', False),
        ('somefield-Cold', 'Not much activity', False)]
    self.assertEqual(unchanged_labels + new_labels, revised_labels)

  def testParseChoicesIntoWellKnownLabels_ConvertExistingLabel(self):
    choices_text = 'High = Must be fixed\nMedium = Might slip'
    field_name = 'Priority'
    revised_labels = field_helpers._ParseChoicesIntoWellKnownLabels(
        choices_text, field_name, self.config)
    kept_labels = [
        (label_def.label, label_def.label_docstring, False)
        for label_def in self.config.well_known_labels
        if not label_def.label.startswith('Priority-')]
    new_labels = [
        ('Priority-High', 'Must be fixed', False),
        ('Priority-Medium', 'Might slip', False)]
    self.maxDiff = None
    self.assertEqual(kept_labels + new_labels, revised_labels)

  def testShiftEnumFieldsIntoLabels_Empty(self):
    labels = []
    labels_remove = []
    field_val_strs = {}
    field_val_strs_remove = {}
    field_helpers.ShiftEnumFieldsIntoLabels(
        labels, labels_remove, field_val_strs, field_val_strs_remove,
        self.config)
    self.assertEqual([], labels)
    self.assertEqual([], labels_remove)
    self.assertEqual({}, field_val_strs)
    self.assertEqual({}, field_val_strs_remove)

  def testShiftEnumFieldsIntoLabels_NoOp(self):
    labels = ['Security', 'Performance', 'Pri-1', 'M-2']
    labels_remove = ['ReleaseBlock']
    field_val_strs = {123: ['CPU']}
    field_val_strs_remove = {234: ['Small']}
    field_helpers.ShiftEnumFieldsIntoLabels(
        labels, labels_remove, field_val_strs, field_val_strs_remove,
        self.config)
    self.assertEqual(['Security', 'Performance', 'Pri-1', 'M-2'], labels)
    self.assertEqual(['ReleaseBlock'], labels_remove)
    self.assertEqual({123: ['CPU']}, field_val_strs)
    self.assertEqual({234: ['Small']}, field_val_strs_remove)

  def testShiftEnumFieldsIntoLabels_FoundSomeEnumFields(self):
    self.config.field_defs.append(
        tracker_bizobj.MakeFieldDef(
            123, 789, 'Component', tracker_pb2.FieldTypes.ENUM_TYPE, None,
            '', False, False, False, None, None, '', False, '', '',
            tracker_pb2.NotifyTriggers.NEVER,
            'no_action', 'What HW part is affected?',
            False))
    self.config.field_defs.append(
        tracker_bizobj.MakeFieldDef(
            234, 789, 'Size', tracker_pb2.FieldTypes.ENUM_TYPE, None,
            '', False, False, False, None, None, '', False, '', '',
            tracker_pb2.NotifyTriggers.NEVER,
            'no_action', 'How big is this work item?',
            False))
    labels = ['Security', 'Performance', 'Pri-1', 'M-2']
    labels_remove = ['ReleaseBlock']
    field_val_strs = {123: ['CPU']}
    field_val_strs_remove = {234: ['Small']}
    field_helpers.ShiftEnumFieldsIntoLabels(
        labels, labels_remove, field_val_strs, field_val_strs_remove,
        self.config)
    self.assertEqual(
        ['Security', 'Performance', 'Pri-1', 'M-2', 'Component-CPU'],
        labels)
    self.assertEqual(['ReleaseBlock', 'Size-Small'], labels_remove)
    self.assertEqual({}, field_val_strs)
    self.assertEqual({}, field_val_strs_remove)

  def testParseOneFieldValue_IntType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Foo', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = field_helpers._ParseOneFieldValue(
        self.mr.cnxn, self.services.user, fd, '8675309')
    self.assertEqual(fv.field_id, 123)
    self.assertEqual(fv.int_value, 8675309)

  def testParseOneFieldValue_StrType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Foo', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = field_helpers._ParseOneFieldValue(
        self.mr.cnxn, self.services.user, fd, '8675309')
    self.assertEqual(fv.field_id, 123)
    self.assertEqual(fv.str_value, '8675309')

  def testParseOneFieldValue_UserType(self):
    self.services.user.TestAddUser('user@example.com', 111L)
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Foo', tracker_pb2.FieldTypes.USER_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = field_helpers._ParseOneFieldValue(
        self.mr.cnxn, self.services.user, fd, 'user@example.com')
    self.assertEqual(fv.field_id, 123)
    self.assertEqual(fv.user_id, 111)

  def testParseOneFieldValue_DateType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Deadline', tracker_pb2.FieldTypes.DATE_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = field_helpers._ParseOneFieldValue(
        self.mr.cnxn, self.services.user, fd, '2009-02-13')
    self.assertEqual(fv.field_id, 123)
    self.assertEqual(fv.date_value, 1234483200)

  def testParseOneFieldValue_UrlType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Design Doc', tracker_pb2.FieldTypes.URL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = field_helpers._ParseOneFieldValue(
        self.mr.cnxn, self.services.user, fd, 'www.google.com')
    self.assertEqual(fv.field_id, 123)
    self.assertEqual(fv.url_value, 'www.google.com')

  def testParseFieldValues_Empty(self):
    field_val_strs = {}
    field_values = field_helpers.ParseFieldValues(
        self.mr.cnxn, self.services.user, field_val_strs, self.config)
    self.assertEqual([], field_values)

  def testParseFieldValues_Normal(self):
    fd_int = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fd_date = tracker_bizobj.MakeFieldDef(
        124, 789, 'Deadline', tracker_pb2.FieldTypes.DATE_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fd_url = tracker_bizobj.MakeFieldDef(
        125, 789, 'Design Doc', tracker_pb2.FieldTypes.URL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.config.field_defs.extend([fd_int, fd_date, fd_url])
    field_val_strs = {
        123: ['80386', '68040'],
        124: ['2009-02-13'],
        125: ['www.google.com']}
    field_values = field_helpers.ParseFieldValues(
        self.mr.cnxn, self.services.user, field_val_strs, self.config)
    fv1 = tracker_bizobj.MakeFieldValue(
        123, 80386, None, None, None, None, False)
    fv2 = tracker_bizobj.MakeFieldValue(
        123, 68040, None, None, None, None, False)
    fv3 = tracker_bizobj.MakeFieldValue(
        124, None, None, None, 1234483200, None, False)
    fv4 = tracker_bizobj.MakeFieldValue(
        125, None, None, None, None, 'www.google.com', False)
    self.assertEqual([fv1, fv2, fv3, fv4], field_values)

  def testValidateOneCustomField_IntType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = tracker_bizobj.MakeFieldValue(123, 8086, None, None, None, None, False)
    msg = field_helpers._ValidateOneCustomField(
        self.mr, self.services, fd, fv)
    self.assertIsNone(msg)

    fd.min_value = 1
    fd.max_value = 999
    msg = field_helpers._ValidateOneCustomField(
        self.mr, self.services, fd, fv)
    self.assertEqual('Value must be <= 999', msg)

    fv.int_value = 0
    msg = field_helpers._ValidateOneCustomField(
        self.mr, self.services, fd, fv)
    self.assertEqual('Value must be >= 1', msg)

  def testValidateOneCustomField_StrType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = tracker_bizobj.MakeFieldValue(
        123, None, 'i386', None, None, None, False)
    msg = field_helpers._ValidateOneCustomField(
        self.mr, self.services, fd, fv)
    self.assertIsNone(msg)

    fd.regex = r'^\d*$'
    msg = field_helpers._ValidateOneCustomField(
        self.mr, self.services, fd, fv)
    self.assertEqual(r'Value must match regular expression: ^\d*$', msg)

    fv.str_value = '386'
    msg = field_helpers._ValidateOneCustomField(
        self.mr, self.services, fd, fv)
    self.assertIsNone(msg)

  def testValidateOneCustomField_UserType(self):
    pass  # TODO(jrobbins): write this test.

  def testValidateOneCustomField_DateType(self):
    pass  # TODO(jrobbins): write this test. @@@

  def testValidateOneCustomField_UrlType(self):
    pass # TODO(jojwang): write this test. This blocks feature launch.

  def testValidateOneCustomField_OtherType(self):
    # There are currently no validation options for date-type custom fields.
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Deadline', tracker_pb2.FieldTypes.DATE_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = tracker_bizobj.MakeFieldValue(
        123, None, None, None, 1234567890, None, False)
    msg = field_helpers._ValidateOneCustomField(
        self.mr, self.services, fd, fv)
    self.assertIsNone(msg)

  def testValidateCustomFields_NoCustomFieldValues(self):
    field_helpers.ValidateCustomFields(
        self.mr, self.services, [], self.config, self.errors)
    self.assertFalse(self.errors.AnyErrors())

  def testValidateCustomFields_NoErrors(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.config.field_defs.append(fd)
    fv1 = tracker_bizobj.MakeFieldValue(
        123, 8086, None, None, None, None, False)
    fv2 = tracker_bizobj.MakeFieldValue(123, 486, None, None, None, None, False)

    field_helpers.ValidateCustomFields(
        self.mr, self.services, [fv1, fv2], self.config, self.errors)
    self.assertFalse(self.errors.AnyErrors())

  def testValidateCustomFields_SomeErrors(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    self.config.field_defs.append(fd)
    fv1 = tracker_bizobj.MakeFieldValue(
        123, 8086, None, None, None, None, False)
    fv2 = tracker_bizobj.MakeFieldValue(123, 486, None, None, None, None, False)

    fd.min_value = 1
    fd.max_value = 999
    field_helpers.ValidateCustomFields(
        self.mr, self.services, [fv1, fv2], self.config, self.errors)
    self.assertTrue(self.errors.AnyErrors())
    self.assertEqual(1, len(self.errors.custom_fields))
    custom_field_error = self.errors.custom_fields[0]
    self.assertEqual(123, custom_field_error.field_id)
    self.assertEqual('Value must be <= 999', custom_field_error.message)
