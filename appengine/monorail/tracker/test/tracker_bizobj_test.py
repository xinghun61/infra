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
        False, False, None, None, None, False,
        None, None, None, 'Some field', False)
    self.assertEqual(1, fd.field_id)

  def testMakeFieldDef_Full(self):
    fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'Size', tracker_pb2.FieldTypes.INT_TYPE, None, None,
        False, False, 1, 100, None, False,
        None, None, None, 'Some field', False)
    self.assertEqual(1, fd.min_value)
    self.assertEqual(100, fd.max_value)

    fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'Size', tracker_pb2.FieldTypes.STR_TYPE, None, None,
        False, False, None, None, 'A.*Z', False,
        'EditIssue', None, None, 'Some field', False)
    self.assertEqual('A.*Z', fd.regex)
    self.assertEqual('EditIssue', fd.needs_perm)

  def testMakeFieldValue(self):
    # Only the first value counts.
    fv = tracker_bizobj.MakeFieldValue(1, 42, 'yay', 111L, True)
    self.assertEqual(1, fv.field_id)
    self.assertEqual(42, fv.int_value)
    self.assertIsNone(fv.str_value)
    self.assertEqual(0, fv.user_id)

    fv = tracker_bizobj.MakeFieldValue(1, None, 'yay', 111L, True)
    self.assertEqual('yay', fv.str_value)
    self.assertEqual(0, fv.user_id)

    fv = tracker_bizobj.MakeFieldValue(1, None, None, 111L, True)
    self.assertEqual(111L, fv.user_id)
    self.assertEqual(True, fv.derived)

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

  def testMakeBlockedOnAmendment(self):
    ref1 = (None, 1)
    ref2 = ('other-proj', 2)
    amendment = tracker_bizobj.MakeBlockedOnAmendment([ref1], [ref2])
    self.assertEqual(tracker_pb2.FieldID.BLOCKEDON, amendment.field)
    self.assertEqual('-other-proj:2 1', amendment.newvalue)

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

  def testGetFieldValueWithRawValue(self):
    class MockUser(object):
      def __init__(self):
        self.email = 'test@example.com'
    users_by_id = {111: MockUser()}

    class MockFieldValue(object):
      def __init__(self, int_value=None, str_value=None, user_id=None):
        self.int_value = int_value
        self.str_value = str_value
        self.user_id = user_id

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
    # Use int_type from the field_value.
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
    # Use str_type from the field_value.
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

  def testSplitBlockedOnRanks(self):
    issue = tracker_pb2.Issue()
    issue.blocked_on_iids = [78902, 78903, 78904]
    issue.blocked_on_ranks = [10, 20, 30]
    rank_rows = zip(issue.blocked_on_iids, issue.blocked_on_ranks)
    rank_rows.reverse()
    ret = tracker_bizobj.SplitBlockedOnRanks(
        issue, 78903, False, issue.blocked_on_iids)
    self.assertEqual(ret, (rank_rows[:1], rank_rows[1:]))
