# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for issue tracker bizobj functions."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
import logging

from framework import framework_constants
from framework import framework_views
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants


class BizobjTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        issue=fake.IssueService())
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.config.field_defs = [
        tracker_pb2.FieldDef(
            field_id=1, project_id=789, field_name='EstDays',
            field_type=tracker_pb2.FieldTypes.INT_TYPE)
        ]
    self.config.component_defs = [
        tracker_pb2.ComponentDef(component_id=1, project_id=789, path='UI'),
        tracker_pb2.ComponentDef(component_id=2, project_id=789, path='DB'),
        ]

  def testGetOwnerId(self):
    issue = tracker_pb2.Issue()
    self.assertEquals(
        tracker_bizobj.GetOwnerId(issue), framework_constants.NO_USER_SPECIFIED)

    issue.derived_owner_id = 123
    self.assertEquals(tracker_bizobj.GetOwnerId(issue), 123)

    issue.owner_id = 456
    self.assertEquals(tracker_bizobj.GetOwnerId(issue), 456)

  def testGetStatus(self):
    issue = tracker_pb2.Issue()
    self.assertEquals(tracker_bizobj.GetStatus(issue), '')

    issue.derived_status = 'InReview'
    self.assertEquals(tracker_bizobj.GetStatus(issue), 'InReview')

    issue.status = 'Forgotten'
    self.assertEquals(tracker_bizobj.GetStatus(issue), 'Forgotten')

  def testGetCcIds(self):
    issue = tracker_pb2.Issue()
    self.assertEquals(tracker_bizobj.GetCcIds(issue), [])

    issue.derived_cc_ids.extend([1, 2, 3])
    self.assertEquals(tracker_bizobj.GetCcIds(issue), [1, 2, 3])

    issue.cc_ids.extend([4, 5, 6])
    self.assertEquals(tracker_bizobj.GetCcIds(issue), [4, 5, 6, 1, 2, 3])

  def testGetApproverIds(self):
    issue = tracker_pb2.Issue()
    self.assertEqual(tracker_bizobj.GetApproverIds(issue), [])

    av_1 = tracker_pb2.ApprovalValue(approver_ids=[111, 222])
    av_2 = tracker_pb2.ApprovalValue()
    av_3 = tracker_pb2.ApprovalValue(approver_ids=[222, 333])
    issue.approval_values = [av_1, av_2, av_3]
    self.assertItemsEqual(
        tracker_bizobj.GetApproverIds(issue), [111, 222, 333])

  def testGetLabels(self):
    issue = tracker_pb2.Issue()
    self.assertEquals(tracker_bizobj.GetLabels(issue), [])

    issue.derived_labels.extend(['a', 'b', 'c'])
    self.assertEquals(tracker_bizobj.GetLabels(issue), ['a', 'b', 'c'])

    issue.labels.extend(['d', 'e', 'f'])
    self.assertEquals(tracker_bizobj.GetLabels(issue),
                      ['d', 'e', 'f', 'a', 'b', 'c'])

  def testFindFieldDef_None(self):
    config = tracker_pb2.ProjectIssueConfig()
    self.assertIsNone(tracker_bizobj.FindFieldDef(None, config))

  def testFindFieldDef_Empty(self):
    config = tracker_pb2.ProjectIssueConfig()
    self.assertIsNone(tracker_bizobj.FindFieldDef('EstDays', config))

  def testFindFieldDef_Default(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.assertIsNone(tracker_bizobj.FindFieldDef('EstDays', config))

  def testFindFieldDef_Normal(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(field_name='EstDays')
    config.field_defs = [fd]
    self.assertEqual(fd, tracker_bizobj.FindFieldDef('EstDays', config))
    self.assertEqual(fd, tracker_bizobj.FindFieldDef('ESTDAYS', config))
    self.assertIsNone(tracker_bizobj.FindFieldDef('Unknown', config))

  def testFindFieldDefByID_Empty(self):
    config = tracker_pb2.ProjectIssueConfig()
    self.assertIsNone(tracker_bizobj.FindFieldDefByID(1, config))

  def testFindFieldDefByID_Default(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.assertIsNone(tracker_bizobj.FindFieldDefByID(1, config))

  def testFindFieldDefByID_Normal(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(field_id=1)
    config.field_defs = [fd]
    self.assertEqual(fd, tracker_bizobj.FindFieldDefByID(1, config))
    self.assertIsNone(tracker_bizobj.FindFieldDefByID(99, config))

  def testFindApprovalDef_Empty(self):
    config = tracker_pb2.ProjectIssueConfig()
    self.assertEqual(None, tracker_bizobj.FindApprovalDef(
        'Nonexistent', config))

  def testFindApprovalDef_Normal(self):
    config = tracker_pb2.ProjectIssueConfig()
    approval_fd = tracker_pb2.FieldDef(field_id=1, field_name='UIApproval')
    approval_def = tracker_pb2.ApprovalDef(
        approval_id=1, approver_ids=[111], survey='')
    config.field_defs = [approval_fd]
    config.approval_defs = [approval_def]
    self.assertEqual(approval_def, tracker_bizobj.FindApprovalDef(
        'UIApproval', config))

  def testFindApprovalDef_NotApproval(self):
    config = tracker_pb2.ProjectIssueConfig()
    field_def = tracker_pb2.FieldDef(field_id=1, field_name='DesignDoc')
    config.field_defs = [field_def]
    self.assertEqual(None, tracker_bizobj.FindApprovalDef('DesignDoc', config))

  def testFindApprovalDefByID_Empty(self):
    config = tracker_pb2.ProjectIssueConfig()
    self.assertEqual(None, tracker_bizobj.FindApprovalDefByID(1, config))

  def testFindApprovalDefByID_Normal(self):
    config = tracker_pb2.ProjectIssueConfig()
    approval_def = tracker_pb2.ApprovalDef(
        approval_id=1, approver_ids=[111, 222], survey='')
    config.approval_defs = [approval_def]
    self.assertEqual(approval_def, tracker_bizobj.FindApprovalDefByID(
        1, config))
    self.assertEqual(None, tracker_bizobj.FindApprovalDefByID(99, config))

  def testFindApprovalValueByID_Normal(self):
    av_24 = tracker_pb2.ApprovalValue(approval_id=24)
    av_22 = tracker_pb2.ApprovalValue()
    self.assertEqual(
        av_24, tracker_bizobj.FindApprovalValueByID(24, [av_22, av_24]))

  def testFindApprovalValueByID_None(self):
    av_no_id = tracker_pb2.ApprovalValue()
    self.assertIsNone(tracker_bizobj.FindApprovalValueByID(24, [av_no_id]))

  def testFindApprovalsSubfields(self):
    config = tracker_pb2.ProjectIssueConfig()
    subfd_1 = tracker_pb2.FieldDef(approval_id=1)
    subfd_2 = tracker_pb2.FieldDef(approval_id=2)
    subfd_3 = tracker_pb2.FieldDef(approval_id=1)
    subfd_4 = tracker_pb2.FieldDef()
    config.field_defs = [subfd_1, subfd_2, subfd_3, subfd_4]

    subfields_dict = tracker_bizobj.FindApprovalsSubfields([1, 2], config)
    self.assertItemsEqual(subfields_dict[1], [subfd_1, subfd_3])
    self.assertItemsEqual(subfields_dict[2], [subfd_2])
    self.assertItemsEqual(subfields_dict[3], [])

  def testFindPhaseByID_Normal(self):
    canary_phase = tracker_pb2.Phase(phase_id=2, name='Canary')
    stable_phase = tracker_pb2.Phase(name='Stable')
    self.assertEqual(
        canary_phase,
        tracker_bizobj.FindPhaseByID(2, [stable_phase, canary_phase]))

  def testFindPhaseByID_None(self):
    stable_phase = tracker_pb2.Phase(name='Stable')
    self.assertIsNone(tracker_bizobj.FindPhaseByID(42, [stable_phase]))

  def testFindPhase_Normal(self):
    canary_phase = tracker_pb2.Phase(phase_id=2)
    stable_phase = tracker_pb2.Phase(name='Stable')
    self.assertEqual(stable_phase, tracker_bizobj.FindPhase(
        'Stable', [stable_phase, canary_phase]))

  def testFindPhase_None(self):
    self.assertIsNone(tracker_bizobj.FindPhase('ghost_phase', []))

  def testGetGrantedPerms_Empty(self):
    config = tracker_pb2.ProjectIssueConfig()
    issue = tracker_pb2.Issue()
    self.assertEqual(
        set(), tracker_bizobj.GetGrantedPerms(issue, {111}, config))

  def testGetGrantedPerms_Default(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    issue = tracker_pb2.Issue()
    self.assertEqual(
        set(), tracker_bizobj.GetGrantedPerms(issue, {111}, config))

  def testGetGrantedPerms_NothingGranted(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(field_id=1)  # Nothing granted
    config.field_defs = [fd]
    fv = tracker_pb2.FieldValue(field_id=1, user_id=222)
    issue = tracker_pb2.Issue(field_values=[fv])
    self.assertEqual(
        set(),
        tracker_bizobj.GetGrantedPerms(issue, {111, 222}, config))

  def testGetGrantedPerms_Normal(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(field_id=1, grants_perm='Highlight')
    config.field_defs = [fd]
    fv = tracker_pb2.FieldValue(field_id=1, user_id=222)
    issue = tracker_pb2.Issue(field_values=[fv])
    self.assertEqual(
        set(),
        tracker_bizobj.GetGrantedPerms(issue, {111}, config))
    self.assertEqual(
        set(['highlight']),
        tracker_bizobj.GetGrantedPerms(issue, {111, 222}, config))

  def testLabelsByPrefix(self):
    expected = tracker_bizobj.LabelsByPrefix(
      ['OneWordLabel', 'Key-Value1', 'Key-Value2', 'Launch-X-Y-Z'],
      ['launch-x'])
    self.assertEqual(
      {'key': ['Value1', 'Value2'],
       'launch-x': ['Y-Z']},
      expected)

  def testLabelIsMaskedByField(self):
    self.assertIsNone(tracker_bizobj.LabelIsMaskedByField('UI', []))
    self.assertIsNone(tracker_bizobj.LabelIsMaskedByField('P-1', []))
    field_names = ['priority', 'size']
    self.assertIsNone(tracker_bizobj.LabelIsMaskedByField(
        'UI', field_names))
    self.assertIsNone(tracker_bizobj.LabelIsMaskedByField(
        'OS-All', field_names))
    self.assertEqual(
        'size', tracker_bizobj.LabelIsMaskedByField('size-xl', field_names))
    self.assertEqual(
        'size', tracker_bizobj.LabelIsMaskedByField('Size-XL', field_names))

  def testNonMaskedLabels(self):
    self.assertEqual([], tracker_bizobj.NonMaskedLabels([], []))
    field_names = ['priority', 'size']
    self.assertEqual([], tracker_bizobj.NonMaskedLabels([], field_names))
    self.assertEqual(
        [], tracker_bizobj.NonMaskedLabels(['Size-XL'], field_names))
    self.assertEqual(
        ['Hot'], tracker_bizobj.NonMaskedLabels(['Hot'], field_names))
    self.assertEqual(
        ['Hot'],
        tracker_bizobj.NonMaskedLabels(['Hot', 'Size-XL'], field_names))

  def testMakeApprovalValue_Basic(self):
    av = tracker_bizobj.MakeApprovalValue(2)
    expected = tracker_pb2.ApprovalValue(approval_id=2)
    self.assertEqual(av, expected)

  def testMakeApprovalValue_Full(self):
    av = tracker_bizobj.MakeApprovalValue(
        2, approver_ids=[], status=tracker_pb2.ApprovalStatus.APPROVED,
        setter_id=3, set_on=123, phase_id=3)
    expected = tracker_pb2.ApprovalValue(
        approval_id=2, approver_ids=[],
        status=tracker_pb2.ApprovalStatus.APPROVED,
        setter_id=3, set_on=123, phase_id=3)
    self.assertEqual(av, expected)

  def testMakeFieldDef_Basic(self):
    fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'Size', tracker_pb2.FieldTypes.USER_TYPE, None, None,
        False, False, False, None, None, None, False,
        None, None, None, 'no_action', 'Some field', False)
    self.assertEqual(1, fd.field_id)
    self.assertEqual(None, fd.approval_id)
    self.assertFalse(fd.is_phase_field)

  def testMakeFieldDef_Full(self):
    fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'Size', tracker_pb2.FieldTypes.INT_TYPE, None, None,
        False, False, False, 1, 100, None, False,
        None, None, None, 'no_action', 'Some field', False, approval_id=4,
        is_phase_field=True)
    self.assertEqual(1, fd.min_value)
    self.assertEqual(100, fd.max_value)
    self.assertEqual(4, fd.approval_id)
    self.assertTrue(fd.is_phase_field)

    fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'Size', tracker_pb2.FieldTypes.STR_TYPE, None, None,
        False, False, False, None, None, 'A.*Z', False,
        'EditIssue', None, None, 'no_action', 'Some field', False, 4)
    self.assertEqual('A.*Z', fd.regex)
    self.assertEqual('EditIssue', fd.needs_perm)
    self.assertEqual(4, fd.approval_id)

  def testMakeFieldDef_IntBools(self):
    fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'Size', tracker_pb2.FieldTypes.INT_TYPE, None, None,
        0, 0, 0, 1, 100, None, 0,
        None, None, None, 'no_action', 'Some field', 0, approval_id=4,
        is_phase_field=1)
    self.assertFalse(fd.is_required)
    self.assertFalse(fd.is_niche)
    self.assertFalse(fd.is_multivalued)
    self.assertFalse(fd.needs_member)
    self.assertFalse(fd.is_deleted)
    self.assertTrue(fd.is_phase_field)

  def testMakeFieldValue(self):
    # Only the first value counts.
    fv = tracker_bizobj.MakeFieldValue(1, 42, 'yay', 111, None, None, True)
    self.assertEqual(1, fv.field_id)
    self.assertEqual(42, fv.int_value)
    self.assertIsNone(fv.str_value)
    self.assertEqual(None, fv.user_id)
    self.assertEqual(None, fv.phase_id)

    fv = tracker_bizobj.MakeFieldValue(1, None, 'yay', 111, None, None, True)
    self.assertEqual('yay', fv.str_value)
    self.assertEqual(None, fv.user_id)

    fv = tracker_bizobj.MakeFieldValue(1, None, None, 111, None, None, True)
    self.assertEqual(111, fv.user_id)
    self.assertEqual(True, fv.derived)

    fv = tracker_bizobj.MakeFieldValue(
        1, None, None, None, 1234567890, None, True)
    self.assertEqual(1234567890, fv.date_value)
    self.assertEqual(True, fv.derived)

    fv = tracker_bizobj.MakeFieldValue(
        1, None, None, None, None, 'www.google.com', True, phase_id=1)
    self.assertEqual('www.google.com', fv.url_value)
    self.assertEqual(True, fv.derived)
    self.assertEqual(1, fv.phase_id)

    with self.assertRaises(ValueError):
      tracker_bizobj.MakeFieldValue(1, None, None, None, None, None, True)

  def testGetFieldValueWithRawValue(self):
    class MockUser(object):
      def __init__(self):
        self.email = 'test@example.com'
    users_by_id = {111: MockUser()}

    class MockFieldValue(object):
      def __init__(
          self, int_value=None, str_value=None, user_id=None,
          date_value=None, url_value=None):
        self.int_value = int_value
        self.str_value = str_value
        self.user_id = user_id
        self.date_value = date_value
        self.url_value = url_value

    # Test user types.
    # Use user_id from the field_value and get user from users_by_id.
    val = tracker_bizobj.GetFieldValueWithRawValue(
        field_type=tracker_pb2.FieldTypes.USER_TYPE,
        users_by_id=users_by_id,
        field_value=MockFieldValue(user_id=111),
        raw_value=113,
    )
    self.assertEqual('test@example.com', val)
    # Specify user_id that does not exist in users_by_id.
    val = tracker_bizobj.GetFieldValueWithRawValue(
        field_type=tracker_pb2.FieldTypes.USER_TYPE,
        users_by_id=users_by_id,
        field_value=MockFieldValue(user_id=112),
        raw_value=113,
    )
    self.assertEqual(112, val)
    # Pass in empty users_by_id.
    val = tracker_bizobj.GetFieldValueWithRawValue(
        field_type=tracker_pb2.FieldTypes.USER_TYPE,
        users_by_id={},
        field_value=MockFieldValue(user_id=111),
        raw_value=113,
    )
    self.assertEqual(111, val)
    # Test different raw_values.
    raw_value_tests = (
        (111, 'test@example.com'),
        (112, 112),
        (framework_constants.NO_USER_NAME, framework_constants.NO_USER_NAME))
    for (raw_value, expected_output) in raw_value_tests:
      val = tracker_bizobj.GetFieldValueWithRawValue(
          field_type=tracker_pb2.FieldTypes.USER_TYPE,
          users_by_id=users_by_id,
          field_value=None,
          raw_value=raw_value,
      )
      self.assertEqual(expected_output, val)

    # Test enum types.
    # The returned value should be the raw_value regardless of field_value being
    # specified.
    for field_value in (MockFieldValue(), None):
      val = tracker_bizobj.GetFieldValueWithRawValue(
          field_type=tracker_pb2.FieldTypes.ENUM_TYPE,
          users_by_id=users_by_id,
          field_value=field_value,
          raw_value='abc',
      )
      self.assertEqual('abc', val)

    # Test int type.
    # Use int_value from the field_value.
    val = tracker_bizobj.GetFieldValueWithRawValue(
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        users_by_id=users_by_id,
        field_value=MockFieldValue(int_value=100),
        raw_value=101,
    )
    self.assertEqual(100, val)
    # Use the raw_value when field_value is not specified.
    val = tracker_bizobj.GetFieldValueWithRawValue(
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        users_by_id=users_by_id,
        field_value=None,
        raw_value=101,
    )
    self.assertEqual(101, val)

    # Test str type.
    # Use str_value from the field_value.
    val = tracker_bizobj.GetFieldValueWithRawValue(
        field_type=tracker_pb2.FieldTypes.STR_TYPE,
        users_by_id=users_by_id,
        field_value=MockFieldValue(str_value='testing'),
        raw_value='test',
    )
    self.assertEqual('testing', val)
    # Use the raw_value when field_value is not specified.
    val = tracker_bizobj.GetFieldValueWithRawValue(
        field_type=tracker_pb2.FieldTypes.STR_TYPE,
        users_by_id=users_by_id,
        field_value=None,
        raw_value='test',
    )
    self.assertEqual('test', val)

    # Test date type.
    # Use date_value from the field_value.
    val = tracker_bizobj.GetFieldValueWithRawValue(
        field_type=tracker_pb2.FieldTypes.DATE_TYPE,
        users_by_id=users_by_id,
        field_value=MockFieldValue(date_value=1234567890),
        raw_value=2345678901,
    )
    self.assertEqual('2009-02-13', val)
    # Use the raw_value when field_value is not specified.
    val = tracker_bizobj.GetFieldValueWithRawValue(
        field_type=tracker_pb2.FieldTypes.DATE_TYPE,
        users_by_id=users_by_id,
        field_value=None,
        raw_value='2016-10-30',
    )
    self.assertEqual('2016-10-30', val)

  def testFindComponentDef_Empty(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    actual = tracker_bizobj.FindComponentDef('DB', config)
    self.assertIsNone(actual)

  def testFindComponentDef_NoMatch(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(path='UI>Splash')
    config.component_defs.append(cd)
    actual = tracker_bizobj.FindComponentDef('DB', config)
    self.assertIsNone(actual)

  def testFindComponentDef_MatchFound(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(path='UI>Splash')
    config.component_defs.append(cd)
    actual = tracker_bizobj.FindComponentDef('UI>Splash', config)
    self.assertEqual(cd, actual)

  def testFindMatchingComponentIDs_Empty(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    actual = tracker_bizobj.FindMatchingComponentIDs('DB', config)
    self.assertEqual([], actual)
    actual = tracker_bizobj.FindMatchingComponentIDs('DB', config, exact=False)
    self.assertEqual([], actual)

  def testFindMatchingComponentIDs_NoMatch(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=1, path='UI>Splash'))
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=2, path='UI>AboutBox'))
    actual = tracker_bizobj.FindMatchingComponentIDs('DB', config)
    self.assertEqual([], actual)
    actual = tracker_bizobj.FindMatchingComponentIDs('DB', config, exact=False)
    self.assertEqual([], actual)

  def testFindMatchingComponentIDs_Match(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=1, path='UI>Splash'))
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=2, path='UI>AboutBox'))
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=3, path='DB>Attachments'))
    actual = tracker_bizobj.FindMatchingComponentIDs('DB', config)
    self.assertEqual([], actual)
    actual = tracker_bizobj.FindMatchingComponentIDs('DB', config, exact=False)
    self.assertEqual([3], actual)

  def testFindMatchingComponentIDs_MatchMultiple(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=1, path='UI>Splash'))
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=2, path='UI>AboutBox'))
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=22, path='UI>AboutBox'))
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=3, path='DB>Attachments'))
    actual = tracker_bizobj.FindMatchingComponentIDs('UI>AboutBox', config)
    self.assertEqual([2, 22], actual)
    actual = tracker_bizobj.FindMatchingComponentIDs('UI', config, exact=False)
    self.assertEqual([1, 2, 22], actual)

  def testFindComponentDefByID_Empty(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    actual = tracker_bizobj.FindComponentDefByID(999, config)
    self.assertIsNone(actual)

  def testFindComponentDefByID_NoMatch(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=1, path='UI>Splash'))
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=2, path='UI>AboutBox'))
    actual = tracker_bizobj.FindComponentDefByID(999, config)
    self.assertIsNone(actual)

  def testFindComponentDefByID_MatchFound(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(component_id=1, path='UI>Splash')
    config.component_defs.append(cd)
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=2, path='UI>AboutBox'))
    actual = tracker_bizobj.FindComponentDefByID(1, config)
    self.assertEqual(cd, actual)

  def testFindAncestorComponents_Empty(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(component_id=1, path='UI>Splash')
    actual = tracker_bizobj.FindAncestorComponents(config, cd)
    self.assertEqual([], actual)

  def testFindAncestorComponents_NoMatch(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(component_id=1, path='UI>Splash')
    config.component_defs.append(tracker_pb2.ComponentDef(
        component_id=2, path='UI>AboutBox'))
    actual = tracker_bizobj.FindAncestorComponents(config, cd)
    self.assertEqual([], actual)

  def testFindAncestorComponents_NoComponents(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(component_id=1, path='UI')
    config.component_defs.append(cd)
    cd2 = tracker_pb2.ComponentDef(component_id=2, path='UI>Splash')
    config.component_defs.append(cd2)
    actual = tracker_bizobj.FindAncestorComponents(config, cd2)
    self.assertEqual([cd], actual)

  def testGetIssueComponentsAndAncestors_NoSuchComponent(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(component_id=1, path='UI')
    config.component_defs.append(cd)
    cd2 = tracker_pb2.ComponentDef(component_id=2, path='UI>Splash')
    config.component_defs.append(cd2)
    issue = tracker_pb2.Issue(component_ids=[999])
    actual = tracker_bizobj.GetIssueComponentsAndAncestors(issue, config)
    self.assertEqual([], actual)

  def testGetIssueComponentsAndAncestors_AffectsNoComponents(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(component_id=1, path='UI')
    config.component_defs.append(cd)
    cd2 = tracker_pb2.ComponentDef(component_id=2, path='UI>Splash')
    config.component_defs.append(cd2)
    issue = tracker_pb2.Issue(component_ids=[])
    actual = tracker_bizobj.GetIssueComponentsAndAncestors(issue, config)
    self.assertEqual([], actual)

  def testGetIssueComponentsAndAncestors_AffectsSomeComponents(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(component_id=1, path='UI')
    config.component_defs.append(cd)
    cd2 = tracker_pb2.ComponentDef(component_id=2, path='UI>Splash')
    config.component_defs.append(cd2)
    issue = tracker_pb2.Issue(component_ids=[2])
    actual = tracker_bizobj.GetIssueComponentsAndAncestors(issue, config)
    self.assertEqual([cd, cd2], actual)

  def testFindDescendantComponents_Empty(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(component_id=1, path='UI')
    actual = tracker_bizobj.FindDescendantComponents(config, cd)
    self.assertEqual([], actual)

  def testFindDescendantComponents_NoMatch(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(component_id=1, path='UI')
    config.component_defs.append(cd)
    actual = tracker_bizobj.FindDescendantComponents(config, cd)
    self.assertEqual([], actual)

  def testFindDescendantComponents_SomeMatch(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    cd = tracker_pb2.ComponentDef(component_id=1, path='UI')
    config.component_defs.append(cd)
    cd2 = tracker_pb2.ComponentDef(component_id=2, path='UI>Splash')
    config.component_defs.append(cd2)
    actual = tracker_bizobj.FindDescendantComponents(config, cd)
    self.assertEqual([cd2], actual)

  def testMakeComponentDef(self):
    cd = tracker_bizobj.MakeComponentDef(
      1, 789, 'UI', 'doc', False, [111], [222], 1234567890,
      111)
    self.assertEqual(1, cd.component_id)
    self.assertEqual([111], cd.admin_ids)
    self.assertEqual([], cd.label_ids)

  def testMakeSavedQuery_WithNone(self):
    sq = tracker_bizobj.MakeSavedQuery(
      None, 'my query', 2, 'priority:high')
    self.assertEqual(None, sq.query_id)
    self.assertEqual(None, sq.subscription_mode)
    self.assertEqual([], sq.executes_in_project_ids)

  def testMakeSavedQuery(self):
    sq = tracker_bizobj.MakeSavedQuery(
      100, 'my query', 2, 'priority:high',
      subscription_mode='immediate', executes_in_project_ids=[789])
    self.assertEqual(100, sq.query_id)
    self.assertEqual('immediate', sq.subscription_mode)
    self.assertEqual([789], sq.executes_in_project_ids)

  def testConvertDictToTemplate(self):
    template = tracker_bizobj.ConvertDictToTemplate(
        dict(name='name', content='content', summary='summary',
             status='status', owner_id=111))
    self.assertEqual('name', template.name)
    self.assertEqual('content', template.content)
    self.assertEqual('summary', template.summary)
    self.assertEqual('status', template.status)
    self.assertEqual(111, template.owner_id)
    self.assertFalse(template.summary_must_be_edited)
    self.assertTrue(template.owner_defaults_to_member)
    self.assertFalse(template.component_required)

    template = tracker_bizobj.ConvertDictToTemplate(
        dict(name='name', content='content', labels=['a', 'b', 'c']))
    self.assertListEqual(
        ['a', 'b', 'c'], list(template.labels))

    template = tracker_bizobj.ConvertDictToTemplate(
        dict(name='name', content='content', summary_must_be_edited=True,
             owner_defaults_to_member=True, component_required=True))
    self.assertTrue(template.summary_must_be_edited)
    self.assertTrue(template.owner_defaults_to_member)
    self.assertTrue(template.component_required)

    template = tracker_bizobj.ConvertDictToTemplate(
        dict(name='name', content='content', summary_must_be_edited=False,
             owner_defaults_to_member=False, component_required=False))
    self.assertFalse(template.summary_must_be_edited)
    self.assertFalse(template.owner_defaults_to_member)
    self.assertFalse(template.component_required)

  def CheckDefaultConfig(self, config):
    self.assertTrue(len(config.well_known_statuses) > 0)
    self.assertTrue(config.statuses_offer_merge > 0)
    self.assertTrue(len(config.well_known_labels) > 0)
    self.assertTrue(len(config.exclusive_label_prefixes) > 0)
    # TODO(jrobbins): test actual values from default config

  def testMakeDefaultProjectIssueConfig(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.default_template_for_developers = 1
    config.default_template_for_users = 2
    self.CheckDefaultConfig(config)

  def testHarmonizeConfigs_Empty(self):
    harmonized = tracker_bizobj.HarmonizeConfigs([])
    self.CheckDefaultConfig(harmonized)

  def testHarmonizeConfigs(self):
    c1 = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    harmonized = tracker_bizobj.HarmonizeConfigs([c1])
    self.assertListEqual(
        [stat.status for stat in c1.well_known_statuses],
        [stat.status for stat in harmonized.well_known_statuses])
    self.assertListEqual(
        [lab.label for lab in c1.well_known_labels],
        [lab.label for lab in harmonized.well_known_labels])
    self.assertEqual('', harmonized.default_sort_spec)

    c2 = tracker_bizobj.MakeDefaultProjectIssueConfig(678)
    tracker_bizobj.SetConfigStatuses(c2, [
        ('Unconfirmed', '', True, False),
        ('New', '', True, True),
        ('Accepted', '', True, False),
        ('Begun', '', True, False),
        ('Fixed', '', False, False),
        ('Obsolete', '', False, False)])
    tracker_bizobj.SetConfigLabels(c2, [
        ('Pri-0', '', False),
        ('Priority-High', '', True),
        ('Pri-1', '', False),
        ('Priority-Medium', '', True),
        ('Pri-2', '', False),
        ('Priority-Low', '', True),
        ('Pri-3', '', False),
        ('Pri-4', '', False)])
    c2.default_sort_spec = 'Pri -status'

    c1.approval_defs = [
        tracker_pb2.ApprovalDef(approval_id=1),
        tracker_pb2.ApprovalDef(approval_id=3),
    ]
    c1.field_defs = [
      tracker_pb2.FieldDef(
          field_id=1, project_id=789, field_name='CowApproval',
          field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
      tracker_pb2.FieldDef(
          field_id=3, project_id=789, field_name='MooApproval',
          field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    ]
    c2.approval_defs = [
        tracker_pb2.ApprovalDef(approval_id=2),
    ]
    c2.field_defs = [
        tracker_pb2.FieldDef(
            field_id=2, project_id=788, field_name='CowApproval',
            field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
    ]
    harmonized = tracker_bizobj.HarmonizeConfigs([c1, c2])
    result_statuses = [stat.status
                       for stat in harmonized.well_known_statuses]
    result_labels = [lab.label
                     for lab in harmonized.well_known_labels]
    self.assertListEqual(
        ['Unconfirmed', 'New', 'Accepted', 'Begun', 'Started', 'Fixed',
         'Obsolete', 'Verified', 'Invalid', 'Duplicate', 'WontFix', 'Done'],
        result_statuses)
    self.assertListEqual(
        ['Pri-0', 'Type-Defect', 'Type-Enhancement', 'Type-Task',
         'Type-Other', 'Priority-Critical', 'Priority-High',
         'Pri-1', 'Priority-Medium', 'Pri-2', 'Priority-Low', 'Pri-3',
         'Pri-4'],
        result_labels[:result_labels.index('OpSys-All')])
    self.assertEqual('Pri -status', harmonized.default_sort_spec.strip())
    self.assertItemsEqual(c1.field_defs + c2.field_defs,
                          harmonized.field_defs)
    self.assertItemsEqual(c1.approval_defs + c2.approval_defs,
                          harmonized.approval_defs)

  def testHarmonizeConfigsMeansOpen(self):
    c1 = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    c2 = tracker_bizobj.MakeDefaultProjectIssueConfig(678)
    means_open = [("TT", True, True),
                  ("TF", True, False),
                  ("FT", False, True),
                  ("FF", False, False)]
    tracker_bizobj.SetConfigStatuses(c1, [
        (x[0], x[0], x[1], False)
         for x in means_open])
    tracker_bizobj.SetConfigStatuses(c2, [
        (x[0], x[0], x[2], False)
         for x in means_open])

    harmonized = tracker_bizobj.HarmonizeConfigs([c1, c2])
    for stat in harmonized.well_known_statuses:
      self.assertEqual(stat.means_open, stat.status != "FF")

  def testHarmonizeConfigs_DeletedCustomField(self):
    """Only non-deleted custom fields in configs are included."""
    harmonized = tracker_bizobj.HarmonizeConfigs([self.config])
    self.assertEqual(1, len(harmonized.field_defs))

    self.config.field_defs[0].is_deleted = True
    harmonized = tracker_bizobj.HarmonizeConfigs([self.config])
    self.assertEqual(0, len(harmonized.field_defs))

  def testHarmonizeLabelOrStatusRows_Empty(self):
    def_rows = []
    actual = tracker_bizobj.HarmonizeLabelOrStatusRows(def_rows)
    self.assertEqual([], actual)

  def testHarmonizeLabelOrStatusRows_Normal(self):
    def_rows = [
        (100, 789, 1, 'Priority-High'),
        (101, 789, 2, 'Priority-Normal'),
        (103, 789, 3, 'Priority-Low'),
        (199, 789, None, 'Monday'),
        (200, 678, 1, 'Priority-High'),
        (201, 678, 2, 'Priority-Medium'),
        (202, 678, 3, 'Priority-Low'),
        (299, 678, None, 'Hot'),
        ]
    actual = tracker_bizobj.HarmonizeLabelOrStatusRows(def_rows)
    self.assertEqual(
        [(199, None, 'Monday'),
         (299, None, 'Hot'),
         (200, 1, 'Priority-High'),
         (100, 1, 'Priority-High'),
         (101, 2, 'Priority-Normal'),
         (201, 2, 'Priority-Medium'),
         (202, 3, 'Priority-Low'),
         (103, 3, 'Priority-Low')
         ],
        actual)

  def testCombineOrderedLists_Empty(self):
    self.assertEqual([], tracker_bizobj._CombineOrderedLists([]))

  def testCombineOrderedLists_Normal(self):
    a = ['Mon', 'Wed', 'Fri']
    b = ['Mon', 'Tue']
    c = ['Wed', 'Thu']
    self.assertEqual(['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
                     tracker_bizobj._CombineOrderedLists([a, b, c]))

    d = ['Mon', 'StartOfWeek', 'Wed', 'MidWeek', 'Fri', 'EndOfWeek']
    self.assertEqual(['Mon', 'StartOfWeek', 'Tue', 'Wed', 'MidWeek', 'Thu',
                      'Fri', 'EndOfWeek'],
                     tracker_bizobj._CombineOrderedLists([a, b, c, d]))

  def testAccumulateCombinedList_Empty(self):
    combined_items = []
    combined_keys = []
    seen_keys_set = set()
    tracker_bizobj._AccumulateCombinedList(
        [], combined_items, combined_keys, seen_keys_set)
    self.assertEqual([], combined_items)
    self.assertEqual([], combined_keys)
    self.assertEqual(set(), seen_keys_set)

  def testAccumulateCombinedList_Normal(self):
    combined_items = ['a', 'b', 'C']
    combined_keys = ['a', 'b', 'c']  # Keys are always lowercased
    seen_keys_set = set(['a', 'b', 'c'])
    tracker_bizobj._AccumulateCombinedList(
        ['b', 'x', 'C', 'd', 'a'], combined_items, combined_keys, seen_keys_set)
    self.assertEqual(['a', 'b', 'x', 'C', 'd'], combined_items)
    self.assertEqual(['a', 'b', 'x', 'c', 'd'], combined_keys)
    self.assertEqual(set(['a', 'b', 'x', 'c', 'd']), seen_keys_set)

  def testAccumulateCombinedList_NormalWithKeyFunction(self):
    combined_items = ['A', 'B', 'C']
    combined_keys = ['@a', '@b', '@c']
    seen_keys_set = set(['@a', '@b', '@c'])
    tracker_bizobj._AccumulateCombinedList(
        ['B', 'X', 'c', 'D', 'A'], combined_items, combined_keys, seen_keys_set,
        key=lambda s: '@' + s)
    self.assertEqual(['A', 'B', 'X', 'C', 'D'], combined_items)
    self.assertEqual(['@a', '@b', '@x', '@c', '@d'], combined_keys)
    self.assertEqual(set(['@a', '@b', '@x', '@c', '@d']), seen_keys_set)

  def testGetBuiltInQuery(self):
    self.assertEqual(
        'is:open', tracker_bizobj.GetBuiltInQuery(2))
    self.assertEqual(
        '', tracker_bizobj.GetBuiltInQuery(101))

  def testUsersInvolvedInComment(self):
    comment = tracker_pb2.IssueComment()
    self.assertEqual({0}, tracker_bizobj.UsersInvolvedInComment(comment))

    comment.user_id = 111
    self.assertEqual(
        {111}, tracker_bizobj.UsersInvolvedInComment(comment))

    amendment = tracker_pb2.Amendment(newvalue='foo')
    comment.amendments.append(amendment)
    self.assertEqual(
        {111}, tracker_bizobj.UsersInvolvedInComment(comment))

    amendment.added_user_ids.append(222)
    amendment.removed_user_ids.append(333)
    self.assertEqual({111, 222, 333},
                     tracker_bizobj.UsersInvolvedInComment(comment))

  def testUsersInvolvedInCommentList(self):
    self.assertEqual(set(), tracker_bizobj.UsersInvolvedInCommentList([]))

    c1 = tracker_pb2.IssueComment()
    c1.user_id = 111
    c1.amendments.append(tracker_pb2.Amendment(newvalue='foo'))

    c2 = tracker_pb2.IssueComment()
    c2.user_id = 111
    c2.amendments.append(tracker_pb2.Amendment(
        added_user_ids=[222], removed_user_ids=[333]))

    self.assertEqual({111},
                     tracker_bizobj.UsersInvolvedInCommentList([c1]))

    self.assertEqual({111, 222, 333},
                     tracker_bizobj.UsersInvolvedInCommentList([c2]))

    self.assertEqual({111, 222, 333},
                     tracker_bizobj.UsersInvolvedInCommentList([c1, c2]))

  def testUsersInvolvedInIssues_Empty(self):
    self.assertEqual(set(), tracker_bizobj.UsersInvolvedInIssues([]))

  def testUsersInvolvedInIssues_Normal(self):
    av_1 = tracker_pb2.ApprovalValue(approver_ids=[666, 222, 444])
    av_2 = tracker_pb2.ApprovalValue(approver_ids=[777], setter_id=888)
    issue1 = tracker_pb2.Issue(
        reporter_id=111, owner_id=222, cc_ids=[222, 333],
        approval_values=[av_1, av_2])
    issue2 = tracker_pb2.Issue(
        reporter_id=333, owner_id=444, derived_cc_ids=[222, 444])
    issue2.field_values = [tracker_pb2.FieldValue(user_id=555)]
    self.assertEqual(
        set([0, 111, 222, 333, 444, 555, 666, 777, 888]),
        tracker_bizobj.UsersInvolvedInIssues([issue1, issue2]))

  def testUsersInvolvedInTemplate_Empty(self):
    template = tracker_bizobj.MakeIssueTemplate(
        'A report', 'Something went wrong', 'New', None, 'Look out!',
        ['Priority-High'], [], [], [])
    self.assertEqual(set(), tracker_bizobj.UsersInvolvedInTemplate(template))

  def testUsersInvolvedInTempalte_Normal(self):
    template = tracker_bizobj.MakeIssueTemplate(
        'A report', 'Something went wrong', 'New', 111, 'Look out!',
        ['Priority-High'], [], [333, 444], [])
    self.assertEqual(
        set([111, 333, 444]),
        tracker_bizobj.UsersInvolvedInTemplate(template))

  def testUsersInvolvedInConfig_Empty(self):
    """There are no user IDs mentioned in a default config."""
    actual = tracker_bizobj.UsersInvolvedInConfig(self.config)
    self.assertEqual(set(), actual)

  def testUsersInvolvedInConfig_Normal(self):
    """We find user IDs mentioned components, fields, and approvals."""
    self.config.component_defs[0].admin_ids = [111]
    self.config.component_defs[0].cc_ids = [444]
    self.config.field_defs[0].admin_ids = [111, 222]
    approval_def = tracker_pb2.ApprovalDef(
        approval_id=1, approver_ids=[111, 333], survey='')
    self.config.approval_defs = [approval_def]
    actual = tracker_bizobj.UsersInvolvedInConfig(self.config)
    self.assertEqual({111, 222, 333, 444}, actual)

  def testLabelIDsInvolvedInConfig_Empty(self):
    """There are no label IDs mentioned in a default config."""
    actual = tracker_bizobj.LabelIDsInvolvedInConfig(self.config)
    self.assertEqual(set(), actual)

  def testLabelIDsInvolvedInConfig_Normal(self):
    """We find label IDs added by components."""
    self.config.component_defs[0].label_ids = [1, 2, 3]
    actual = tracker_bizobj.LabelIDsInvolvedInConfig(self.config)
    self.assertEqual({1, 2, 3}, actual)

  def testMakeApprovalDelta_AllSpecified(self):
    added_fv = tracker_bizobj.MakeFieldValue(
      1, None, 'added str', None, None, None, False)
    removed_fv = tracker_bizobj.MakeFieldValue(
      1, None, 'removed str', None, None, None, False)
    clear_fvs = [24]
    labels_add = ['ittly-bittly', 'piggly-wiggly']
    labels_remove = ['golly-goops', 'whoopsie']
    actual = tracker_bizobj.MakeApprovalDelta(
        tracker_pb2.ApprovalStatus.APPROVED, 111, [222], [],
        [added_fv], [removed_fv], clear_fvs, labels_add, labels_remove,
        set_on=1234)
    self.assertEqual(actual.status, tracker_pb2.ApprovalStatus.APPROVED)
    self.assertEqual(actual.setter_id, 111)
    self.assertEqual(actual.set_on, 1234)
    self.assertEqual(actual.subfield_vals_add, [added_fv])
    self.assertEqual(actual.subfield_vals_remove, [removed_fv])
    self.assertEqual(actual.subfields_clear, clear_fvs)
    self.assertEqual(actual.labels_add, labels_add)
    self.assertEqual(actual.labels_remove, labels_remove)

  def testMakeApprovalDelta_WithNones(self):
    added_fv = tracker_bizobj.MakeFieldValue(
      1, None, 'added str', None, None, None, False)
    removed_fv = tracker_bizobj.MakeFieldValue(
      1, None, 'removed str', None, None, None, False)
    clear_fields = [2]
    labels_add = ['ittly-bittly', 'piggly-wiggly']
    labels_remove = ['golly-goops', 'whoopsie']
    actual = tracker_bizobj.MakeApprovalDelta(
        None, 111, [222], [],
        [added_fv], [removed_fv], clear_fields,
        labels_add, labels_remove)
    self.assertIsNone(actual.status)
    self.assertIsNone(actual.setter_id)
    self.assertIsNone(actual.set_on)

  def testMakeIssueDelta_AllSpecified(self):
    added_fv = tracker_bizobj.MakeFieldValue(
      1, None, 'added str', None, None, None, False)
    removed_fv = tracker_bizobj.MakeFieldValue(
      1, None, 'removed str', None, None, None, False)
    actual = tracker_bizobj.MakeIssueDelta(
      'New', 111, [222], [333], [1], [2],
      ['AddedLabel'], ['RemovedLabel'], [added_fv], [removed_fv],
      [3], [78901], [78902], [78903], [78904], 78905,
      'New summary',
      ext_blocked_on_add=['b/123', 'b/234'],
      ext_blocked_on_remove=['b/345', 'b/456'],
      ext_blocking_add=['b/567', 'b/678'],
      ext_blocking_remove=['b/789', 'b/890'])
    self.assertEqual('New', actual.status)
    self.assertEqual(111, actual.owner_id)
    self.assertEqual([222], actual.cc_ids_add)
    self.assertEqual([333], actual.cc_ids_remove)
    self.assertEqual([1], actual.comp_ids_add)
    self.assertEqual([2], actual.comp_ids_remove)
    self.assertEqual(['AddedLabel'], actual.labels_add)
    self.assertEqual(['RemovedLabel'], actual.labels_remove)
    self.assertEqual([added_fv], actual.field_vals_add)
    self.assertEqual([removed_fv], actual.field_vals_remove)
    self.assertEqual([3], actual.fields_clear)
    self.assertEqual([78901], actual.blocked_on_add)
    self.assertEqual([78902], actual.blocked_on_remove)
    self.assertEqual([78903], actual.blocking_add)
    self.assertEqual([78904], actual.blocking_remove)
    self.assertEqual(78905, actual.merged_into)
    self.assertEqual('New summary', actual.summary)
    self.assertEqual(['b/123', 'b/234'], actual.ext_blocked_on_add)
    self.assertEqual(['b/345', 'b/456'], actual.ext_blocked_on_remove)
    self.assertEqual(['b/567', 'b/678'], actual.ext_blocking_add)
    self.assertEqual(['b/789', 'b/890'], actual.ext_blocking_remove)

  def testMakeIssueDelta_WithNones(self):
    """None for status, owner_id, or summary does not set a value."""
    actual = tracker_bizobj.MakeIssueDelta(
      None, None, [], [], [], [],
      [], [], [], [],
      [], [], [], [], [], None,
      None)
    self.assertIsNone(actual.status)
    self.assertIsNone(actual.owner_id)
    self.assertIsNone(actual.merged_into)
    self.assertIsNone(actual.summary)

  def testApplyLabelChanges_RemoveAndAdd(self):
    issue = tracker_pb2.Issue(labels=['tobe-removed', 'tobe-notremoved'])
    amendment = tracker_bizobj.ApplyLabelChanges(
        issue, self.config, [u'tobe-added'], [u'tobe-removed'])
    self.assertEqual(amendment, tracker_bizobj.MakeLabelsAmendment(
        ['tobe-added'], ['tobe-removed']))

  def testApplyLabelChanges_RemoveInvalidLabel(self):
    issue = tracker_pb2.Issue(labels=[])
    amendment = tracker_bizobj.ApplyLabelChanges(
        issue, self.config, [], [u'lost-car'])
    self.assertIsNone(amendment)

  def testApplyLabelChanges_NoChangesAfterMerge(self):
    issue = tracker_pb2.Issue(labels=['lost-car'])
    amendment = tracker_bizobj.ApplyLabelChanges(
        issue, self.config, [u'lost-car'], [])
    self.assertIsNone(amendment)

  def testApplyLabelChanges_Empty(self):
    issue = tracker_pb2.Issue(labels=[])
    amendment = tracker_bizobj.ApplyLabelChanges(issue, self.config, [], [])
    self.assertIsNone(amendment)

  def testApplyFieldValueChanges(self):
    self.config.field_defs = [
        tracker_pb2.FieldDef(
            field_id=1, project_id=789, field_name='EstDays',
            field_type=tracker_pb2.FieldTypes.INT_TYPE),
        tracker_pb2.FieldDef(
            field_id=2, project_id=789, field_name='SleepHrs',
            field_type=tracker_pb2.FieldTypes.INT_TYPE, is_phase_field=True),
        tracker_pb2.FieldDef(
            field_id=3, project_id=789, field_name='Chickens',
            field_type=tracker_pb2.FieldTypes.STR_TYPE, is_phase_field=True,
            is_multivalued=True),
    ]
    original_keep = [
        tracker_pb2.FieldValue(field_id=3, str_value='bok', phase_id=45)]
    original_replace = [
        tracker_pb2.FieldValue(field_id=1, int_value=72),
        tracker_pb2.FieldValue(field_id=2, int_value=88, phase_id=44),
    ]
    issue = tracker_pb2.Issue(
        phases=[
            tracker_pb2.Phase(phase_id=45, name='high-school'),
            tracker_pb2.Phase(phase_id=44, name='college')])
    issue.field_values = original_keep + original_replace

    fvs_add_ignore = [
        tracker_pb2.FieldValue(field_id=3, str_value='egg', phase_id=42)]
    fvs_add = [
        tracker_pb2.FieldValue(field_id=1, int_value=73),  # replace
        tracker_pb2.FieldValue(field_id=2, int_value=99, phase_id=44),  #replace
        tracker_pb2.FieldValue(field_id=2, int_value=100, phase_id=45),  # added
        # added
        tracker_pb2.FieldValue(field_id=3, str_value='rooster', phase_id=45),
    ]
    fvs_remove = []
    fields_clear = []
    amendments = tracker_bizobj.ApplyFieldValueChanges(
        issue, self.config, fvs_add+fvs_add_ignore, fvs_remove, fields_clear)

    self.assertEqual(
        amendments,
        [tracker_bizobj.MakeFieldAmendment(1, self.config, [73]),
         tracker_bizobj.MakeFieldAmendment(
             2, self.config, [99], phase_name='college'),
         tracker_bizobj.MakeFieldAmendment(
             2, self.config, [100], phase_name='high-school'),
         tracker_bizobj.MakeFieldAmendment(
             3, self.config, ['rooster'], phase_name='high-school')])
    self.assertEqual(issue.field_values, original_keep + fvs_add)

  def testApplyIssueDelta_NoChange(self):
    """A delta with no change should change nothing."""
    issue = tracker_pb2.Issue(
        status='New', owner_id=111, cc_ids=[222], labels=['a', 'b'],
        component_ids=[1], blocked_on_iids=[78902], blocking_iids=[78903],
        merged_into=78904, summary='Sum')
    delta = tracker_pb2.IssueDelta()

    amendments, impacted_iids = tracker_bizobj.ApplyIssueDelta(
        self.cnxn, self.services.issue, issue, delta, self.config)

    self.assertEqual('New', issue.status)
    self.assertEqual(111, issue.owner_id)
    self.assertEqual([222], issue.cc_ids)
    self.assertEqual(['a', 'b'], issue.labels)
    self.assertEqual([1], issue.component_ids)
    self.assertEqual([78902], issue.blocked_on_iids)
    self.assertEqual([78903], issue.blocking_iids)
    self.assertEqual(78904, issue.merged_into)
    self.assertEqual('Sum', issue.summary)

    self.assertEqual(0, len(amendments))
    self.assertEqual(0, len(impacted_iids))

  def testApplyIssueDelta_BuiltInFields(self):
    """A delta can change built-in fields."""
    ref_issue_70 = fake.MakeTestIssue(
        789, 70, 'Something that must be done before', 'New', 111)
    self.services.issue.TestAddIssue(ref_issue_70)
    ref_issue_71 = fake.MakeTestIssue(
        789, 71, 'Something that can only be done after', 'New', 111)
    self.services.issue.TestAddIssue(ref_issue_71)
    ref_issue_72 = fake.MakeTestIssue(
        789, 72, 'Something that seems the same', 'New', 111)
    self.services.issue.TestAddIssue(ref_issue_72)
    ref_issue_73 = fake.MakeTestIssue(
        789, 73, 'Something that used to seem the same', 'New', 111)
    self.services.issue.TestAddIssue(ref_issue_73)
    issue = tracker_pb2.Issue(
        status='New', owner_id=111, cc_ids=[222], labels=['a', 'b'],
        component_ids=[1], blocked_on_iids=[78902], blocking_iids=[78903],
        merged_into=ref_issue_73.issue_id, summary='Sum')
    delta = tracker_pb2.IssueDelta(
      status='Duplicate', owner_id=999, cc_ids_add=[333, 444],
      comp_ids_add=[2], labels_add=['c', 'd'],
      blocked_on_add=[ref_issue_70.issue_id],
      blocking_add=[ref_issue_71.issue_id],
      merged_into=ref_issue_72.issue_id, summary='New summary')

    actual_amendments, actual_impacted_iids = tracker_bizobj.ApplyIssueDelta(
        self.cnxn, self.services.issue, issue, delta, self.config)

    self.assertEqual('Duplicate', issue.status)
    self.assertEqual(999, issue.owner_id)
    self.assertEqual([222, 333, 444], issue.cc_ids)
    self.assertEqual([1, 2], issue.component_ids)
    self.assertEqual(['a', 'b', 'c', 'd'], issue.labels)
    self.assertEqual([78902, ref_issue_70.issue_id], issue.blocked_on_iids)
    self.assertEqual([78903, ref_issue_71.issue_id], issue.blocking_iids)
    self.assertEqual(ref_issue_72.issue_id, issue.merged_into)
    self.assertEqual('New summary', issue.summary)

    self.assertEqual(
      [tracker_bizobj.MakeStatusAmendment('Duplicate', 'New'),
       tracker_bizobj.MakeOwnerAmendment(999, 111),
       tracker_bizobj.MakeCcAmendment([333, 444], []),
       tracker_bizobj.MakeComponentsAmendment([2], [], self.config),
       tracker_bizobj.MakeLabelsAmendment(['c', 'd'], []),
       tracker_bizobj.MakeBlockedOnAmendment([(None, 70)], []),
       tracker_bizobj.MakeBlockingAmendment([(None, 71)], []),
       tracker_bizobj.MakeMergedIntoAmendment((None, 72), (None, 73)),
       tracker_bizobj.MakeSummaryAmendment('New summary', 'Sum'),
       ],
      actual_amendments)
    self.assertEqual(
      set([ref_issue_70.issue_id, ref_issue_71.issue_id,
           ref_issue_72.issue_id, ref_issue_73.issue_id]),
      actual_impacted_iids)

  def testApplyIssueDelta_ReferrencedIssueNotFound(self):
    """This part of the code copes with missing issues."""
    issue = tracker_pb2.Issue(
        status='New', owner_id=111, cc_ids=[222], labels=['a', 'b'],
        component_ids=[1], blocked_on_iids=[78902], blocking_iids=[78903],
        merged_into=78904, summary='Sum')
    delta = tracker_pb2.IssueDelta(
      blocked_on_add=[78905], blocked_on_remove=[78902],
      blocking_add=[78906], blocking_remove=[78903],
      merged_into=78907)

    actual_amendments, actual_impacted_iids = tracker_bizobj.ApplyIssueDelta(
        self.cnxn, self.services.issue, issue, delta, self.config)

    self.assertEqual([78905], issue.blocked_on_iids)
    self.assertEqual([78906], issue.blocking_iids)
    self.assertEqual(78907, issue.merged_into)

    self.assertEqual(
      [tracker_bizobj.MakeBlockedOnAmendment([], []),
       tracker_bizobj.MakeBlockingAmendment([], []),
       tracker_bizobj.MakeMergedIntoAmendment(None, None),
       ],
      actual_amendments)
    self.assertEqual(
      set([78902, 78903, 78905, 78906]),
      actual_impacted_iids)

  def testApplyIssueDelta_CustomPhaseFields(self):
    """A delta can add, remove, or clear custom phase fields."""
    fd_a = tracker_pb2.FieldDef(
        field_id=1, project_id=789, field_name='a',
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        is_multivalued=True, is_phase_field=True)
    fd_b = tracker_pb2.FieldDef(
        field_id=2, project_id=789, field_name='b',
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        is_phase_field=True)
    fd_c = tracker_pb2.FieldDef(
        field_id=3, project_id=789, field_name='c',
        field_type=tracker_pb2.FieldTypes.INT_TYPE, is_phase_field=True)
    self.config.field_defs = [fd_a, fd_b, fd_c]
    fv_a1_p1 = tracker_pb2.FieldValue(
        field_id=1, int_value=1, phase_id=1)  # fv
    fv_a2_p1 = tracker_pb2.FieldValue(
        field_id=1, int_value=2, phase_id=1)  # add
    fv_a3_p1 = tracker_pb2.FieldValue(
        field_id=1, int_value=3, phase_id=1)  # add
    fv_b1_p1 = tracker_pb2.FieldValue(
        field_id=2, int_value=1, phase_id=1)  # add
    fv_c2_p1 = tracker_pb2.FieldValue(
        field_id=3, int_value=2, phase_id=1)  # clear

    fv_a2_p2 = tracker_pb2.FieldValue(
        field_id=1, int_value=2, phase_id=2)  # add
    fv_b1_p2 = tracker_pb2.FieldValue(
        field_id=2, int_value=1, phase_id=2)  # fv remove
    fv_c1_p2 = tracker_pb2.FieldValue(
        field_id=3, int_value=1, phase_id=2)  # clear

    issue = tracker_pb2.Issue(
        status='New', owner_id=111, summary='Sum',
        field_values=[fv_a1_p1, fv_c2_p1, fv_b1_p2, fv_c1_p2])
    issue.phases = [
        tracker_pb2.Phase(phase_id=1, name='Phase-1'),
        tracker_pb2.Phase(phase_id=2, name='Phase-2')]

    delta = tracker_pb2.IssueDelta(
        field_vals_add=[fv_a2_p1, fv_a3_p1, fv_b1_p1, fv_a2_p2],
        field_vals_remove=[fv_b1_p2], fields_clear=[3])

    actual_amendments, actual_impacted_iids = tracker_bizobj.ApplyIssueDelta(
        self.cnxn, self.services.issue, issue, delta, self.config)
    self.assertEqual(
      [tracker_bizobj.MakeFieldAmendment(
          1, self.config, ['2', '3'], [], phase_name='Phase-1'),
       tracker_bizobj.MakeFieldAmendment(
           1, self.config, ['2'], [], phase_name='Phase-2'),
       tracker_bizobj.MakeFieldAmendment(
           2, self.config, ['1'], [], phase_name='Phase-1'),
       tracker_bizobj.MakeFieldAmendment(
           2, self.config, [], ['1'], phase_name='Phase-2'),
       tracker_bizobj.MakeFieldClearedAmendment(3, self.config)],
      actual_amendments)
    self.assertEqual(set(), actual_impacted_iids)

  def testApplyIssueDelta_CustomFields(self):
    """A delta can add, remove, or clear custom fields."""
    fd_a = tracker_pb2.FieldDef(
        field_id=1, project_id=789, field_name='a',
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        is_multivalued=True)
    fd_b = tracker_pb2.FieldDef(
        field_id=2, project_id=789, field_name='b',
        field_type=tracker_pb2.FieldTypes.INT_TYPE)
    fd_c = tracker_pb2.FieldDef(
        field_id=3, project_id=789, field_name='c',
        field_type=tracker_pb2.FieldTypes.INT_TYPE)
    fd_d = tracker_pb2.FieldDef(
        field_id=4, project_id=789, field_name='d',
        field_type=tracker_pb2.FieldTypes.ENUM_TYPE)
    self.config.field_defs = [fd_a, fd_b, fd_c, fd_d]
    fv_a1 = tracker_pb2.FieldValue(field_id=1, int_value=1)
    fv_a2 = tracker_pb2.FieldValue(field_id=1, int_value=2)
    fv_b1 = tracker_pb2.FieldValue(field_id=2, int_value=1)
    fv_c1 = tracker_pb2.FieldValue(field_id=3, int_value=1)
    issue = tracker_pb2.Issue(
        status='New', owner_id=111, labels=['d-val', 'Hot'], summary='Sum',
        field_values=[fv_a1, fv_b1, fv_c1])
    delta = tracker_pb2.IssueDelta(
      field_vals_add=[fv_a2], field_vals_remove=[fv_b1], fields_clear=[3, 4])

    actual_amendments, actual_impacted_iids = tracker_bizobj.ApplyIssueDelta(
        self.cnxn, self.services.issue, issue, delta, self.config)

    self.assertEqual([fv_a1, fv_a2], issue.field_values)
    self.assertEqual(['Hot'], issue.labels)

    self.assertEqual(
      [tracker_bizobj.MakeFieldAmendment(1, self.config, ['2'], []),
       tracker_bizobj.MakeFieldAmendment(2, self.config, [], ['1']),
       tracker_bizobj.MakeFieldClearedAmendment(3, self.config),
       tracker_bizobj.MakeFieldClearedAmendment(4, self.config),
       ],
      actual_amendments)
    self.assertEqual(set(), actual_impacted_iids)

  def testApplyIssueDelta_ExternalRefs(self):
    """Only applies valid issue refs from a delta."""
    issue = tracker_pb2.Issue(
        status='New', owner_id=111, cc_ids=[222], labels=['a', 'b'],
        component_ids=[1], blocked_on_iids=[78902], blocking_iids=[78903],
        merged_into=78904, summary='Sum',
        dangling_blocked_on_refs=[
          tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/345'),
          tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/111')],
        dangling_blocking_refs=[
          tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/789'),
          tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/222')])
    delta = tracker_pb2.IssueDelta(
        # Add one valid, one invalid, and another valid.
        ext_blocked_on_add=['b/123', 'b123', 'b/234'],
        # Remove one valid, one invalid, and one that does not exist.
        ext_blocked_on_remove=['b/345', 'b', 'b/456'],
        # Add one valid, one invalid, and another valid.
        ext_blocking_add=['b/567', 'b//123', 'b/678'],
        # Remove one valid, one invalid, and one that does not exist.
        ext_blocking_remove=['b/789', 'b/123/123', 'b/890'])

    amendments, impacted_iids = tracker_bizobj.ApplyIssueDelta(
        self.cnxn, self.services.issue, issue, delta, self.config)

    # Test amendments.
    self.assertEqual(2, len(amendments))
    self.assertEqual(tracker_pb2.FieldID.BLOCKEDON, amendments[0].field)
    self.assertEqual('-b/345 -b/456 b/123 b/234', amendments[0].newvalue)
    self.assertEqual(tracker_pb2.FieldID.BLOCKING, amendments[1].field)
    self.assertEqual('-b/789 -b/890 b/567 b/678', amendments[1].newvalue)

    self.assertEqual(0, len(impacted_iids))

    # Issue refs are applied correctly and alphabetized.
    self.assertEqual([
          tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/111'),
          tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/123'),
          tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/234'),
        ], issue.dangling_blocked_on_refs)
    self.assertEqual([
          tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/222'),
          tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/567'),
          tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/678'),
        ], issue.dangling_blocking_refs)

  def testApplyIssueDelta_MergedIntoExternal(self):
    """ApplyIssueDelta applies valid mergedinto refs."""
    issue = tracker_pb2.Issue(status='New', owner_id=111)
    delta = tracker_pb2.IssueDelta(merged_into_external='b/5678')
    amendments, impacted_iids = tracker_bizobj.ApplyIssueDelta(
        self.cnxn, self.services.issue, issue, delta, self.config)

    # Test amendments.
    self.assertEqual(1, len(amendments))
    self.assertEqual(tracker_pb2.FieldID.MERGEDINTO, amendments[0].field)
    self.assertEqual('b/5678', amendments[0].newvalue)

    self.assertEqual(0, len(impacted_iids))

    # Issue refs are applied correctly and alphabetized.
    self.assertEqual('b/5678', issue.merged_into_external)

  def testApplyIssueDelta_MergedIntoExternalInvalid(self):
    """ApplyIssueDelta does not accept invalid mergedinto refs."""
    issue = tracker_pb2.Issue(status='New', owner_id=111)
    delta = tracker_pb2.IssueDelta(merged_into_external='a/5678')
    amendments, impacted_iids = tracker_bizobj.ApplyIssueDelta(
        self.cnxn, self.services.issue, issue, delta, self.config)

    # No change.
    self.assertEqual(0, len(amendments))
    self.assertEqual(0, len(impacted_iids))
    self.assertEqual(None, issue.merged_into_external)

  def testApplyIssueDelta_MergedIntoFromInternalToExternal(self):
    """ApplyIssueDelta updates from an internal to an external ref."""
    self.services.issue.TestAddIssue(fake.MakeTestIssue(1, 2, 'Summary',
        'New', 111, issue_id=6789))
    issue = tracker_pb2.Issue(status='New', owner_id=111, merged_into=6789)
    delta = tracker_pb2.IssueDelta(merged_into_external='b/5678')
    amendments, impacted_iids = tracker_bizobj.ApplyIssueDelta(
        self.cnxn, self.services.issue, issue, delta, self.config)

    # Test amendments.
    self.assertEqual(1, len(amendments))
    self.assertEqual(tracker_pb2.FieldID.MERGEDINTO, amendments[0].field)
    self.assertEqual('-2 b/5678', amendments[0].newvalue)
    self.assertEqual(set([6789]), impacted_iids)
    self.assertEqual(0, issue.merged_into)
    self.assertEqual('b/5678', issue.merged_into_external)

  def testApplyIssueDelta_MergedIntoFromExternalToInternal(self):
    """ApplyIssueDelta updates from an external to an internalref."""
    self.services.issue.TestAddIssue(fake.MakeTestIssue(1, 2, 'Summary',
        'New', 111, issue_id=6789))
    issue = tracker_pb2.Issue(status='New', owner_id=111,
        merged_into_external='b/5678')
    delta = tracker_pb2.IssueDelta(merged_into=6789)
    amendments, impacted_iids = tracker_bizobj.ApplyIssueDelta(
        self.cnxn, self.services.issue, issue, delta, self.config)

    # Test amendments.
    self.assertEqual(1, len(amendments))
    self.assertEqual(tracker_pb2.FieldID.MERGEDINTO, amendments[0].field)
    self.assertEqual('-b/5678 2', amendments[0].newvalue)
    self.assertEqual(set([6789]), impacted_iids)
    self.assertEqual(6789, issue.merged_into)
    self.assertEqual(None, issue.merged_into_external)

  def testApplyIssueDelta_NoMergedIntoInternalAndExternal(self):
    """ApplyIssueDelta does not allow updating the internal and external
    merged_into fields at the same time.
    """
    issue = tracker_pb2.Issue(status='New', owner_id=111, merged_into=321)
    delta = tracker_pb2.IssueDelta(merged_into=543,
        merged_into_external='b/5678')
    with self.assertRaises(ValueError):
      tracker_bizobj.ApplyIssueDelta(self.cnxn, self.services.issue, issue,
          delta, self.config)

  def testMakeAmendment(self):
    amendment = tracker_bizobj.MakeAmendment(
        tracker_pb2.FieldID.STATUS, 'new', [111], [222])
    self.assertEqual(tracker_pb2.FieldID.STATUS, amendment.field)
    self.assertEqual('new', amendment.newvalue)
    self.assertEqual([111], amendment.added_user_ids)
    self.assertEqual([222], amendment.removed_user_ids)

  def testPlusMinusString(self):
    self.assertEqual('', tracker_bizobj._PlusMinusString([], []))
    self.assertEqual('-a -b c d',
                     tracker_bizobj._PlusMinusString(['c', 'd'], ['a', 'b']))

  def testPlusMinusAmendment(self):
    amendment = tracker_bizobj._PlusMinusAmendment(
        tracker_pb2.FieldID.STATUS, ['add1', 'add2'], ['remove1'])
    self.assertEqual(tracker_pb2.FieldID.STATUS, amendment.field)
    self.assertEqual('-remove1 add1 add2', amendment.newvalue)

  def testPlusMinusRefsAmendment(self):
    ref1 = (None, 1)
    ref2 = ('other-proj', 2)
    amendment = tracker_bizobj._PlusMinusRefsAmendment(
        tracker_pb2.FieldID.STATUS, [ref1], [ref2])
    self.assertEqual(tracker_pb2.FieldID.STATUS, amendment.field)
    self.assertEqual('-other-proj:2 1', amendment.newvalue)

  def testMakeSummaryAmendment(self):
    amendment = tracker_bizobj.MakeSummaryAmendment('', None)
    self.assertEqual(tracker_pb2.FieldID.SUMMARY, amendment.field)
    self.assertEqual('', amendment.newvalue)
    self.assertEqual(None, amendment.oldvalue)

    amendment = tracker_bizobj.MakeSummaryAmendment('new summary', '')
    self.assertEqual(tracker_pb2.FieldID.SUMMARY, amendment.field)
    self.assertEqual('new summary', amendment.newvalue)
    self.assertEqual('', amendment.oldvalue)

  def testMakeStatusAmendment(self):
    amendment = tracker_bizobj.MakeStatusAmendment('', None)
    self.assertEqual(tracker_pb2.FieldID.STATUS, amendment.field)
    self.assertEqual('', amendment.newvalue)
    self.assertEqual(None, amendment.oldvalue)

    amendment = tracker_bizobj.MakeStatusAmendment('New', '')
    self.assertEqual(tracker_pb2.FieldID.STATUS, amendment.field)
    self.assertEqual('New', amendment.newvalue)
    self.assertEqual('', amendment.oldvalue)

  def testMakeOwnerAmendment(self):
    amendment = tracker_bizobj.MakeOwnerAmendment(111, 0)
    self.assertEqual(tracker_pb2.FieldID.OWNER, amendment.field)
    self.assertEqual('', amendment.newvalue)
    self.assertEqual([111], amendment.added_user_ids)
    self.assertEqual([0], amendment.removed_user_ids)

  def testMakeCcAmendment(self):
    amendment = tracker_bizobj.MakeCcAmendment([111], [222])
    self.assertEqual(tracker_pb2.FieldID.CC, amendment.field)
    self.assertEqual('', amendment.newvalue)
    self.assertEqual([111], amendment.added_user_ids)
    self.assertEqual([222], amendment.removed_user_ids)

  def testMakeLabelsAmendment(self):
    amendment = tracker_bizobj.MakeLabelsAmendment(['added1'], ['removed1'])
    self.assertEqual(tracker_pb2.FieldID.LABELS, amendment.field)
    self.assertEqual('-removed1 added1', amendment.newvalue)

  def testDiffValueLists(self):
    added, removed = tracker_bizobj.DiffValueLists([], [])
    self.assertItemsEqual([], added)
    self.assertItemsEqual([], removed)

    added, removed = tracker_bizobj.DiffValueLists([], None)
    self.assertItemsEqual([], added)
    self.assertItemsEqual([], removed)

    added, removed = tracker_bizobj.DiffValueLists([1, 2], [])
    self.assertItemsEqual([1, 2], added)
    self.assertItemsEqual([], removed)

    added, removed = tracker_bizobj.DiffValueLists([], [8, 9])
    self.assertItemsEqual([], added)
    self.assertItemsEqual([8, 9], removed)

    added, removed = tracker_bizobj.DiffValueLists([1, 2], [8, 9])
    self.assertItemsEqual([1, 2], added)
    self.assertItemsEqual([8, 9], removed)

    added, removed = tracker_bizobj.DiffValueLists([1, 2, 5, 6], [5, 6, 8, 9])
    self.assertItemsEqual([1, 2], added)
    self.assertItemsEqual([8, 9], removed)

    added, removed = tracker_bizobj.DiffValueLists([5, 6], [5, 6, 8, 9])
    self.assertItemsEqual([], added)
    self.assertItemsEqual([8, 9], removed)

    added, removed = tracker_bizobj.DiffValueLists([1, 2, 5, 6], [5, 6])
    self.assertItemsEqual([1, 2], added)
    self.assertItemsEqual([], removed)

    added, removed = tracker_bizobj.DiffValueLists(
        [1, 2, 2, 5, 6], [5, 6, 8, 9])
    self.assertItemsEqual([1, 2, 2], added)
    self.assertItemsEqual([8, 9], removed)

    added, removed = tracker_bizobj.DiffValueLists(
        [1, 2, 5, 6], [5, 6, 8, 8, 9])
    self.assertItemsEqual([1, 2], added)
    self.assertItemsEqual([8, 8, 9], removed)

  def testMakeFieldAmendment_NoSuchFieldDef(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    with self.assertRaises(ValueError):
      tracker_bizobj.MakeFieldAmendment(1, config, ['Large'], ['Small'])

  def testMakeFieldAmendment_MultiValued(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(
        field_id=1, field_name='Days', is_multivalued=True)
    config.field_defs.append(fd)
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '-Mon Tue Wed', [], [], 'Days'),
        tracker_bizobj.MakeFieldAmendment(1, config, ['Tue', 'Wed'], ['Mon']))
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '-Mon', [], [], 'Days'),
        tracker_bizobj.MakeFieldAmendment(1, config, [], ['Mon']))

  def testMakeFieldAmendment_MultiValuedUser(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(
        field_id=1, field_name='Friends', is_multivalued=True,
        field_type=tracker_pb2.FieldTypes.USER_TYPE)
    config.field_defs.append(fd)
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '', [111], [222], 'Friends'),
        tracker_bizobj.MakeFieldAmendment(1, config, [111], [222]))
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '', [], [222], 'Friends'),
        tracker_bizobj.MakeFieldAmendment(1, config, [], [222]))

  def testMakeFieldAmendment_SingleValued(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(field_id=1, field_name='Size')
    config.field_defs.append(fd)
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, 'Large', [], [], 'Size'),
        tracker_bizobj.MakeFieldAmendment(1, config, ['Large'], ['Small']))
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '----', [], [], 'Size'),
        tracker_bizobj.MakeFieldAmendment(1, config, [], ['Small']))

  def testMakeFieldAmendment_SingleValuedUser(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(
        field_id=1, field_name='Friend',
        field_type=tracker_pb2.FieldTypes.USER_TYPE)
    config.field_defs.append(fd)
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '', [111], [], 'Friend'),
        tracker_bizobj.MakeFieldAmendment(1, config, [111], [222]))
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '', [], [], 'Friend'),
        tracker_bizobj.MakeFieldAmendment(1, config, [], [222]))

  def testMakeFieldAmendment_PhaseField(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(
        field_id=1, field_name='Friend',
        field_type=tracker_pb2.FieldTypes.USER_TYPE, is_phase_field=True)
    config.field_defs.append(fd)
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '', [111], [], 'PhaseName-Friend'),
        tracker_bizobj.MakeFieldAmendment(
            1, config, [111], [222], phase_name='PhaseName'))
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '', [], [], 'PhaseName-3-Friend'),
        tracker_bizobj.MakeFieldAmendment(
            1, config, [], [222], phase_name='PhaseName-3'))

  def testMakeFieldClearedAmendment_FieldNotFound(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    with self.assertRaises(ValueError):
      tracker_bizobj.MakeFieldClearedAmendment(1, config)

  def testMakeFieldClearedAmendment_Normal(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(field_id=1, field_name='Rabbit')
    config.field_defs.append(fd)
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '----', [], [], 'Rabbit'),
        tracker_bizobj.MakeFieldClearedAmendment(1, config))

  def testMakeApprovalStructureAmendment(self):
    actual_amendment = tracker_bizobj.MakeApprovalStructureAmendment(
        ['Chicken1', 'Chicken', 'Llama'], ['Cow', 'Chicken2', 'Llama'])
    amendment = tracker_bizobj.MakeAmendment(
        tracker_pb2.FieldID.CUSTOM, '-Cow -Chicken2 Chicken1 Chicken',
        [], [], 'Approvals')
    self.assertEqual(amendment, actual_amendment)

  def testMakeApprovalStatusAmendment(self):
    actual_amendment = tracker_bizobj.MakeApprovalStatusAmendment(
        tracker_pb2.ApprovalStatus.APPROVED)
    amendment = tracker_pb2.Amendment(
        field=tracker_pb2.FieldID.CUSTOM, newvalue='approved',
        custom_field_name='Status')
    self.assertEqual(amendment, actual_amendment)

  def testMakeApprovalApproversAmendment(self):
    actual_amendment = tracker_bizobj.MakeApprovalApproversAmendment(
        [222], [333])
    amendment = tracker_pb2.Amendment(
        field=tracker_pb2.FieldID.CUSTOM, newvalue='', added_user_ids=[222],
        removed_user_ids=[333], custom_field_name='Approvers')
    self.assertEqual(actual_amendment, amendment)

  def testMakeComponentsAmendment_NoChange(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs = [
        tracker_pb2.ComponentDef(component_id=1, path='UI'),
        tracker_pb2.ComponentDef(component_id=2, path='DB')]
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.COMPONENTS, '', [], []),
        tracker_bizobj.MakeComponentsAmendment([], [], config))

  def testMakeComponentsAmendment_NotFound(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs = [
        tracker_pb2.ComponentDef(component_id=1, path='UI'),
        tracker_pb2.ComponentDef(component_id=2, path='DB')]
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.COMPONENTS, '', [], []),
        tracker_bizobj.MakeComponentsAmendment([99], [999], config))

  def testMakeComponentsAmendment_Normal(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.component_defs = [
        tracker_pb2.ComponentDef(component_id=1, path='UI'),
        tracker_pb2.ComponentDef(component_id=2, path='DB')]
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.COMPONENTS, '-UI DB', [], []),
        tracker_bizobj.MakeComponentsAmendment([2], [1], config))

  def testMakeBlockedOnAmendment(self):
    ref1 = (None, 1)
    ref2 = ('other-proj', 2)
    amendment = tracker_bizobj.MakeBlockedOnAmendment([ref1], [ref2])
    self.assertEqual(tracker_pb2.FieldID.BLOCKEDON, amendment.field)
    self.assertEqual('-other-proj:2 1', amendment.newvalue)

    amendment = tracker_bizobj.MakeBlockedOnAmendment([ref2], [ref1])
    self.assertEqual(tracker_pb2.FieldID.BLOCKEDON, amendment.field)
    self.assertEqual('-1 other-proj:2', amendment.newvalue)

  def testMakeBlockingAmendment(self):
    ref1 = (None, 1)
    ref2 = ('other-proj', 2)
    amendment = tracker_bizobj.MakeBlockingAmendment([ref1], [ref2])
    self.assertEqual(tracker_pb2.FieldID.BLOCKING, amendment.field)
    self.assertEqual('-other-proj:2 1', amendment.newvalue)

  def testMakeMergedIntoAmendment(self):
    ref1 = (None, 1)
    ref2 = ('other-proj', 2)
    amendment = tracker_bizobj.MakeMergedIntoAmendment(ref1, ref2)
    self.assertEqual(tracker_pb2.FieldID.MERGEDINTO, amendment.field)
    self.assertEqual('-other-proj:2 1', amendment.newvalue)

  def testMakeProjectAmendment(self):
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.PROJECT, 'moonshot', [], []),
        tracker_bizobj.MakeProjectAmendment('moonshot'))

  def testAmendmentString(self):
    users_by_id = {
        111: framework_views.StuffUserView(111, 'username@gmail.com', True),
        framework_constants.DELETED_USER_ID: framework_views.StuffUserView(
            framework_constants.DELETED_USER_ID, '', True),
    }
    summary_amendment = tracker_bizobj.MakeSummaryAmendment('new summary', None)
    self.assertEqual(
        'new summary',
        tracker_bizobj.AmendmentString(summary_amendment, users_by_id))

    status_amendment = tracker_bizobj.MakeStatusAmendment('', None)
    self.assertEqual(
        '', tracker_bizobj.AmendmentString(status_amendment, users_by_id))
    status_amendment = tracker_bizobj.MakeStatusAmendment('Assigned', 'New')
    self.assertEqual(
        'Assigned',
        tracker_bizobj.AmendmentString(status_amendment, users_by_id))

    owner_amendment = tracker_bizobj.MakeOwnerAmendment(0, 0)
    self.assertEqual(
        '----', tracker_bizobj.AmendmentString(owner_amendment, users_by_id))
    owner_amendment = tracker_bizobj.MakeOwnerAmendment(111, 0)
    self.assertEqual(
        'usern...@gmail.com',
        tracker_bizobj.AmendmentString(owner_amendment, users_by_id))

    owner_amendment_deleted = tracker_bizobj.MakeOwnerAmendment(1, 0)
    self.assertEqual(
        framework_constants.DELETED_USER_NAME,
        tracker_bizobj.AmendmentString(owner_amendment_deleted, users_by_id))

  def testAmendmentLinks(self):
    users_by_id = {
        111: framework_views.StuffUserView(111, 'foo@gmail.com', False),
        222: framework_views.StuffUserView(222, 'bar@gmail.com', False),
        333: framework_views.StuffUserView(333, 'baz@gmail.com', False),
        framework_constants.DELETED_USER_ID: framework_views.StuffUserView(
            framework_constants.DELETED_USER_ID, '', True),
        }
    # SUMMARY
    summary_amendment = tracker_bizobj.MakeSummaryAmendment('new summary', None)
    self.assertEqual(
        [{'value': 'new summary', 'url': None}],
        tracker_bizobj.AmendmentLinks(summary_amendment, users_by_id, 'proj'))

    summary_amendment = tracker_bizobj.MakeSummaryAmendment(
        'new summary', 'NULL')
    self.assertEqual(
        [{'value': 'new summary', 'url': None}],
        tracker_bizobj.AmendmentLinks(summary_amendment, users_by_id, 'proj'))

    summary_amendment = tracker_bizobj.MakeSummaryAmendment(
        'new summary', 'old info')
    self.assertEqual(
        [{'value': 'new summary (was: old info)', 'url': None}],
        tracker_bizobj.AmendmentLinks(summary_amendment, users_by_id, 'proj'))

    # STATUS
    status_amendment = tracker_bizobj.MakeStatusAmendment('New', None)
    self.assertEqual(
        [{'value': 'New', 'url': None}],
        tracker_bizobj.AmendmentLinks(status_amendment, users_by_id, 'proj'))

    status_amendment = tracker_bizobj.MakeStatusAmendment('New', 'NULL')
    self.assertEqual(
        [{'value': 'New', 'url': None}],
        tracker_bizobj.AmendmentLinks(status_amendment, users_by_id, 'proj'))

    status_amendment = tracker_bizobj.MakeStatusAmendment(
        'Assigned', 'New')
    self.assertEqual(
        [{'value': 'Assigned (was: New)', 'url': None}],
        tracker_bizobj.AmendmentLinks(status_amendment, users_by_id, 'proj'))

    # OWNER
    owner_amendment = tracker_bizobj.MakeOwnerAmendment(0, 0)
    self.assertEqual(
        [{'value': '----', 'url': None}],
        tracker_bizobj.AmendmentLinks(owner_amendment, users_by_id, 'proj'))
    owner_amendment = tracker_bizobj.MakeOwnerAmendment(111, 0)
    self.assertEqual(
        [{'value': 'foo@gmail.com', 'url': None}],
        tracker_bizobj.AmendmentLinks(owner_amendment, users_by_id, 'proj'))

    # BLOCKEDON, BLOCKING, MERGEDINTO
    blocking_amendment = tracker_bizobj.MakeBlockingAmendment(
        [(None, 123), ('blah', 234)], [(None, 345), ('blah', 456)])
    self.assertEqual([
        {'value': '-345', 'url': '/p/proj/issues/detail?id=345'},
        {'value': '-blah:456', 'url': '/p/blah/issues/detail?id=456'},
        {'value': '123', 'url': '/p/proj/issues/detail?id=123'},
        {'value': 'blah:234', 'url': '/p/blah/issues/detail?id=234'}],
        tracker_bizobj.AmendmentLinks(blocking_amendment, users_by_id, 'proj'))

    # newvalue catchall
    label_amendment = tracker_bizobj.MakeLabelsAmendment(
        ['My-Label', 'Your-Label'], ['Their-Label'])
    self.assertEqual([
        {'value': '-Their-Label', 'url': None},
        {'value': 'My-Label', 'url': None},
        {'value': 'Your-Label', 'url': None}],
        tracker_bizobj.AmendmentLinks(label_amendment, users_by_id, 'proj'))

    # CC, or CUSTOM with user type
    cc_amendment = tracker_bizobj.MakeCcAmendment([222, 333], [111])
    self.assertEqual([
        {'value': '-foo@gmail.com', 'url': None},
        {'value': 'bar@gmail.com', 'url': None},
        {'value': 'baz@gmail.com', 'url': None}],
        tracker_bizobj.AmendmentLinks(cc_amendment, users_by_id, 'proj'))
    user_amendment = tracker_bizobj.MakeAmendment(
        tracker_pb2.FieldID.CUSTOM, None, [222, 333], [111], 'ultracc')
    self.assertEqual([
        {'value': '-foo@gmail.com', 'url': None},
        {'value': 'bar@gmail.com', 'url': None},
        {'value': 'baz@gmail.com', 'url': None}],
        tracker_bizobj.AmendmentLinks(user_amendment, users_by_id, 'proj'))

    # deleted users
    cc_amendment_deleted = tracker_bizobj.MakeCcAmendment(
        [framework_constants.DELETED_USER_ID], [])
    self.assertEqual(
        [{'value': framework_constants.DELETED_USER_NAME, 'url': None}],
        tracker_bizobj.AmendmentLinks(
            cc_amendment_deleted, users_by_id, 'proj'))

  def testGetAmendmentFieldName_Custom(self):
    amendment = tracker_bizobj.MakeAmendment(
        tracker_pb2.FieldID.CUSTOM, None, [222, 333], [111], 'Rabbit')
    self.assertEqual('Rabbit', tracker_bizobj.GetAmendmentFieldName(amendment))

  def testGetAmendmentFieldName_Builtin(self):
    amendment = tracker_bizobj.MakeAmendment(
        tracker_pb2.FieldID.SUMMARY, 'It broke', [], [])
    self.assertEqual('Summary', tracker_bizobj.GetAmendmentFieldName(amendment))

  def testMakeDanglingIssueRef(self):
    di_ref = tracker_bizobj.MakeDanglingIssueRef('proj', 123)
    self.assertEqual('proj', di_ref.project)
    self.assertEqual(123, di_ref.issue_id)

  def testFormatIssueURL_NoRef(self):
    self.assertEqual('', tracker_bizobj.FormatIssueURL(None))

  def testFormatIssueRef(self):
    self.assertEqual('', tracker_bizobj.FormatIssueRef(None))

    self.assertEqual(
        'p:1', tracker_bizobj.FormatIssueRef(('p', 1)))

    self.assertEqual(
        '1', tracker_bizobj.FormatIssueRef((None, 1)))

  def testFormatIssueRef_External(self):
    """Outputs shortlink as-is."""
    ref = tracker_pb2.DanglingIssueRef(ext_issue_identifier='b/1234')
    self.assertEqual('b/1234', tracker_bizobj.FormatIssueRef(ref))

  def testFormatIssueRef_ExternalInvalid(self):
    """Does not validate external IDs."""
    ref = tracker_pb2.DanglingIssueRef(ext_issue_identifier='invalid')
    self.assertEqual('invalid', tracker_bizobj.FormatIssueRef(ref))

  def testFormatIssueRef_Empty(self):
    """Passes on empty values."""
    ref = tracker_pb2.DanglingIssueRef(ext_issue_identifier='')
    self.assertEqual('', tracker_bizobj.FormatIssueRef(ref))

  def testParseIssueRef(self):
    self.assertEqual(None, tracker_bizobj.ParseIssueRef(''))
    self.assertEqual(None, tracker_bizobj.ParseIssueRef('  \t '))

    ref_pn, ref_id = tracker_bizobj.ParseIssueRef('1')
    self.assertEqual(None, ref_pn)
    self.assertEqual(1, ref_id)

    ref_pn, ref_id = tracker_bizobj.ParseIssueRef('-1')
    self.assertEqual(None, ref_pn)
    self.assertEqual(1, ref_id)

    ref_pn, ref_id = tracker_bizobj.ParseIssueRef('p:2')
    self.assertEqual('p', ref_pn)
    self.assertEqual(2, ref_id)

    ref_pn, ref_id = tracker_bizobj.ParseIssueRef('-p:2')
    self.assertEqual('p', ref_pn)
    self.assertEqual(2, ref_id)

  def testSafeParseIssueRef(self):
    self.assertEqual(None, tracker_bizobj._SafeParseIssueRef('-'))
    self.assertEqual(None, tracker_bizobj._SafeParseIssueRef('test:'))
    ref_pn, ref_id = tracker_bizobj.ParseIssueRef('p:2')
    self.assertEqual('p', ref_pn)
    self.assertEqual(2, ref_id)

  def testMergeFields_NoChange(self):
    fv1 = tracker_bizobj.MakeFieldValue(1, 42, None, None, None, None, False)
    merged_fvs, fvs_added, fvs_removed = tracker_bizobj.MergeFields(
        [fv1], [], [], [])
    self.assertEqual([fv1], merged_fvs)
    self.assertEqual([], fvs_added)
    self.assertEqual([], fvs_removed)

  def testMergeFields_SingleValued(self):
    fd = tracker_pb2.FieldDef(field_id=1, field_name='foo')
    fv1 = tracker_bizobj.MakeFieldValue(1, 42, None, None, None, None, False)
    fv2 = tracker_bizobj.MakeFieldValue(1, 43, None, None, None, None, False)
    fv3 = tracker_bizobj.MakeFieldValue(1, 44, None, None, None, None, False)

    # Adding one replaces all values since the field is single-valued.
    merged_fvs, fvs_added, fvs_removed = tracker_bizobj.MergeFields(
        [fv1, fv2], [fv3], [], [fd])
    self.assertItemsEqual([fv3], merged_fvs)
    self.assertItemsEqual([fv3], fvs_added)
    self.assertItemsEqual([], fvs_removed)

    # Removing one just removes it, does not reset.
    merged_fvs, fvs_added, fvs_removed = tracker_bizobj.MergeFields(
        [fv1, fv2], [], [fv2], [fd])
    self.assertItemsEqual([fv1], merged_fvs)
    self.assertItemsEqual([], fvs_added)
    self.assertItemsEqual([fv2], fvs_removed)

  def testMergeFields_SingleValuedPhase(self):
    fd = tracker_pb2.FieldDef(
        field_id=1, field_name='phase-foo', is_phase_field=True)
    fv1 = tracker_bizobj.MakeFieldValue(
        1, 45, None, None, None, None, False, phase_id=1)
    fv2 = tracker_bizobj.MakeFieldValue(
        1, 46, None, None, None, None, False, phase_id=2)
    fv3 = tracker_bizobj.MakeFieldValue(
        1, 47, None, None, None, None, False, phase_id=1) # should replace fv4

     # Adding one replaces all values since the field is single-valued.
    merged_fvs, fvs_added, fvs_removed = tracker_bizobj.MergeFields(
        [fv1, fv2], [fv3], [], [fd])
    self.assertItemsEqual([fv3, fv2], merged_fvs)
    self.assertItemsEqual([fv3], fvs_added)
    self.assertItemsEqual([], fvs_removed)

    # Removing one just removes it, does not reset.
    merged_fvs, fvs_added, fvs_removed = tracker_bizobj.MergeFields(
        [fv1, fv2], [], [fv2], [fd])
    self.assertItemsEqual([fv1], merged_fvs)
    self.assertItemsEqual([], fvs_added)
    self.assertItemsEqual([fv2], fvs_removed)

  def testMergeFields_MultiValued(self):
    fd = tracker_pb2.FieldDef(
        field_id=1, field_name='foo', is_multivalued=True)
    fv1 = tracker_bizobj.MakeFieldValue(1, 42, None, None, None, None, False)
    fv2 = tracker_bizobj.MakeFieldValue(1, 43, None, None, None, None, False)
    fv3 = tracker_bizobj.MakeFieldValue(1, 44, None, None, None, None, False)
    fv4 = tracker_bizobj.MakeFieldValue(1, 42, None, None, None, None, False)
    fv5 = tracker_bizobj.MakeFieldValue(1, 99, None, None, None, None, False)

    merged_fvs, fvs_added, fvs_removed = tracker_bizobj.MergeFields(
        [fv1, fv2], [fv2, fv3], [fv4, fv5], [fd])
    self.assertEqual([fv2, fv3], merged_fvs)
    self.assertEqual([fv3], fvs_added)
    self.assertEqual([fv4], fvs_removed)

  def testMergeFields_MultiValuedPhase(self):
    fd = tracker_pb2.FieldDef(
        field_id=1, field_name='foo', is_multivalued=True, is_phase_field=True)
    fv1 = tracker_bizobj.MakeFieldValue(
        1, 42, None, None, None, None, False, phase_id=1)
    fv2 = tracker_bizobj.MakeFieldValue(
        1, 43, None, None, None, None, False, phase_id=2)
    fv3 = tracker_bizobj.MakeFieldValue(
        1, 44, None, None, None, None, False, phase_id=1)
    fv4 = tracker_bizobj.MakeFieldValue(
        1, 99, None, None, None, None, False, phase_id=2)

    merged_fvs, fvs_added, fvs_removed = tracker_bizobj.MergeFields(
        [fv1, fv2], [fv3, fv1], [fv2, fv4], [fd])
    self.assertItemsEqual([fv1, fv3], merged_fvs)
    self.assertItemsEqual([fv3], fvs_added)
    self.assertItemsEqual([fv2], fvs_removed)

  def testSplitBlockedOnRanks_Normal(self):
    issue = tracker_pb2.Issue()
    issue.blocked_on_iids = [78902, 78903, 78904]
    issue.blocked_on_ranks = [10, 20, 30]
    rank_rows = list(zip(issue.blocked_on_iids, issue.blocked_on_ranks))
    rank_rows.reverse()
    ret = tracker_bizobj.SplitBlockedOnRanks(
        issue, 78903, False, issue.blocked_on_iids)
    self.assertEqual(ret, (rank_rows[:1], rank_rows[1:]))

  def testSplitBlockedOnRanks_BadTarget(self):
    issue = tracker_pb2.Issue()
    issue.blocked_on_iids = [78902, 78903, 78904]
    issue.blocked_on_ranks = [10, 20, 30]
    rank_rows = list(zip(issue.blocked_on_iids, issue.blocked_on_ranks))
    rank_rows.reverse()
    ret = tracker_bizobj.SplitBlockedOnRanks(
        issue, 78999, False, issue.blocked_on_iids)
    self.assertEqual(ret, (rank_rows, []))
