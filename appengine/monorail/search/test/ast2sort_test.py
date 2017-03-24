# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the ast2sort module."""

import unittest

from search import ast2sort
from search import query2ast


BUILTIN_ISSUE_FIELDS = query2ast.BUILTIN_ISSUE_FIELDS
ANY_FIELD = query2ast.BUILTIN_ISSUE_FIELDS['any_field']


class AST2SortTest(unittest.TestCase):

  def setUp(self):
    self.harmonized_labels = [
        (101, 0, 'Hot'), (102, 1, 'Cold'), (103, None, 'Odd')]
    self.harmonized_statuses = [
        (201, 0, 'New'), (202, 1, 'Assigned'), (203, None, 'OnHold')]
    self.harmonized_fields = []
    self.fmt = lambda string, **kwords: string

  def testBuildSortClauses_EmptySortDirectives(self):
    left_joins, order_by = ast2sort.BuildSortClauses(
        [], self.harmonized_labels, self.harmonized_statuses,
        self.harmonized_fields)
    self.assertEqual([], left_joins)
    self.assertEqual([], order_by)

  def testBuildSortClauses_Normal(self):
    left_joins, order_by = ast2sort.BuildSortClauses(
        ['stars', 'status', 'pri', 'reporter', 'id'], self.harmonized_labels,
        self.harmonized_statuses, self.harmonized_fields)
    expected_left_joins = [
        ('User AS Sort3 ON Issue.reporter_id = Sort3.user_id', [])]
    expected_order_by = [
        ('Issue.star_count ASC', []),
        ('FIELD(IF(ISNULL(Issue.status_id), Issue.derived_status_id, '
         'Issue.status_id), %s,%s) DESC', [201, 202]),
        ('FIELD(IF(ISNULL(Issue.status_id), Issue.derived_status_id, '
         'Issue.status_id), %s) DESC', [203]),
        ('ISNULL(Sort3.email) ASC', []),
        ('Sort3.email ASC', []),
        ('Issue.local_id ASC', [])]
    self.assertEqual(expected_left_joins, left_joins)
    self.assertEqual(expected_order_by, order_by)

  def testProcessProjectSD(self):
    left_joins, order_by = ast2sort._ProcessProjectSD(self.fmt)
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('Issue.project_id {sort_dir}', [])],
        order_by)

  def testProcessReporterSD(self):
    left_joins, order_by = ast2sort._ProcessReporterSD(self.fmt)
    self.assertEqual(
        [('User AS {alias} ON Issue.reporter_id = {alias}.user_id', [])],
        left_joins)
    self.assertEqual(
        [('ISNULL({alias}.email) {sort_dir}', []),
         ('{alias}.email {sort_dir}', [])],
        order_by)

  def testProcessOwnerSD(self):
    left_joins, order_by = ast2sort._ProcessOwnerSD(self.fmt)
    self.assertEqual(
        [('User AS {alias} ON (Issue.owner_id = {alias}.user_id OR '
          'Issue.derived_owner_id = {alias}.user_id)', [])],
        left_joins)
    self.assertEqual(
        [('ISNULL({alias}.email) {sort_dir}', []),
         ('{alias}.email {sort_dir}', [])],
        order_by)

  def testProcessCcSD(self):
    left_joins, order_by = ast2sort._ProcessCcSD(self.fmt)
    self.assertEqual(
        [('Issue2Cc AS {alias} ON Issue.id = {alias}.issue_id '
          'LEFT JOIN User AS {alias}_user '
          'ON {alias}.cc_id = {alias}_user.user_id', [])],
        left_joins)
    self.assertEqual(
        [('ISNULL({alias}_user.email) {sort_dir}', []),
         ('{alias}_user.email {sort_dir}', [])],
        order_by)

  def testProcessComponentSD(self):
    left_joins, order_by = ast2sort._ProcessComponentSD(self.fmt)
    self.assertEqual(
        [('Issue2Component AS {alias} ON Issue.id = {alias}.issue_id '
          'LEFT JOIN ComponentDef AS {alias}_component '
          'ON {alias}.component_id = {alias}_component.id', [])],
        left_joins)
    self.assertEqual(
        [('ISNULL({alias}_component.path) {sort_dir}', []),
         ('{alias}_component.path {sort_dir}', [])],
        order_by)

  def testProcessSummarySD(self):
    left_joins, order_by = ast2sort._ProcessSummarySD(self.fmt)
    self.assertEqual(
        [('IssueSummary AS {alias} ON Issue.id = {alias}.issue_id', [])],
        left_joins)
    self.assertEqual(
        [('{alias}.summary {sort_dir}', [])],
        order_by)

  def testProcessStatusSD(self):
    pass  # TODO(jrobbins): fill in this test case

  def testProcessBlockedSD(self):
    left_joins, order_by = ast2sort._ProcessBlockedSD(self.fmt)
    self.assertEqual(
        [('IssueRelation AS {alias} ON Issue.id = {alias}.issue_id '
          'AND {alias}.kind = %s', ['blockedon'])],
        left_joins)
    self.assertEqual(
        [('ISNULL({alias}.dst_issue_id) {sort_dir}', [])],
        order_by)

  def testProcessBlockedOnSD(self):
    left_joins, order_by = ast2sort._ProcessBlockedOnSD(self.fmt)
    self.assertEqual(
        [('IssueRelation AS {alias} ON Issue.id = {alias}.issue_id '
          'AND {alias}.kind = %s', ['blockedon'])],
        left_joins)
    self.assertEqual(
        [('ISNULL({alias}.dst_issue_id) {sort_dir}', []),
         ('{alias}.dst_issue_id {sort_dir}', [])],
        order_by)

  def testProcessBlockingSD(self):
    left_joins, order_by = ast2sort._ProcessBlockingSD(self.fmt)
    self.assertEqual(
        [('IssueRelation AS {alias} ON Issue.id = {alias}.dst_issue_id '
          'AND {alias}.kind = %s', ['blockedon'])],
        left_joins)
    self.assertEqual(
        [('ISNULL({alias}.issue_id) {sort_dir}', []),
         ('{alias}.issue_id {sort_dir}', [])],
        order_by)

  def testProcessMergedIntoSD(self):
    left_joins, order_by = ast2sort._ProcessMergedIntoSD(self.fmt)
    self.assertEqual(
        [('IssueRelation AS {alias} ON Issue.id = {alias}.issue_id '
          'AND {alias}.kind = %s', ['mergedinto'])],
        left_joins)
    self.assertEqual(
        [('ISNULL({alias}.dst_issue_id) {sort_dir}', []),
         ('{alias}.dst_issue_id {sort_dir}', [])],
        order_by)

  def testProcessCustomAndLabelSD(self):
    pass  # TODO(jrobbins): fill in this test case

  def testLabelSortClauses_NoSuchLabels(self):
    sd = 'somethingelse'
    harmonized_labels = [
      (101, 0, 'Type-Defect'),
      (102, 1, 'Type-Enhancement'),
      (103, 2, 'Type-Task'),
      (104, 0, 'Priority-High'),
      (199, None, 'Type-Laundry'),
      ]
    left_joins, order_by = ast2sort._LabelSortClauses(
      sd, harmonized_labels, self.fmt)
    self.assertEqual([], left_joins)
    self.assertEqual([], order_by)

  def testLabelSortClauses_Normal(self):
    sd = 'type'
    harmonized_labels = [
      (101, 0, 'Type-Defect'),
      (102, 1, 'Type-Enhancement'),
      (103, 2, 'Type-Task'),
      (104, 0, 'Priority-High'),
      (199, None, 'Type-Laundry'),
      ]
    left_joins, order_by = ast2sort._LabelSortClauses(
      sd, harmonized_labels, self.fmt)
    self.assertEqual(1, len(left_joins))
    self.assertEqual(
      ('Issue2Label AS {alias} ON Issue.id = {alias}.issue_id AND '
       '{alias}.label_id IN ({all_label_ph})',
       [101, 102, 103, 199]),
      left_joins[0])
    self.assertEqual(2, len(order_by))
    self.assertEqual(
      ('FIELD({alias}.label_id, {wk_label_ph}) {rev_sort_dir}',
       [101, 102, 103]),
      order_by[0])
    self.assertEqual(
      ('FIELD({alias}.label_id, {odd_label_ph}) {rev_sort_dir}',
       [199]),
      order_by[1])

  def testOneSortDirective_NativeSortable(self):
    left_joins, order_by = ast2sort._OneSortDirective(
        1, 'opened', self.harmonized_labels, self.harmonized_statuses,
        self.harmonized_fields)
    self.assertEqual([], left_joins)
    self.assertEqual([('Issue.opened ASC', [])], order_by)

    left_joins, order_by = ast2sort._OneSortDirective(
        1, 'stars', self.harmonized_labels, self.harmonized_statuses,
        self.harmonized_fields)
    self.assertEqual([], left_joins)
    self.assertEqual([('Issue.star_count ASC', [])], order_by)

    left_joins, order_by = ast2sort._OneSortDirective(
        1, '-stars', self.harmonized_labels, self.harmonized_statuses,
        self.harmonized_fields)
    self.assertEqual([], left_joins)
    self.assertEqual([('Issue.star_count DESC', [])], order_by)

    left_joins, order_by = ast2sort._OneSortDirective(
        1, 'componentmodified', self.harmonized_labels,
        self.harmonized_statuses, self.harmonized_fields)
    self.assertEqual([], left_joins)
    self.assertEqual([('Issue.component_modified ASC', [])], order_by)
