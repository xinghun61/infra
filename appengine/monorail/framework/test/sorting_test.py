# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for sorting.py functions."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
# For convenient debugging
import logging

import mox

from framework import sorting
from framework import framework_views
from proto import tracker_pb2
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


def MakeDescending(accessor):
  return sorting._MaybeMakeDescending(accessor, True)


class DescendingValueTest(unittest.TestCase):

  def testMinString(self):
    """When sorting desc, a min string will sort last instead of first."""
    actual = sorting.DescendingValue.MakeDescendingValue(sorting.MIN_STRING)
    self.assertEqual(sorting.MAX_STRING, actual)

  def testMaxString(self):
    """When sorting desc, a max string will sort first instead of last."""
    actual = sorting.DescendingValue.MakeDescendingValue(sorting.MAX_STRING)
    self.assertEqual(sorting.MIN_STRING, actual)

  def testDescValues(self):
    """The point of DescendingValue is to reverse the sort order."""
    anti_a = sorting.DescendingValue.MakeDescendingValue('a')
    anti_b = sorting.DescendingValue.MakeDescendingValue('b')
    self.assertTrue(anti_a > anti_b)

  def testMaybeMakeDescending(self):
    """It returns an accessor that makes DescendingValue iff arg is True."""
    asc_accessor = sorting._MaybeMakeDescending(lambda issue: 'a', False)
    asc_value = asc_accessor('fake issue')
    self.assertTrue(asc_value is 'a')

    desc_accessor = sorting._MaybeMakeDescending(lambda issue: 'a', True)
    print(desc_accessor)
    desc_value = desc_accessor('fake issue')
    self.assertTrue(isinstance(desc_value, sorting.DescendingValue))


class SortingTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.default_cols = 'a b c'
    self.builtin_cols = 'a b x y z'
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.config.component_defs.append(tracker_bizobj.MakeComponentDef(
        11, 789, 'Database', 'doc', False, [], [], 0, 0))
    self.config.component_defs.append(tracker_bizobj.MakeComponentDef(
        22, 789, 'User Interface', 'doc', True, [], [], 0, 0))
    self.config.component_defs.append(tracker_bizobj.MakeComponentDef(
        33, 789, 'Installer', 'doc', False, [], [], 0, 0))

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testMakeSingleSortKeyAccessor_Status(self):
    """Sorting by status should create an accessor for that column."""
    self.mox.StubOutWithMock(sorting, '_IndexOrLexical')
    status_names = [wks.status for wks in self.config.well_known_statuses]
    sorting._IndexOrLexical(status_names, 'status accessor')
    self.mox.ReplayAll()

    sorting._MakeSingleSortKeyAccessor(
      'status', self.config, {'status': 'status accessor'}, [], {}, [])
    self.mox.VerifyAll()

  def testMakeSingleSortKeyAccessor_Component(self):
    """Sorting by component should create an accessor for that column."""
    self.mox.StubOutWithMock(sorting, '_IndexListAccessor')
    component_ids = [11, 33, 22]
    sorting._IndexListAccessor(component_ids, 'component accessor')
    self.mox.ReplayAll()

    sorting._MakeSingleSortKeyAccessor(
      'component', self.config, {'component': 'component accessor'}, [], {}, [])
    self.mox.VerifyAll()

  def testMakeSingleSortKeyAccessor_OtherBuiltInColunms(self):
    """Sorting a built-in column should create an accessor for that column."""
    accessor = sorting._MakeSingleSortKeyAccessor(
      'buildincol', self.config, {'buildincol': 'accessor'}, [], {}, [])
    self.assertEqual('accessor', accessor)

  def testMakeSingleSortKeyAccessor_WithPostProcessor(self):
    """Sorting a built-in user column should create a user accessor."""
    self.mox.StubOutWithMock(sorting, '_MakeAccessorWithPostProcessor')
    users_by_id = {111: 'fake user'}
    sorting._MakeAccessorWithPostProcessor(
        users_by_id, 'mock owner accessor', 'mock postprocessor')
    self.mox.ReplayAll()

    sorting._MakeSingleSortKeyAccessor(
      'owner', self.config, {'owner': 'mock owner accessor'},
      {'owner': 'mock postprocessor'}, users_by_id, [])
    self.mox.VerifyAll()

  def testIndexOrLexical(self):
    well_known_values = ['x-a', 'x-b', 'x-c', 'x-d']
    art = 'this is a fake artifact'

    # Case 1: accessor generates no values.
    base_accessor = lambda art: None
    accessor = sorting._IndexOrLexical(well_known_values, base_accessor)
    self.assertEqual(sorting.MAX_STRING, accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual(sorting.DescendingValue(sorting.MAX_STRING),
                     neg_accessor(art))

    # Case 2: accessor generates a value, but it is an empty value.
    base_accessor = lambda art: ''
    accessor = sorting._IndexOrLexical(well_known_values, base_accessor)
    self.assertEqual(sorting.MAX_STRING, accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual(sorting.DescendingValue(sorting.MAX_STRING),
                     neg_accessor(art))

    # Case 3: A single well-known value
    base_accessor = lambda art: 'x-c'
    accessor = sorting._IndexOrLexical(well_known_values, base_accessor)
    self.assertEqual(2, accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual(-2, neg_accessor(art))

    # Case 4: A single odd-ball value
    base_accessor = lambda art: 'x-zzz'
    accessor = sorting._IndexOrLexical(well_known_values, base_accessor)
    self.assertEqual('x-zzz', accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual(
        sorting.DescendingValue('x-zzz'), neg_accessor(art))

  def testIndexListAccessor_SomeWellKnownValues(self):
    """Values sort according to their position in the well-known list."""
    well_known_values = [11, 33, 22]  # These represent component IDs.
    art = fake.MakeTestIssue(789, 1, 'sum 1', 'New', 111)
    base_accessor = lambda issue: issue.component_ids
    accessor = sorting._IndexListAccessor(well_known_values, base_accessor)

    # Case 1: accessor generates no values.
    self.assertEqual(sorting.MAX_STRING, accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual(sorting.MAX_STRING, neg_accessor(art))

    # Case 2: A single well-known value
    art.component_ids = [33]
    self.assertEqual([1], accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual([-1], neg_accessor(art))

    # Case 3: Multiple well-known and odd-ball values
    art.component_ids = [33, 11, 99]
    self.assertEqual([0, 1, sorting.MAX_STRING], accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual([sorting.MAX_STRING, -1, 0],
                     neg_accessor(art))

  def testIndexListAccessor_NoWellKnownValues(self):
    """When there are no well-known values, all values sort last."""
    well_known_values = []  # Nothing pre-defined, so everything is oddball
    art = fake.MakeTestIssue(789, 1, 'sum 1', 'New', 111)
    base_accessor = lambda issue: issue.component_ids
    accessor = sorting._IndexListAccessor(well_known_values, base_accessor)

    # Case 1: accessor generates no values.
    self.assertEqual(sorting.MAX_STRING, accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual(sorting.MAX_STRING, neg_accessor(art))

    # Case 2: A single oddball value
    art.component_ids = [33]
    self.assertEqual([sorting.MAX_STRING], accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual([sorting.MAX_STRING], neg_accessor(art))

    # Case 3: Multiple odd-ball values
    art.component_ids = [33, 11, 99]
    self.assertEqual(
      [sorting.MAX_STRING, sorting.MAX_STRING, sorting.MAX_STRING],
      accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual(
      [sorting.MAX_STRING, sorting.MAX_STRING, sorting.MAX_STRING],
      neg_accessor(art))

  def testIndexOrLexicalList(self):
    well_known_values = ['Pri-High', 'Pri-Med', 'Pri-Low']
    art = fake.MakeTestIssue(789, 1, 'sum 1', 'New', 111, merged_into=200001)

    # Case 1: accessor generates no values.
    accessor = sorting._IndexOrLexicalList(well_known_values, [], 'pri', {})
    self.assertEqual(sorting.MAX_STRING, accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual(sorting.MAX_STRING, neg_accessor(art))

    # Case 2: A single well-known value
    art.labels = ['Pri-Med']
    accessor = sorting._IndexOrLexicalList(well_known_values, [], 'pri', {})
    self.assertEqual([1], accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual([-1], neg_accessor(art))

    # Case 3: Multiple well-known and odd-ball values
    art.labels = ['Pri-zzz', 'Pri-Med', 'yyy', 'Pri-High']
    accessor = sorting._IndexOrLexicalList(well_known_values, [], 'pri', {})
    self.assertEqual([0, 1, 'zzz'], accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual([sorting.DescendingValue('zzz'), -1, 0],
                     neg_accessor(art))

    # Case 4: Multi-part prefix.
    well_known_values.extend(['X-Y-Header', 'X-Y-Footer'])
    art.labels = ['X-Y-Footer', 'X-Y-Zone', 'X-Y-Header', 'X-Y-Area']
    accessor = sorting._IndexOrLexicalList(well_known_values, [], 'x-y', {})
    self.assertEqual([3, 4, 'area', 'zone'], accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual([sorting.DescendingValue('zone'),
                      sorting.DescendingValue('area'), -4, -3],
                     neg_accessor(art))

  def testIndexOrLexicalList_CustomFields(self):
    art = fake.MakeTestIssue(789, 1, 'sum 2', 'New', 111)
    art.labels = ['samename-value1']
    art.field_values = [tracker_bizobj.MakeFieldValue(
        3, 6078, None, None, None, None, False)]

    all_field_defs = [
        tracker_bizobj.MakeFieldDef(
            3, 789, 'samename', tracker_pb2.FieldTypes.INT_TYPE,
            None, None, False, False, False, None, None, None, False, None,
            None, None, None, 'cow spots', False),
        tracker_bizobj.MakeFieldDef(
            4, 788, 'samename', tracker_pb2.FieldTypes.APPROVAL_TYPE,
            None, None, False, False, False, None, None, None, False, None,
            None, None, None, 'cow spots', False),
        tracker_bizobj.MakeFieldDef(
            4, 788, 'notsamename', tracker_pb2.FieldTypes.APPROVAL_TYPE,
            None, None, False, False, False, None, None, None, False, None,
            None, None, None, 'should get filtered out', False)
    ]

    accessor = sorting._IndexOrLexicalList([], all_field_defs, 'samename', {})
    self.assertEqual([6078, 'value1'], accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual(
        [sorting.DescendingValue('value1'), -6078], neg_accessor(art))

  def testIndexOrLexicalList_PhaseCustomFields(self):
    art = fake.MakeTestIssue(789, 1, 'sum 2', 'New', 111)
    art.labels = ['summer.goats-value1']
    art.field_values = [
        tracker_bizobj.MakeFieldValue(
            3, 33, None, None, None, None, False, phase_id=77),
        tracker_bizobj.MakeFieldValue(
            3, 34, None, None, None, None, False, phase_id=77),
        tracker_bizobj.MakeFieldValue(
            3, 1000, None, None, None, None, False, phase_id=78)]
    art.phases = [tracker_pb2.Phase(phase_id=77, name='summer'),
                  tracker_pb2.Phase(phase_id=78, name='winter')]

    all_field_defs = [
        tracker_bizobj.MakeFieldDef(
            3, 789, 'goats', tracker_pb2.FieldTypes.INT_TYPE,
            None, None, False, False, True, None, None, None, False, None,
            None, None, None, 'goats love mineral', False, is_phase_field=True),
        tracker_bizobj.MakeFieldDef(
            4, 788, 'boo', tracker_pb2.FieldTypes.APPROVAL_TYPE,
            None, None, False, False, False, None, None, None, False, None,
            None, None, None, 'ahh', False),
        ]

    accessor = sorting._IndexOrLexicalList(
        [], all_field_defs, 'summer.goats', {})
    self.assertEqual([33, 34, 'value1'], accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual(
        [sorting.DescendingValue('value1'), -34, -33], neg_accessor(art))

  def testIndexOrLexicalList_ApprovalStatus(self):
    art = fake.MakeTestIssue(789, 1, 'sum 2', 'New', 111)
    art.labels = ['samename-value1']
    art.approval_values = [tracker_pb2.ApprovalValue(approval_id=4)]

    all_field_defs = [
        tracker_bizobj.MakeFieldDef(
            3, 789, 'samename', tracker_pb2.FieldTypes.INT_TYPE,
            None, None, False, False, False, None, None, None, False, None,
            None, None, None, 'cow spots', False),
        tracker_bizobj.MakeFieldDef(
            4, 788, 'samename', tracker_pb2.FieldTypes.APPROVAL_TYPE,
            None, None, False, False, False, None, None, None, False, None,
            None, None, None, 'cow spots', False)
    ]

    accessor = sorting._IndexOrLexicalList([], all_field_defs, 'samename', {})
    self.assertEqual([0, 'value1'], accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual([sorting.DescendingValue('value1'),
                      sorting.DescendingValue(0)],
                     neg_accessor(art))

  def testIndexOrLexicalList_ApprovalApprover(self):
    art = art = fake.MakeTestIssue(789, 1, 'sum 2', 'New', 111)
    art.labels = ['samename-approver-value1']
    art.approval_values = [
        tracker_pb2.ApprovalValue(approval_id=4, approver_ids=[333])]

    all_field_defs = [
        tracker_bizobj.MakeFieldDef(
            4, 788, 'samename', tracker_pb2.FieldTypes.APPROVAL_TYPE,
            None, None, False, False, False, None, None, None, False, None,
            None, None, None, 'cow spots', False)
    ]
    users_by_id = {333: framework_views.StuffUserView(333, 'a@test.com', True)}

    accessor = sorting._IndexOrLexicalList(
        [], all_field_defs, 'samename-approver', users_by_id)
    self.assertEqual(['a@test.com', 'value1'], accessor(art))
    neg_accessor = MakeDescending(accessor)
    self.assertEqual([sorting.DescendingValue('value1'),
                      sorting.DescendingValue('a@test.com')],
                     neg_accessor(art))

  def testComputeSortDirectives(self):
    config = tracker_pb2.ProjectIssueConfig()
    self.assertEquals(['project', 'id'],
                      sorting.ComputeSortDirectives(config, '', ''))

    self.assertEquals(['a', 'b', 'c', 'project', 'id'],
                      sorting.ComputeSortDirectives(config, '', 'a b C'))

    config.default_sort_spec = 'id -reporter Owner'
    self.assertEquals(['id', '-reporter', 'owner', 'project'],
                      sorting.ComputeSortDirectives(config, '', ''))

    self.assertEquals(
        ['x', '-b', 'a', 'c', '-owner', 'id', '-reporter', 'project'],
        sorting.ComputeSortDirectives(config, 'x -b', 'A -b c -owner'))
