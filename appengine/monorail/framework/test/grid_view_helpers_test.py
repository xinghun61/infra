# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for grid_view_helpers classes and functions."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import framework_constants
from framework import framework_views
from framework import grid_view_helpers
from testing import fake
from tracker import tracker_bizobj


class GridViewHelpersTest(unittest.TestCase):

  def setUp(self):
    self.default_cols = 'a b c'
    self.builtin_cols = 'a b x y z'
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

    self.art1 = fake.MakeTestIssue(
        789, 1, 'a summary', '', 0, derived_owner_id=111, star_count=12,
        derived_labels='Priority-Medium Hot Mstone-1 Mstone-2',
        derived_status='Overdue')
    self.art2 = fake.MakeTestIssue(
        789, 1, 'a summary', 'New', 111, star_count=12, merged_into=200001,
        labels='Priority-Medium Type-DEFECT Hot Mstone-1 Mstone-2')
    self.users_by_id = {
        111: framework_views.StuffUserView(111, 'foo@example.com', True),
        }

  def testSortGridHeadings(self):
    config = fake.MakeTestConfig(
        789, labels=('Priority-High Priority-Medium Priority-Low Hot Cold '
                     'Milestone-Near Milestone-Far'),
        statuses=('New Accepted Started Fixed WontFix Invalid Duplicate'))
    asc_accessors = {
        'id': 'some function that is not called',
        'reporter': 'some function that is not called',
        'opened': 'some function that is not called',
        'modified': 'some function that is not called',
        }

    # Verify that status headings are sorted according to the status
    # values defined in the config.
    col_name = 'status'
    headings = ['Duplicate', 'Limbo', 'New', 'OnHold', 'Accepted', 'Fixed']
    sorted_headings = grid_view_helpers.SortGridHeadings(
        col_name, headings, self.users_by_id, config, asc_accessors)
    self.assertEqual(
        sorted_headings,
        ['New', 'Accepted', 'Fixed', 'Duplicate', 'Limbo', 'OnHold'])

    # Verify that special columns are sorted alphabetically.
    col_name = 'id'
    headings = [1, 2, 5, 3, 4]
    sorted_headings = grid_view_helpers.SortGridHeadings(
        col_name, headings, self.users_by_id, config, asc_accessors)
    self.assertEqual(sorted_headings,
                     [1, 2, 3, 4, 5])

    # Verify that label value headings are sorted according to the labels
    # values defined in the config.
    col_name = 'priority'
    headings = ['Medium', 'High', 'Low', 'dont-care']
    sorted_headings = grid_view_helpers.SortGridHeadings(
        col_name, headings, self.users_by_id, config, asc_accessors)
    self.assertEqual(sorted_headings,
                     ['High', 'Medium', 'Low', 'dont-care'])

  def testGetArtifactAttr_Explicit(self):
    label_values = grid_view_helpers.MakeLabelValuesDict(self.art2)

    id_vals = grid_view_helpers.GetArtifactAttr(
        self.art2, 'id', self.users_by_id, label_values, self.config, {})
    self.assertEqual([1], id_vals)
    summary_vals = grid_view_helpers.GetArtifactAttr(
        self.art2, 'summary', self.users_by_id, label_values, self.config, {})
    self.assertEqual(['a summary'], summary_vals)
    status_vals = grid_view_helpers.GetArtifactAttr(
        self.art2, 'status', self.users_by_id, label_values, self.config, {})
    self.assertEqual(['New'], status_vals)
    stars_vals = grid_view_helpers.GetArtifactAttr(
        self.art2, 'stars', self.users_by_id, label_values, self.config, {})
    self.assertEqual([12], stars_vals)
    owner_vals = grid_view_helpers.GetArtifactAttr(
        self.art2, 'owner', self.users_by_id, label_values, self.config, {})
    self.assertEqual(['f...@example.com'], owner_vals)
    priority_vals = grid_view_helpers.GetArtifactAttr(
        self.art2, 'priority', self.users_by_id, label_values, self.config, {})
    self.assertEqual(['Medium'], priority_vals)
    mstone_vals = grid_view_helpers.GetArtifactAttr(
        self.art2, 'mstone', self.users_by_id, label_values, self.config, {})
    self.assertEqual(['1', '2'], mstone_vals)
    foo_vals = grid_view_helpers.GetArtifactAttr(
        self.art2, 'foo', self.users_by_id, label_values, self.config, {})
    self.assertEqual([framework_constants.NO_VALUES], foo_vals)
    art3 = fake.MakeTestIssue(
        987, 5, 'unecessary summary', 'New', 111, star_count=12,
        issue_id=200001, project_name='other-project')
    related_issues = {200001: art3}
    merged_into_vals = grid_view_helpers.GetArtifactAttr(
        self.art2, 'mergedinto', self.users_by_id, label_values,
        self.config, related_issues)
    self.assertEqual(['other-project:5'], merged_into_vals)

  def testGetArtifactAttr_Derived(self):
    label_values = grid_view_helpers.MakeLabelValuesDict(self.art1)
    status_vals = grid_view_helpers.GetArtifactAttr(
        self.art1, 'status', self.users_by_id, label_values, self.config, {})
    self.assertEqual(['Overdue'], status_vals)
    owner_vals = grid_view_helpers.GetArtifactAttr(
        self.art1, 'owner', self.users_by_id, label_values, self.config, {})
    self.assertEqual(['f...@example.com'], owner_vals)
    priority_vals = grid_view_helpers.GetArtifactAttr(
        self.art1, 'priority', self.users_by_id, label_values, self.config, {})
    self.assertEqual(['Medium'], priority_vals)
    mstone_vals = grid_view_helpers.GetArtifactAttr(
        self.art1, 'mstone', self.users_by_id, label_values, self.config, {})
    self.assertEqual(['1', '2'], mstone_vals)

  def testMakeLabelValuesDict_Empty(self):
    art = fake.MakeTestIssue(
        789, 1, 'a summary', '', 0, derived_owner_id=111, star_count=12)
    label_values = grid_view_helpers.MakeLabelValuesDict(art)
    self.assertEqual({}, label_values)

  def testMakeLabelValuesDict(self):
    art = fake.MakeTestIssue(
        789, 1, 'a summary', '', 0, derived_owner_id=111, star_count=12,
        labels=['Priority-Medium', 'Hot', 'Mstone-1', 'Mstone-2'])
    label_values = grid_view_helpers.MakeLabelValuesDict(art)
    self.assertEqual(
        {'priority': ['Medium'], 'mstone': ['1', '2']},
        label_values)

    art = fake.MakeTestIssue(
        789, 1, 'a summary', '', 0, derived_owner_id=111, star_count=12,
        labels='Priority-Medium Hot Mstone-1'.split(),
        derived_labels=['Mstone-2'])
    label_values = grid_view_helpers.MakeLabelValuesDict(art)
    self.assertEqual(
        {'priority': ['Medium'], 'mstone': ['1', '2']},
        label_values)

  def testMakeDrillDownSearch(self):
    self.assertEqual('-has:milestone ',
                     grid_view_helpers.MakeDrillDownSearch('milestone', '----'))
    self.assertEqual('milestone=22 ',
                     grid_view_helpers.MakeDrillDownSearch('milestone', '22'))
    self.assertEqual(
        'owner=a@example.com ',
        grid_view_helpers.MakeDrillDownSearch('owner', 'a@example.com'))

  def testAnyArtifactHasNoAttr_Empty(self):
    artifacts = []
    all_label_values = {}
    self.assertFalse(grid_view_helpers.AnyArtifactHasNoAttr(
        artifacts, 'milestone', self.users_by_id, all_label_values,
        self.config, {}))

  def testAnyArtifactHasNoAttr(self):
    artifacts = [self.art1]
    all_label_values = {
        self.art1.local_id: grid_view_helpers.MakeLabelValuesDict(self.art1),
        }
    self.assertFalse(grid_view_helpers.AnyArtifactHasNoAttr(
        artifacts, 'mstone', self.users_by_id, all_label_values,
        self.config, {}))
    self.assertTrue(grid_view_helpers.AnyArtifactHasNoAttr(
        artifacts, 'milestone', self.users_by_id, all_label_values,
        self.config, {}))

  def testGetGridViewData(self):
    # TODO(jojwang): write this test
    pass

  def testPrepareForMakeGridData(self):
    # TODO(jojwang): write this test
    pass
