# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for table_view_helpers classes and functions."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import unittest
import logging

from framework import framework_views
from framework import table_view_helpers
from proto import tracker_pb2
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


EMPTY_SEARCH_RESULTS = []

SEARCH_RESULTS_WITH_LABELS = [
    fake.MakeTestIssue(
        789, 1, 'sum 1', 'New', 111, labels='Priority-High Mstone-1',
        merged_into=200001, star_count=1),
    fake.MakeTestIssue(
        789, 2, 'sum 2', 'New', 111, labels='Priority-High Mstone-1',
        merged_into=1, star_count=1),
    fake.MakeTestIssue(
        789, 3, 'sum 3', 'New', 111, labels='Priority-Low Mstone-1.1',
        merged_into=1, star_count=1),
    # 'Visibility-Super-High' tests that only first dash counts
    fake.MakeTestIssue(
        789, 4, 'sum 4', 'New', 111, labels='Visibility-Super-High',
        star_count=1),
    ]


def MakeTestIssue(local_id, issue_id, summary):
  issue = tracker_pb2.Issue()
  issue.local_id = local_id
  issue.issue_id = issue_id
  issue.summary = summary
  return issue


class TableCellTest(unittest.TestCase):

  USERS_BY_ID = {}

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.config.field_defs = [
        tracker_bizobj.MakeFieldDef(
            1, 789, 'Goats', tracker_pb2.FieldTypes.INT_TYPE, None, None,
            False, False, False, None, None, None, False, None, None, None,
            None, 'Num of Goats in the season', False, is_phase_field=True),
        tracker_bizobj.MakeFieldDef(
            2, 789, 'DogNames', tracker_pb2.FieldTypes.STR_TYPE, None, None,
            False, False, False, None, None, None, False, None, None, None,
            None, 'good dog names', False),
        tracker_bizobj.MakeFieldDef(
            3, 789, 'Approval', tracker_pb2.FieldTypes.APPROVAL_TYPE,
            None, None, False, False, False, None, None, None, False, None,
            None, None, None, 'Tracks review from cows', False)
    ]
    self.config.approval_defs = [tracker_pb2.ApprovalDef(approval_id=3)]
    self.issue = MakeTestIssue(
        local_id=1, issue_id=100001, summary='One')
    self.issue.field_values = [
        tracker_bizobj.MakeFieldValue(
            1, 34, None, None, None, None, False, phase_id=23),
        tracker_bizobj.MakeFieldValue(
            1, 35, None, None, None, None, False, phase_id=24),
        tracker_bizobj.MakeFieldValue(
            2, None, 'Waffles', None, None, None, False),
    ]
    self.issue.phases = [
        tracker_pb2.Phase(phase_id=23, name='winter'),
        tracker_pb2.Phase(phase_id=24, name='summer')]
    self.issue.approval_values = [
        tracker_pb2.ApprovalValue(
            approval_id=3, approver_ids=[111, 222, 333])]
    self.users_by_id = {
        111: framework_views.StuffUserView(111, 'foo@example.com', False),
        222: framework_views.StuffUserView(222, 'foo2@example.com', True),
    }

    self.summary_table_cell_kws = {
        'col': None,
        'users_by_id': {},
        'non_col_labels': [('lab', False)],
        'label_values': {},
        'related_issues': {},
        'config': 'fake_config',
        }

  def testTableCellSummary(self):
    """TableCellSummary stores the data given to it."""
    cell = table_view_helpers.TableCellSummary(
        MakeTestIssue(4, 4, 'Lame default summary.'),
        **self.summary_table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_SUMMARY)
    self.assertEqual(cell.values[0].item, 'Lame default summary.')
    self.assertEqual(cell.non_column_labels[0].value, 'lab')

  def testTableCellSummary_NoPythonEscaping(self):
    """TableCellSummary stores the summary without escaping it in python."""
    cell = table_view_helpers.TableCellSummary(
        MakeTestIssue(4, 4, '<b>bold</b> "summary".'),
        **self.summary_table_cell_kws)
    self.assertEqual(cell.values[0].item,'<b>bold</b> "summary".')

  def testTableCellCustom_normal(self):
    """TableCellCustom stores the value of a custom FieldValue."""
    cell_dognames = table_view_helpers.TableCellCustom(
        self.issue, col='dognames', config=self.config)
    self.assertEqual(cell_dognames.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell_dognames.values[0].item, 'Waffles')

  def testTableCellCustom_phasefields(self):
    """TableCellCustom stores the value of a custom FieldValue."""
    cell_winter = table_view_helpers.TableCellCustom(
        self.issue, col='winter.goats', config=self.config)
    self.assertEqual(cell_winter.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell_winter.values[0].item, 34)

    cell_summer = table_view_helpers.TableCellCustom(
        self.issue, col='summer.goats', config=self.config)
    self.assertEqual(cell_summer.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell_summer.values[0].item, 35)

  def testTableCellApprovalStatus(self):
    """TableCellApprovalStatus stores the status of an ApprovalValue."""
    cell = table_view_helpers.TableCellApprovalStatus(
        self.issue, col='Approval', config=self.config)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 'NOT_SET')

  def testTableCellApprovalApprover(self):
    """TableCellApprovalApprover stores the approvers of an ApprovalValue."""
    cell = table_view_helpers.TableCellApprovalApprover(
        self.issue, col='Approval-approver', config=self.config,
        users_by_id=self.users_by_id)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(len(cell.values), 2)
    self.assertItemsEqual([cell.values[0].item, cell.values[1].item],
                          ['foo@example.com', 'f...@example.com'])

  # TODO(jrobbins): TableCellProject, TableCellStars



