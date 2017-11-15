# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for issue tracker bizobj functions."""

import unittest

from framework import framework_constants
from framework import framework_views
from proto import tracker_pb2
from tracker import tracker_bizobj
from tracker import tracker_constants


class BizobjTest(unittest.TestCase):

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

  def testGetLabels(self):
    issue = tracker_pb2.Issue()
    self.assertEquals(tracker_bizobj.GetLabels(issue), [])

    issue.derived_labels.extend(['a', 'b', 'c'])
    self.assertEquals(tracker_bizobj.GetLabels(issue), ['a', 'b', 'c'])

    issue.labels.extend(['d', 'e', 'f'])
    self.assertEquals(tracker_bizobj.GetLabels(issue),
                      ['d', 'e', 'f', 'a', 'b', 'c'])

  def testUsersInvolvedInConfig_Empty(self):
    config = tracker_pb2.ProjectIssueConfig()
    self.assertEqual(set(), tracker_bizobj.UsersInvolvedInConfig(config))

  def testUsersInvolvedInConfig_Default(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.assertEqual(set(), tracker_bizobj.UsersInvolvedInConfig(config))

  def testUsersInvolvedInConfig_Normal(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.templates[0].owner_id = 111L
    config.templates[0].admin_ids = [111L, 222L]
    config.field_defs = [tracker_pb2.FieldDef(admin_ids=[333L])]
    self.assertEqual(
        {111L, 222L, 333L},
        tracker_bizobj.UsersInvolvedInConfig(config))

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

  def testGetGrantedPerms_Empty(self):
    config = tracker_pb2.ProjectIssueConfig()
    issue = tracker_pb2.Issue()
    self.assertEqual(
        set(), tracker_bizobj.GetGrantedPerms(issue, {111L}, config))

  def testGetGrantedPerms_Default(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    issue = tracker_pb2.Issue()
    self.assertEqual(
        set(), tracker_bizobj.GetGrantedPerms(issue, {111L}, config))

  def testGetGrantedPerms_NothingGranted(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(field_id=1)  # Nothing granted
    config.field_defs = [fd]
    fv = tracker_pb2.FieldValue(field_id=1, user_id=222L)
    issue = tracker_pb2.Issue(field_values=[fv])
    self.assertEqual(
        set(),
        tracker_bizobj.GetGrantedPerms(issue, {111L, 222L}, config))

  def testGetGrantedPerms_Normal(self):
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    fd = tracker_pb2.FieldDef(field_id=1, grants_perm='Highlight')
    config.field_defs = [fd]
    fv = tracker_pb2.FieldValue(field_id=1, user_id=222L)
    issue = tracker_pb2.Issue(field_values=[fv])
    self.assertEqual(
        set(),
        tracker_bizobj.GetGrantedPerms(issue, {111L}, config))
    self.assertEqual(
        set(['highlight']),
        tracker_bizobj.GetGrantedPerms(issue, {111L, 222L}, config))

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

  def testMakeFieldDef_Basic(self):
    fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'Size', tracker_pb2.FieldTypes.USER_TYPE, None, None,
        False, False, False, None, None, None, False,
        None, None, None, 'no_action', 'Some field', False)
    self.assertEqual(1, fd.field_id)

  def testMakeFieldDef_Full(self):
    fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'Size', tracker_pb2.FieldTypes.INT_TYPE, None, None,
        False, False, False, 1, 100, None, False,
        None, None, None, 'no_action', 'Some field', False)
    self.assertEqual(1, fd.min_value)
    self.assertEqual(100, fd.max_value)

    fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'Size', tracker_pb2.FieldTypes.STR_TYPE, None, None,
        False, False, False, None, None, 'A.*Z', False,
        'EditIssue', None, None, 'no_action', 'Some field', False)
    self.assertEqual('A.*Z', fd.regex)
    self.assertEqual('EditIssue', fd.needs_perm)

  def testMakeFieldValue(self):
    # Only the first value counts.
    fv = tracker_bizobj.MakeFieldValue(1, 42, 'yay', 111L, None, None, True)
    self.assertEqual(1, fv.field_id)
    self.assertEqual(42, fv.int_value)
    self.assertIsNone(fv.str_value)
    self.assertEqual(None, fv.user_id)

    fv = tracker_bizobj.MakeFieldValue(1, None, 'yay', 111L, None, None, True)
    self.assertEqual('yay', fv.str_value)
    self.assertEqual(None, fv.user_id)

    fv = tracker_bizobj.MakeFieldValue(1, None, None, 111L, None, None, True)
    self.assertEqual(111L, fv.user_id)
    self.assertEqual(True, fv.derived)

    fv = tracker_bizobj.MakeFieldValue(
        1, None, None, None, 1234567890, None, True)
    self.assertEqual(1234567890, fv.date_value)
    self.assertEqual(True, fv.derived)

    fv = tracker_bizobj.MakeFieldValue(
        1, None, None, None, None, 'www.google.com', True)
    self.assertEqual('www.google.com', fv.url_value)
    self.assertEqual(True, fv.derived)

    with self.assertRaises(ValueError):
      tracker_bizobj.MakeFieldValue(1, None, None, None, None, None, True)

  def testGetFieldValueWithRawValue(self):
    class MockUser(object):
      def __init__(self):
        self.email = 'test@example.com'
    users_by_id = {111: MockUser()}

    class MockFieldValue(object):
      def __init__(
          self, int_value=None, str_value=None, user_id=None, date_value=None):
        self.int_value = int_value
        self.str_value = str_value
        self.user_id = user_id
        self.date_value = date_value

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
      1, 789, 'UI', 'doc', False, [111L], [222L], 1234567890,
      111L)
    self.assertEqual(1, cd.component_id)
    self.assertEqual([111L], cd.admin_ids)
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
             status='status', owner_id=111L))
    self.assertEqual('name', template.name)
    self.assertEqual('content', template.content)
    self.assertEqual('summary', template.summary)
    self.assertEqual('status', template.status)
    self.assertEqual(111L, template.owner_id)
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
    self.assertTrue(len(config.templates) > 0)
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

    comment.user_id = 111L
    self.assertEqual(
        {111L}, tracker_bizobj.UsersInvolvedInComment(comment))

    amendment = tracker_pb2.Amendment(newvalue='foo')
    comment.amendments.append(amendment)
    self.assertEqual(
        {111L}, tracker_bizobj.UsersInvolvedInComment(comment))

    amendment.added_user_ids.append(222L)
    amendment.removed_user_ids.append(333L)
    self.assertEqual({111L, 222L, 333L},
                     tracker_bizobj.UsersInvolvedInComment(comment))

  def testUsersInvolvedInCommentList(self):
    self.assertEqual(set(), tracker_bizobj.UsersInvolvedInCommentList([]))

    c1 = tracker_pb2.IssueComment()
    c1.user_id = 111L
    c1.amendments.append(tracker_pb2.Amendment(newvalue='foo'))

    c2 = tracker_pb2.IssueComment()
    c2.user_id = 111L
    c2.amendments.append(tracker_pb2.Amendment(
        added_user_ids=[222L], removed_user_ids=[333L]))

    self.assertEqual({111L},
                     tracker_bizobj.UsersInvolvedInCommentList([c1]))

    self.assertEqual({111L, 222L, 333L},
                     tracker_bizobj.UsersInvolvedInCommentList([c2]))

    self.assertEqual({111L, 222L, 333L},
                     tracker_bizobj.UsersInvolvedInCommentList([c1, c2]))

  def testUsersInvolvedInIssues_Empty(self):
    self.assertEqual(set(), tracker_bizobj.UsersInvolvedInIssues([]))

  def testUsersInvolvedInIssues_Normal(self):
    issue1 = tracker_pb2.Issue(
        reporter_id=111L, owner_id=222L, cc_ids=[222L, 333L])
    issue2 = tracker_pb2.Issue(
        reporter_id=333L, owner_id=444L, derived_cc_ids=[222L, 444L])
    issue2.field_values = [tracker_pb2.FieldValue(user_id=555L)]
    self.assertEqual(
        set([0L, 111L, 222L, 333L, 444L, 555L]),
        tracker_bizobj.UsersInvolvedInIssues([issue1, issue2]))

  def testMakeAmendment(self):
    amendment = tracker_bizobj.MakeAmendment(
        tracker_pb2.FieldID.STATUS, 'new', [111L], [222L])
    self.assertEqual(tracker_pb2.FieldID.STATUS, amendment.field)
    self.assertEqual('new', amendment.newvalue)
    self.assertEqual([111L], amendment.added_user_ids)
    self.assertEqual([222L], amendment.removed_user_ids)

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
    amendment = tracker_bizobj.MakeOwnerAmendment(111L, 0)
    self.assertEqual(tracker_pb2.FieldID.OWNER, amendment.field)
    self.assertEqual('', amendment.newvalue)
    self.assertEqual([111L], amendment.added_user_ids)
    self.assertEqual([0], amendment.removed_user_ids)

  def testMakeCcAmendment(self):
    amendment = tracker_bizobj.MakeCcAmendment([111L], [222L])
    self.assertEqual(tracker_pb2.FieldID.CC, amendment.field)
    self.assertEqual('', amendment.newvalue)
    self.assertEqual([111L], amendment.added_user_ids)
    self.assertEqual([222L], amendment.removed_user_ids)

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
            tracker_pb2.FieldID.CUSTOM, '', [111L], [222L], 'Friends'),
        tracker_bizobj.MakeFieldAmendment(1, config, [111L], [222L]))
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '', [], [222L], 'Friends'),
        tracker_bizobj.MakeFieldAmendment(1, config, [], [222L]))

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
            tracker_pb2.FieldID.CUSTOM, '', [111L], [], 'Friend'),
        tracker_bizobj.MakeFieldAmendment(1, config, [111L], [222L]))
    self.assertEqual(
        tracker_bizobj.MakeAmendment(
            tracker_pb2.FieldID.CUSTOM, '', [], [], 'Friend'),
        tracker_bizobj.MakeFieldAmendment(1, config, [], [222L]))

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
        111L: framework_views.StuffUserView(111L, 'username@gmail.com', True)
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
    owner_amendment = tracker_bizobj.MakeOwnerAmendment(111L, 0)
    self.assertEqual(
        'usern...@gmail.com',
        tracker_bizobj.AmendmentString(owner_amendment, users_by_id))

  def testAmendmentLinks(self):
    users_by_id = {
        111L: framework_views.StuffUserView(111L, 'foo@gmail.com', False),
        222L: framework_views.StuffUserView(222L, 'bar@gmail.com', False),
        333L: framework_views.StuffUserView(333L, 'baz@gmail.com', False)
        }
    # SUMMARY
    summary_amendment = tracker_bizobj.MakeSummaryAmendment('new summary', None)
    self.assertEqual(
        [{'value': 'new summary', 'url': None}],
        tracker_bizobj.AmendmentLinks(summary_amendment, users_by_id, 'proj'))
    summary_amendment = tracker_bizobj.MakeSummaryAmendment(
        'new summary', 'old info')
    self.assertEqual(
        [{'value': 'new summary (was: old info)', 'url': None}],
        tracker_bizobj.AmendmentLinks(summary_amendment, users_by_id, 'proj'))

    # OWNER
    owner_amendment = tracker_bizobj.MakeOwnerAmendment(0, 0)
    self.assertEqual(
        [{'value': '----', 'url': None}],
        tracker_bizobj.AmendmentLinks(owner_amendment, users_by_id, 'proj'))
    owner_amendment = tracker_bizobj.MakeOwnerAmendment(111L, 0)
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
    cc_amendment = tracker_bizobj.MakeCcAmendment([222L, 333L], [111L])
    self.assertEqual([
        {'value': '-foo@gmail.com', 'url': None},
        {'value': 'bar@gmail.com', 'url': None},
        {'value': 'baz@gmail.com', 'url': None}],
        tracker_bizobj.AmendmentLinks(cc_amendment, users_by_id, 'proj'))
    user_amendment = tracker_bizobj.MakeAmendment(
        tracker_pb2.FieldID.CUSTOM, None, [222L, 333L], [111L], 'ultracc')
    self.assertEqual([
        {'value': '-foo@gmail.com', 'url': None},
        {'value': 'bar@gmail.com', 'url': None},
        {'value': 'baz@gmail.com', 'url': None}],
        tracker_bizobj.AmendmentLinks(user_amendment, users_by_id, 'proj'))

  def testGetAmendmentFieldName_Custom(self):
    amendment = tracker_bizobj.MakeAmendment(
        tracker_pb2.FieldID.CUSTOM, None, [222L, 333L], [111L], 'Rabbit')
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
    self.assertEqual([fv3], merged_fvs)
    self.assertEqual([fv3], fvs_added)
    self.assertEqual([], fvs_removed)

    # Removing one just removes it, does not reset.
    merged_fvs, fvs_added, fvs_removed = tracker_bizobj.MergeFields(
        [fv1, fv2], [], [fv2], [fd])
    self.assertEqual([fv1], merged_fvs)
    self.assertEqual([], fvs_added)
    self.assertEqual([fv2], fvs_removed)

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

  def testSplitBlockedOnRanks_Normal(self):
    issue = tracker_pb2.Issue()
    issue.blocked_on_iids = [78902, 78903, 78904]
    issue.blocked_on_ranks = [10, 20, 30]
    rank_rows = zip(issue.blocked_on_iids, issue.blocked_on_ranks)
    rank_rows.reverse()
    ret = tracker_bizobj.SplitBlockedOnRanks(
        issue, 78903, False, issue.blocked_on_iids)
    self.assertEqual(ret, (rank_rows[:1], rank_rows[1:]))

  def testSplitBlockedOnRanks_BadTarget(self):
    issue = tracker_pb2.Issue()
    issue.blocked_on_iids = [78902, 78903, 78904]
    issue.blocked_on_ranks = [10, 20, 30]
    rank_rows = zip(issue.blocked_on_iids, issue.blocked_on_ranks)
    rank_rows.reverse()
    ret = tracker_bizobj.SplitBlockedOnRanks(
        issue, 78999, False, issue.blocked_on_iids)
    self.assertEqual(ret, (rank_rows, []))
