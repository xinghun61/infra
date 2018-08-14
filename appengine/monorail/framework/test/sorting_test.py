# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for sorting.py functions."""

import unittest
# For convenient debugging
import logging

import mox

from framework import sorting
from proto import tracker_pb2
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


def MakeDescending(accessor):
  return sorting._MaybeMakeDescending(accessor, True)


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
    users_by_id = {111L: 'fake user'}
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
    art = fake.MakeTestIssue(789, 1, 'sum 1', 'New', 111L)
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
    art = fake.MakeTestIssue(789, 1, 'sum 1', 'New', 111L)
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
    art = fake.MakeTestIssue(789, 1, 'sum 1', 'New', 111L, merged_into=200001)

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