class TableViewHelpersTest(unittest.TestCase):

  def setUp(self):
    self.default_cols = 'a b c'
    self.builtin_cols = ['a', 'b', 'x', 'y', 'z']
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

  def testComputeUnshownColumns_CommonCase(self):
    shown_cols = ['a', 'b', 'c']
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.default_col_spec = self.default_cols
    config.well_known_labels = []

    unshown = table_view_helpers.ComputeUnshownColumns(
        EMPTY_SEARCH_RESULTS, shown_cols, config, self.builtin_cols)
    self.assertEquals(unshown, ['x', 'y', 'z'])

    unshown = table_view_helpers.ComputeUnshownColumns(
        SEARCH_RESULTS_WITH_LABELS, shown_cols, config, self.builtin_cols)
    self.assertEquals(
        unshown, ['Mstone', 'Priority', 'Visibility', 'x', 'y', 'z'])

  def testComputeUnshownColumns_MoreBuiltins(self):
    shown_cols = ['a', 'b', 'c', 'x', 'y']
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.default_col_spec = self.default_cols
    config.well_known_labels = []

    unshown = table_view_helpers.ComputeUnshownColumns(
        EMPTY_SEARCH_RESULTS, shown_cols, config, self.builtin_cols)
    self.assertEquals(unshown, ['z'])

    unshown = table_view_helpers.ComputeUnshownColumns(
        SEARCH_RESULTS_WITH_LABELS, shown_cols, config, self.builtin_cols)
    self.assertEquals(unshown, ['Mstone', 'Priority', 'Visibility', 'z'])

  def testComputeUnshownColumns_NotAllDefaults(self):
    shown_cols = ['a', 'b']
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.default_col_spec = self.default_cols
    config.well_known_labels = []

    unshown = table_view_helpers.ComputeUnshownColumns(
        EMPTY_SEARCH_RESULTS, shown_cols, config, self.builtin_cols)
    self.assertEquals(unshown, ['c', 'x', 'y', 'z'])

    unshown = table_view_helpers.ComputeUnshownColumns(
        SEARCH_RESULTS_WITH_LABELS, shown_cols, config, self.builtin_cols)
    self.assertEquals(
        unshown, ['Mstone', 'Priority', 'Visibility', 'c', 'x', 'y', 'z'])

  def testComputeUnshownColumns_ExtraNonDefaults(self):
    shown_cols = ['a', 'b', 'c', 'd', 'e', 'f']
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.default_col_spec = self.default_cols
    config.well_known_labels = []

    unshown = table_view_helpers.ComputeUnshownColumns(
        EMPTY_SEARCH_RESULTS, shown_cols, config, self.builtin_cols)
    self.assertEquals(unshown, ['x', 'y', 'z'])

    unshown = table_view_helpers.ComputeUnshownColumns(
        SEARCH_RESULTS_WITH_LABELS, shown_cols, config, self.builtin_cols)
    self.assertEquals(
        unshown, ['Mstone', 'Priority', 'Visibility', 'x', 'y', 'z'])

  def testComputeUnshownColumns_UserColumnsShown(self):
    shown_cols = ['a', 'b', 'c', 'Priority']
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.default_col_spec = self.default_cols
    config.well_known_labels = []

    unshown = table_view_helpers.ComputeUnshownColumns(
        EMPTY_SEARCH_RESULTS, shown_cols, config, self.builtin_cols)
    self.assertEquals(unshown, ['x', 'y', 'z'])

    unshown = table_view_helpers.ComputeUnshownColumns(
        SEARCH_RESULTS_WITH_LABELS, shown_cols, config, self.builtin_cols)
    self.assertEquals(unshown, ['Mstone', 'Visibility', 'x', 'y', 'z'])

  def testComputeUnshownColumns_EverythingShown(self):
    shown_cols = [
        'a', 'b', 'c', 'x', 'y', 'z', 'Priority', 'Mstone', 'Visibility']
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.default_col_spec = self.default_cols
    config.well_known_labels = []

    unshown = table_view_helpers.ComputeUnshownColumns(
        EMPTY_SEARCH_RESULTS, shown_cols, config, self.builtin_cols)
    self.assertEquals(unshown, [])

    unshown = table_view_helpers.ComputeUnshownColumns(
        SEARCH_RESULTS_WITH_LABELS, shown_cols, config, self.builtin_cols)
    self.assertEquals(unshown, [])

  def testComputeUnshownColumns_NothingShown(self):
    shown_cols = []
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.default_col_spec = self.default_cols
    config.well_known_labels = []

    unshown = table_view_helpers.ComputeUnshownColumns(
        EMPTY_SEARCH_RESULTS, shown_cols, config, self.builtin_cols)
    self.assertEquals(unshown, ['a', 'b', 'c', 'x', 'y', 'z'])

    unshown = table_view_helpers.ComputeUnshownColumns(
        SEARCH_RESULTS_WITH_LABELS, shown_cols, config, self.builtin_cols)
    self.assertEquals(
        unshown,
        ['Mstone', 'Priority', 'Visibility', 'a', 'b', 'c', 'x', 'y', 'z'])

  def testComputeUnshownColumns_NoBuiltins(self):
    shown_cols = ['a', 'b', 'c']
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.default_col_spec = ''
    config.well_known_labels = []
    builtin_cols = []

    unshown = table_view_helpers.ComputeUnshownColumns(
        EMPTY_SEARCH_RESULTS, shown_cols, config, builtin_cols)
    self.assertEquals(unshown, [])

    unshown = table_view_helpers.ComputeUnshownColumns(
        SEARCH_RESULTS_WITH_LABELS, shown_cols, config, builtin_cols)
    self.assertEquals(unshown, ['Mstone', 'Priority', 'Visibility'])

  def testComputeUnshownColumns_FieldDefs(self):
    search_results = [
        fake.MakeTestIssue(
            789, 1, 'sum 1', 'New', 111,
            field_values=[
                tracker_bizobj.MakeFieldValue(
                    5, 74, None, None, None, None, False, phase_id=4),
                tracker_bizobj.MakeFieldValue(
                    6, 78, None, None, None, None, False, phase_id=5)],
            phases=[
                tracker_pb2.Phase(phase_id=4, name='goats'),
                tracker_pb2.Phase(phase_id=5, name='sheep')]),
        fake.MakeTestIssue(
            789, 2, 'sum 2', 'New', 111,
            field_values=[
                tracker_bizobj.MakeFieldValue(
                    5, 74, None, None, None, None, False, phase_id=3),
                tracker_bizobj.MakeFieldValue(
                    6, 77, None, None, None, None, False, phase_id=3)],
            phases=[
                tracker_pb2.Phase(phase_id=3, name='Goats'),
                tracker_pb2.Phase(phase_id=3, name='Goats-Exp')]),
    ]

    shown_cols = ['a', 'b', 'a1', 'a2-approver', 'f3', 'goats.g1', 'sheep.g2']
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    config.default_col_spec = ''
    config.well_known_labels = []
    config.field_defs = [
      tracker_bizobj.MakeFieldDef(
          1, 789, 'a1', tracker_pb2.FieldTypes.APPROVAL_TYPE,
          None, None, False, False, False, None, None, None, False, None,
          None, None, None, 'Tracks review from cows', False),
      tracker_bizobj.MakeFieldDef(
          2, 789, 'a2', tracker_pb2.FieldTypes.APPROVAL_TYPE,
          None, None, False, False, False, None, None, None, False, None,
          None, None, None, 'Tracks review from chickens', False),
      tracker_bizobj.MakeFieldDef(
          3, 789, 'f3', tracker_pb2.FieldTypes.STR_TYPE,
          None, None, False, False, False, None, None, None, False, None,
          None, None, None, 'cow names', False),
      tracker_bizobj.MakeFieldDef(
          4, 789, 'f4', tracker_pb2.FieldTypes.INT_TYPE,
          None, None, False, False, False, None, None, None, False, None,
          None, None, None, 'chicken gobbles', False),
      tracker_bizobj.MakeFieldDef(
          5, 789, 'g1', tracker_pb2.FieldTypes.INT_TYPE,
          None, None, False, False, False, None, None, None, False, None,
          None, None, None, 'fluff', False, is_phase_field=True),
      tracker_bizobj.MakeFieldDef(
          6, 789, 'g2', tracker_pb2.FieldTypes.INT_TYPE,
          None, None, False, False, False, None, None, None, False, None,
          None, None, None, 'poof', False, is_phase_field=True),
    ]
    builtin_cols = []

    unshown = table_view_helpers.ComputeUnshownColumns(
        search_results, shown_cols, config, builtin_cols)
    self.assertEqual(unshown, [
        'a1-approver', 'a2', 'f4',
        'goats-exp.g1', 'goats-exp.g2', 'goats.g2', 'sheep.g1'])

  def testExtractUniqueValues_NoColumns(self):
    column_values = table_view_helpers.ExtractUniqueValues(
        [], SEARCH_RESULTS_WITH_LABELS, {}, self.config, {})
    self.assertEquals([], column_values)

  def testExtractUniqueValues_NoResults(self):
    cols = ['type', 'priority', 'owner', 'status', 'stars', 'attachments']
    column_values = table_view_helpers.ExtractUniqueValues(
        cols, EMPTY_SEARCH_RESULTS, {}, self.config, {})
    self.assertEquals(6, len(column_values))
    for index, col in enumerate(cols):
      self.assertEquals(index, column_values[index].col_index)
      self.assertEquals(col, column_values[index].column_name)
      self.assertEquals([], column_values[index].filter_values)

  def testExtractUniqueValues_ExplicitResults(self):
    cols = ['priority', 'owner', 'status', 'stars', 'mstone', 'foo']
    users_by_id = {
        111: framework_views.StuffUserView(111, 'foo@example.com', True),
        }
    column_values = table_view_helpers.ExtractUniqueValues(
        cols, SEARCH_RESULTS_WITH_LABELS, users_by_id, self.config, {})
    self.assertEquals(len(cols), len(column_values))

    self.assertEquals('priority', column_values[0].column_name)
    self.assertEquals(['High', 'Low'], column_values[0].filter_values)

    self.assertEquals('owner', column_values[1].column_name)
    self.assertEquals(['f...@example.com'], column_values[1].filter_values)

    self.assertEquals('status', column_values[2].column_name)
    self.assertEquals(['New'], column_values[2].filter_values)

    self.assertEquals('stars', column_values[3].column_name)
    self.assertEquals([1], column_values[3].filter_values)

    self.assertEquals('mstone', column_values[4].column_name)
    self.assertEquals(['1', '1.1'], column_values[4].filter_values)

    self.assertEquals('foo', column_values[5].column_name)
    self.assertEquals([], column_values[5].filter_values)

    # self.assertEquals('mergedinto', column_values[6].column_name)
    # self.assertEquals(
    #    ['1', 'other-project:1'], column_values[6].filter_values)

  def testExtractUniqueValues_CombinedColumns(self):
    cols = ['priority/pri', 'owner', 'status', 'stars', 'mstone/milestone']
    users_by_id = {
        111: framework_views.StuffUserView(111, 'foo@example.com', True),
        }
    issue = fake.MakeTestIssue(
        789, 5, 'sum 5', 'New', 111, merged_into=200001,
        labels='Priority-High Pri-0 Milestone-1.0 mstone-1',
        star_count=15)

    column_values = table_view_helpers.ExtractUniqueValues(
        cols, SEARCH_RESULTS_WITH_LABELS + [issue], users_by_id,
        self.config, {})
    self.assertEquals(5, len(column_values))

    self.assertEquals('priority/pri', column_values[0].column_name)
    self.assertEquals(['0', 'High', 'Low'], column_values[0].filter_values)

    self.assertEquals('owner', column_values[1].column_name)
    self.assertEquals(['f...@example.com'], column_values[1].filter_values)

    self.assertEquals('status', column_values[2].column_name)
    self.assertEquals(['New'], column_values[2].filter_values)

    self.assertEquals('stars', column_values[3].column_name)
    self.assertEquals([1, 15], column_values[3].filter_values)

    self.assertEquals('mstone/milestone', column_values[4].column_name)
    self.assertEquals(['1', '1.0', '1.1'], column_values[4].filter_values)

  def testExtractUniqueValues_DerivedValues(self):
    cols = ['priority', 'milestone', 'owner', 'status']
    users_by_id = {
        111: framework_views.StuffUserView(111, 'foo@example.com', True),
        222: framework_views.StuffUserView(222, 'bar@example.com', True),
        333: framework_views.StuffUserView(333, 'lol@example.com', True),
        }
    search_results = [
        fake.MakeTestIssue(
            789, 1, 'sum 1', '', 111, labels='Priority-High Milestone-1.0',
            derived_labels='Milestone-2.0 Foo', derived_status='Started'),
        fake.MakeTestIssue(
            789, 2, 'sum 2', 'New', 111, labels='Priority-High Milestone-1.0',
            derived_owner_id=333),  # Not seen because of owner_id
        fake.MakeTestIssue(
            789, 3, 'sum 3', 'New', 0, labels='Priority-Low Milestone-1.1',
            derived_owner_id=222),
        ]

    column_values = table_view_helpers.ExtractUniqueValues(
        cols, search_results, users_by_id, self.config, {})
    self.assertEquals(4, len(column_values))

    self.assertEquals('priority', column_values[0].column_name)
    self.assertEquals(['High', 'Low'], column_values[0].filter_values)

    self.assertEquals('milestone', column_values[1].column_name)
    self.assertEquals(['1.0', '1.1', '2.0'],
                      column_values[1].filter_values)

    self.assertEquals('owner', column_values[2].column_name)
    self.assertEquals(['b...@example.com', 'f...@example.com'],
                      column_values[2].filter_values)

    self.assertEquals('status', column_values[3].column_name)
    self.assertEquals(['New', 'Started'], column_values[3].filter_values)

  def testExtractUniqueValues_ColumnsRobustness(self):
    cols = ['reporter', 'cc', 'owner', 'status', 'attachments']
    search_results = [
        tracker_pb2.Issue(),
        ]
    column_values = table_view_helpers.ExtractUniqueValues(
        cols, search_results, {}, self.config, {})

    self.assertEquals(5, len(column_values))
    for col_val in column_values:
      if col_val.column_name == 'attachments':
        self.assertEquals([0], col_val.filter_values)
      else:
        self.assertEquals([], col_val.filter_values)

  def testMakeTableData_Empty(self):
    visible_results = []
    lower_columns = []
    cell_factories = {}
    table_data = table_view_helpers.MakeTableData(
        visible_results, [], lower_columns, lower_columns,
        cell_factories, [], 'unused function', {}, self.config)
    self.assertEqual([], table_data)

    lower_columns = ['type', 'priority', 'summary', 'stars']
    cell_factories = {
        'summary': table_view_helpers.TableCellSummary,
        'stars': table_view_helpers.TableCellStars,
        }

    table_data = table_view_helpers.MakeTableData(
        visible_results, [], lower_columns, [], {},
        cell_factories, 'unused function', {}, self.config)
    self.assertEqual([], table_data)

  def testMakeTableData_Normal(self):
    art = fake.MakeTestIssue(
        789, 1, 'sum 1', 'New', 111, labels='Type-Defect Priority-Medium')
    visible_results = [art]
    lower_columns = ['type', 'priority', 'summary', 'stars']
    cell_factories = {
        'summary': table_view_helpers.TableCellSummary,
        'stars': table_view_helpers.TableCellStars,
        }

    table_data = table_view_helpers.MakeTableData(
        visible_results, [], lower_columns, lower_columns, {},
        cell_factories, lambda art: 'id', {}, self.config)
    self.assertEqual(1, len(table_data))
    row = table_data[0]
    self.assertEqual(4, len(row.cells))
    self.assertEqual('Defect', row.cells[0].values[0].item)

  def testMakeTableData_Groups(self):
    art = fake.MakeTestIssue(
        789, 1, 'sum 1', 'New', 111, labels='Type-Defect Priority-Medium')
    visible_results = [art]
    lower_columns = ['type', 'priority', 'summary', 'stars']
    lower_group_by = ['priority']
    cell_factories = {
        'summary': table_view_helpers.TableCellSummary,
        'stars': table_view_helpers.TableCellStars,
        }

    table_data = table_view_helpers.MakeTableData(
        visible_results, [], lower_columns, lower_group_by, {},
        cell_factories, lambda art: 'id', {}, self.config)
    self.assertEqual(1, len(table_data))
    row = table_data[0]
    self.assertEqual(1, len(row.group.cells))
    self.assertEqual('Medium', row.group.cells[0].values[0].item)

  def testMakeRowData(self):
    art = fake.MakeTestIssue(
        789, 1, 'sum 1', 'New', 111, labels='Type-Defect Priority-Medium',
        star_count=1)
    columns = ['type', 'priority', 'summary', 'stars']

    cell_factories = [table_view_helpers.TableCellKeyLabels,
                      table_view_helpers.TableCellKeyLabels,
                      table_view_helpers.TableCellSummary,
                      table_view_helpers.TableCellStars]

    # a result is an table_view_helpers.TableRow object with a "cells" field
    # containing a list of table_view_helpers.TableCell objects.
    result = table_view_helpers.MakeRowData(
        art, columns, {}, cell_factories, {}, self.config, {})

    self.assertEqual(len(columns), len(result.cells))

    for i in range(len(columns)):
      cell = result.cells[i]
      self.assertEqual(i, cell.col_index)

    self.assertEqual(table_view_helpers.CELL_TYPE_ATTR, result.cells[0].type)
    self.assertEqual('Defect', result.cells[0].values[0].item)
    self.assertFalse(result.cells[0].values[0].is_derived)

    self.assertEqual(table_view_helpers.CELL_TYPE_ATTR, result.cells[1].type)
    self.assertEqual('Medium', result.cells[1].values[0].item)
    self.assertFalse(result.cells[1].values[0].is_derived)

    self.assertEqual(
        table_view_helpers.CELL_TYPE_SUMMARY, result.cells[2].type)
    self.assertEqual('sum 1', result.cells[2].values[0].item)
    self.assertFalse(result.cells[2].values[0].is_derived)

    self.assertEqual(table_view_helpers.CELL_TYPE_ATTR, result.cells[3].type)
    self.assertEqual(1, result.cells[3].values[0].item)
    self.assertFalse(result.cells[3].values[0].is_derived)

  def testAccumulateLabelValues_Empty(self):
    label_values, non_col_labels = collections.defaultdict(list), []
    table_view_helpers._AccumulateLabelValues(
        [], [], label_values, non_col_labels)
    self.assertEqual({}, label_values)
    self.assertEqual([], non_col_labels)

    label_values, non_col_labels = collections.defaultdict(list), []
    table_view_helpers._AccumulateLabelValues(
        [], ['Type', 'Priority'], label_values, non_col_labels)
    self.assertEqual({}, label_values)
    self.assertEqual([], non_col_labels)

  def testAccumulateLabelValues_OneWordLabels(self):
    label_values, non_col_labels = collections.defaultdict(list), []
    table_view_helpers._AccumulateLabelValues(
        ['HelloThere'], [], label_values, non_col_labels)
    self.assertEqual({}, label_values)
    self.assertEqual([('HelloThere', False)], non_col_labels)

    label_values, non_col_labels = collections.defaultdict(list), []
    table_view_helpers._AccumulateLabelValues(
        ['HelloThere'], [], label_values, non_col_labels, is_derived=True)
    self.assertEqual({}, label_values)
    self.assertEqual([('HelloThere', True)], non_col_labels)

  def testAccumulateLabelValues_KeyValueLabels(self):
    label_values, non_col_labels = collections.defaultdict(list), []
    table_view_helpers._AccumulateLabelValues(
        ['Type-Defect', 'Milestone-Soon'], ['type', 'milestone'],
        label_values, non_col_labels)
    self.assertEqual(
        {'type': [('Defect', False)],
         'milestone': [('Soon', False)]},
        label_values)
    self.assertEqual([], non_col_labels)

  def testAccumulateLabelValues_MultiValueLabels(self):
    label_values, non_col_labels = collections.defaultdict(list), []
    table_view_helpers._AccumulateLabelValues(
        ['OS-Mac', 'OS-Linux'], ['os', 'arch'],
        label_values, non_col_labels)
    self.assertEqual(
        {'os': [('Mac', False), ('Linux', False)]},
        label_values)
    self.assertEqual([], non_col_labels)

  def testAccumulateLabelValues_MultiPartLabels(self):
    label_values, non_col_labels = collections.defaultdict(list), []
    table_view_helpers._AccumulateLabelValues(
        ['OS-Mac-Server', 'OS-Mac-Laptop'], ['os', 'os-mac'],
        label_values, non_col_labels)
    self.assertEqual(
        {'os': [('Mac-Server', False), ('Mac-Laptop', False)],
         'os-mac': [('Server', False), ('Laptop', False)],
         },
        label_values)
    self.assertEqual([], non_col_labels)

  def testChooseCellFactory(self):
    """We choose the right kind of table cell for the specified column."""
    cell_factories = {
      'summary': table_view_helpers.TableCellSummary,
      'stars': table_view_helpers.TableCellStars,
      }
    os_fd = tracker_bizobj.MakeFieldDef(
        1, 789, 'os', tracker_pb2.FieldTypes.ENUM_TYPE, None, None, False,
        False, False, None, None, None, False, None, None, None, None,
        'Operating system', False)
    deadline_fd = tracker_bizobj.MakeFieldDef(
        2, 789, 'deadline', tracker_pb2.FieldTypes.DATE_TYPE, None, None, False,
        False, False, None, None, None, False, None, None, None, None,
        'Deadline to resolve issue', False)
    approval_fd = tracker_bizobj.MakeFieldDef(
        3, 789, 'CowApproval', tracker_pb2.FieldTypes.APPROVAL_TYPE,
        None, None, False,
        False, False, None, None, None, False, None, None, None, None,
        'Tracks reviews from cows', False)
    goats_fd = tracker_bizobj.MakeFieldDef(
        4, 789, 'goats', tracker_pb2.FieldTypes.INT_TYPE, None, None, False,
        False, False, None, None, None, False, None, None, None, None,
        'Num goats in each phase', False, is_phase_field=True)
    self.config.field_defs = [os_fd, deadline_fd, approval_fd, goats_fd]

    # The column is defined in cell_factories.
    actual = table_view_helpers.ChooseCellFactory(
        'summary', cell_factories, self.config)
    self.assertEqual(table_view_helpers.TableCellSummary, actual)

    # The column is a composite column.
    actual = table_view_helpers.ChooseCellFactory(
        'summary/stars', cell_factories, self.config)
    self.assertEqual('FactoryClass', actual.__name__)

    # The column is a enum custom field, so it is treated like a label.
    actual = table_view_helpers.ChooseCellFactory(
        'os', cell_factories, self.config)
    self.assertEqual(table_view_helpers.TableCellKeyLabels, actual)

    # The column is a non-enum custom field.
    actual = table_view_helpers.ChooseCellFactory(
        'deadline', cell_factories, self.config)
    self.assertEqual(
      [(table_view_helpers.TableCellCustom, 'deadline'),
       (table_view_helpers.TableCellKeyLabels, 'deadline')],
      actual.factory_col_list)

    # The column is an approval custom field.
    actual = table_view_helpers.ChooseCellFactory(
        'CowApproval', cell_factories, self.config)
    self.assertEqual(
        [(table_view_helpers.TableCellApprovalStatus, 'CowApproval'),
         (table_view_helpers.TableCellKeyLabels, 'CowApproval')],
        actual.factory_col_list)

    # The column is an approval custom field with '-approver'.
    actual = table_view_helpers.ChooseCellFactory(
        'CowApproval-approver', cell_factories, self.config)
    self.assertEqual(
        [(table_view_helpers.TableCellApprovalApprover, 'CowApproval-approver'),
         (table_view_helpers.TableCellKeyLabels, 'CowApproval-approver')],
        actual.factory_col_list)

    # The column specifies a phase custom field.
    actual = table_view_helpers.ChooseCellFactory(
        'winter.goats', cell_factories, self.config)
    self.assertEqual(
         [(table_view_helpers.TableCellCustom, 'winter.goats'),
          (table_view_helpers.TableCellKeyLabels, 'winter.goats')],
         actual.factory_col_list)


    # Column that don't match one of the other cases is assumed to be a label.
    actual = table_view_helpers.ChooseCellFactory(
        'reward', cell_factories, self.config)
    self.assertEqual(table_view_helpers.TableCellKeyLabels, actual)

  def testCompositeFactoryTableCell_Empty(self):
    """If we made a composite of zero columns, it would have no values."""
    composite = table_view_helpers.CompositeFactoryTableCell([])
    cell = composite('artifact')
    self.assertEqual([], cell.values)

  def testCompositeFactoryTableCell_Normal(self):
    """If we make a composite, it has values from each of the sub cells."""
    composite = table_view_helpers.CompositeFactoryTableCell(
        [(sub_factory_1, 'col1'),
         (sub_factory_2, 'col2')])

    cell = composite('artifact')
    self.assertEqual(
        ['sub_cell_1_col1',
         'sub_cell_2_col2'],
        cell.values)

  def testCompositeColTableCell_Empty(self):
    """If we made a composite of zero columns, it would have no values."""
    composite = table_view_helpers.CompositeColTableCell([], {}, self.config)
    cell = composite('artifact')
    self.assertEqual([], cell.values)


  def testCompositeColTableCell_Normal(self):
    """If we make a composite, it has values from each of the sub cells."""
    composite = table_view_helpers.CompositeColTableCell(
      ['col1', 'col2'],
      {'col1': sub_factory_1, 'col2': sub_factory_2},
      self.config)
    cell = composite('artifact')
    self.assertEqual(
        ['sub_cell_1_col1',
         'sub_cell_2_col2'],
        cell.values)


def sub_factory_1(_art, **kw):
  return testing_helpers.Blank(
      values=['sub_cell_1_%s' % kw['col']],
      non_column_labels=[])


def sub_factory_2(_art, **kw):
  return testing_helpers.Blank(
      values=['sub_cell_2_%s' % kw['col']],
      non_column_labels=[])
