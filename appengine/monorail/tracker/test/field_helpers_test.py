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
    self.assertEqual('', parsed.approvers_str)
    self.assertEqual('', parsed.survey)
    self.assertEqual('', parsed.parent_approval_name)
    self.assertFalse(parsed.is_phase_field)

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
        applicable_type=['Defect'],
        approver_names=['approver@chromium.org'],
        survey=['Are there UX changes?'],
        parent_approval_name=['UIReview'],
        is_phase_field=['on'],
    )
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
    self.assertEqual('approver@chromium.org', parsed.approvers_str)
    self.assertEqual('Are there UX changes?', parsed.survey)
    self.assertEqual('UIReview', parsed.parent_approval_name)
    self.assertTrue(parsed.is_phase_field)

  def testParseFieldDefRequest_PreventPhaseApprovals(self):
    post_data = fake.PostData(
        field_type=['approval_type'],
        is_phase_field=['on'],
    )
    parsed = field_helpers.ParseFieldDefRequest(post_data, self.config)
    self.assertEqual('approval_type', parsed.field_type_str)
    self.assertFalse(parsed.is_phase_field)

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

  def testReviseApprovals_New(self):
    self.config.field_defs.append(
      tracker_bizobj.MakeFieldDef(
          123, 789, 'UX Review', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
          '', False, False, False, None, None, '', False, '', '',
          tracker_pb2.NotifyTriggers.NEVER, 'no_action',
          'Approval for UX review', False))
    existing_approvaldef = tracker_pb2.ApprovalDef(
        approval_id=123, approver_ids=[101L, 102L], survey='')
    self.config.approval_defs = [existing_approvaldef]
    revised_approvals = field_helpers.ReviseApprovals(
        124, [103L], '', self.config)
    self.assertEqual(len(revised_approvals), 2)
    self.assertEqual(revised_approvals,
                     [(123, [101L, 102L], ''), (124, [103L], '')])

  def testReviseApprovals_Existing(self):
    existing_approvaldef = tracker_pb2.ApprovalDef(
        approval_id=123, approver_ids=[101L, 102L], survey='')
    self.config.approval_defs = [existing_approvaldef]
    revised_approvals = field_helpers.ReviseApprovals(
        123, [103L], '', self.config)
    self.assertEqual(revised_approvals, [(123, [103L], '')])

  def testParseOneFieldValue_IntType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Foo', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = field_helpers.ParseOneFieldValue(
        self.mr.cnxn, self.services.user, fd, '8675309')
    self.assertEqual(fv.field_id, 123)
    self.assertEqual(fv.int_value, 8675309)

  def testParseOneFieldValue_StrType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Foo', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = field_helpers.ParseOneFieldValue(
        self.mr.cnxn, self.services.user, fd, '8675309')
    self.assertEqual(fv.field_id, 123)
    self.assertEqual(fv.str_value, '8675309')

  def testParseOneFieldValue_UserType(self):
    self.services.user.TestAddUser('user@example.com', 111L)
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Foo', tracker_pb2.FieldTypes.USER_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = field_helpers.ParseOneFieldValue(
        self.mr.cnxn, self.services.user, fd, 'user@example.com')
    self.assertEqual(fv.field_id, 123)
    self.assertEqual(fv.user_id, 111)

  def testParseOneFieldValue_DateType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Deadline', tracker_pb2.FieldTypes.DATE_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = field_helpers.ParseOneFieldValue(
        self.mr.cnxn, self.services.user, fd, '2009-02-13')
    self.assertEqual(fv.field_id, 123)
    self.assertEqual(fv.date_value, 1234483200)

  def testParseOneFieldValue_UrlType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Design Doc', tracker_pb2.FieldTypes.URL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = field_helpers.ParseOneFieldValue(
        self.mr.cnxn, self.services.user, fd, 'www.google.com')
    self.assertEqual(fv.field_id, 123)
    self.assertEqual(fv.url_value, 'http://www.google.com')

  def testParseOneFieldValue(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Target', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'milestone target',
        False, is_phase_field=True)
    phase_fvs = field_helpers.ParseOnePhaseFieldValue(
        self.mr.cnxn, self.services.user, fd, '70', [30, 40])
    self.assertEqual(len(phase_fvs), 2)
    self.assertEqual(phase_fvs[0].phase_id, 30)
    self.assertEqual(phase_fvs[1].phase_id, 40)

  def testParseFieldValues_Empty(self):
    field_val_strs = {}
    field_values = field_helpers.ParseFieldValues(
        self.mr.cnxn, self.services.user, field_val_strs, self.config)
    self.assertEqual([], field_values)

  def testParseFieldValues_EmptyPhases(self):
    field_val_strs = {126: ['70']}
    fd_phase = tracker_bizobj.MakeFieldDef(
        126, 789, 'Target', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'milestone target',
        False, is_phase_field=True)
    self.config.field_defs.extend([fd_phase])
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
    fd_phase = tracker_bizobj.MakeFieldDef(
        126, 789, 'Target', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'milestone target',
        False, is_phase_field=True)
    self.config.field_defs.extend([fd_int, fd_date, fd_url, fd_phase])
    field_val_strs = {
        123: ['80386', '68040'],
        124: ['2009-02-13'],
        125: ['www.google.com'],
        126: ['70'],
    }
    field_values = field_helpers.ParseFieldValues(
        self.mr.cnxn, self.services.user, field_val_strs, self.config,
        phase_ids=[30, 40])
    fv1 = tracker_bizobj.MakeFieldValue(
        123, 80386, None, None, None, None, False)
    fv2 = tracker_bizobj.MakeFieldValue(
        123, 68040, None, None, None, None, False)
    fv3 = tracker_bizobj.MakeFieldValue(
        124, None, None, None, 1234483200, None, False)
    fv4 = tracker_bizobj.MakeFieldValue(
        125, None, None, None, None, 'http://www.google.com', False)
    fv5 = tracker_bizobj.MakeFieldValue(
        126, 70, None, None, None, None, False, phase_id=30)
    fv6 = tracker_bizobj.MakeFieldValue(
        126, 70, None, None, None, None, False, phase_id=40)
    self.assertEqual([fv1, fv2, fv3, fv4, fv5, fv6], field_values)

  def test_IntType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = tracker_bizobj.MakeFieldValue(123, 8086, None, None, None, None, False)
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
    self.assertIsNone(msg)

    fd.min_value = 1
    fd.max_value = 999
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
    self.assertEqual('Value must be <= 999', msg)

    fv.int_value = 0
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
    self.assertEqual('Value must be >= 1', msg)

  def test_FilterIntType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fd.min_value = 1
    fd.max_value = 100
    fvs = [
        tracker_bizobj.MakeFieldValue(123, 200, None, None, None, None, False),
        tracker_bizobj.MakeFieldValue(124, 99, None, None, None, None, False),
        tracker_bizobj.MakeFieldValue(125, 0, None, None, None, None, False)]
    self.assertEqual([fvs[1]],
                     field_helpers.FilterValidFieldValues(
                         self.mr, self.mr.project, self.services, fd, fvs))

  def test_StrType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = tracker_bizobj.MakeFieldValue(
        123, None, 'i386', None, None, None, False)
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
    self.assertIsNone(msg)

    fd.regex = r'^\d*$'
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
    self.assertEqual(r'Value must match regular expression: ^\d*$', msg)

    fv.str_value = '386'
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
    self.assertIsNone(msg)

  def test_FilterStrType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fd.regex = r'^\d*$'
    fvs = [
        tracker_bizobj.MakeFieldValue(123, None, 'x3', None, None, None, False),
        tracker_bizobj.MakeFieldValue(124, None, '33', None, None, None, False),
        tracker_bizobj.MakeFieldValue(125, None, '', None, None, None, False)]
    self.assertEqual([fvs[1], fvs[2]],
                     field_helpers.FilterValidFieldValues(
                         self.mr, self.mr.project, self.services, fd, fvs))

  def test_UserType(self):
    pass  # TODO(jrobbins): write this test.

  def test_DateType(self):
    pass  # TODO(jrobbins): write this test. @@@

  def test_UrlType(self):
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'CPU', tracker_pb2.FieldTypes.URL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)

    fv = tracker_bizobj.MakeFieldValue(
        123, None, None, None, None, 'www.google.com', False)
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
    self.assertIsNone(msg)

    fv.url_value = 'go/puppies'
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
    self.assertIsNone(msg)

    fv.url_value = 'go/213'
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
    self.assertIsNone(msg)

    fv.url_value = 'puppies'
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
    self.assertEqual('Value must be a valid url', msg)

  def test_OtherType(self):
    # There are currently no validation options for date-type custom fields.
    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'Deadline', tracker_pb2.FieldTypes.DATE_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False)
    fv = tracker_bizobj.MakeFieldValue(
        123, None, None, None, 1234567890, None, False)
    msg = field_helpers.ValidateCustomField(
        self.mr, self.mr.project, self.services, fd, fv)
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

  def testFormatUrlFieldValue(self):
    self.assertEqual('http://www.google.com',
                     field_helpers.FormatUrlFieldValue('www.google.com'))
    self.assertEqual('https://www.bing.com',
                     field_helpers.FormatUrlFieldValue('https://www.bing.com'))

  def testReviseFieldDefFromParsed_INT(self):
    parsed_field_def = field_helpers.ParsedFieldDef(
        'EstDays', 'int_type', min_value=5, max_value=7, regex='',
        needs_member=True, needs_perm='Commit', grants_perm='View',
        notify_on=tracker_pb2.NotifyTriggers.ANY_COMMENT,
        is_required=True, is_niche=True, importance='required',
        is_multivalued=True, field_docstring='updated doc', choices_text='',
        applicable_type='Launch', applicable_predicate='', revised_labels=[],
        date_action_str='ping_participants', approvers_str='', survey='',
        parent_approval_name='', is_phase_field=False)

    fd = tracker_bizobj.MakeFieldDef(
        123, 789, 'EstDays', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, 4, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'doc', False,
        approval_id=3)

    new_fd = field_helpers.ReviseFieldDefFromParsed(parsed_field_def, fd)
    # assert INT fields
    self.assertEqual(new_fd.min_value, 5)
    self.assertEqual(new_fd.max_value, 7)

    # assert USER fields
    self.assertEqual(new_fd.notify_on, tracker_pb2.NotifyTriggers.ANY_COMMENT)
    self.assertTrue(new_fd.needs_member)
    self.assertEqual(new_fd.needs_perm, 'Commit')
    self.assertEqual(new_fd.grants_perm, 'View')

    # assert DATE fields
    self.assertEqual(new_fd.date_action,
                     tracker_pb2.DateAction.PING_PARTICIPANTS)

    # assert general fields
    self.assertTrue(new_fd.is_required)
    self.assertTrue(new_fd.is_niche)
    self.assertEqual(new_fd.applicable_type, 'Launch')
    self.assertEqual(new_fd.docstring, 'updated doc')
    self.assertTrue(new_fd.is_multivalued)
    self.assertEqual(new_fd.approval_id, 3)
    self.assertFalse(new_fd.is_phase_field)
