# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the ast2sort module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import tracker_pb2
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
        [('User AS {alias}_exp ON Issue.owner_id = {alias}_exp.user_id', []),
         ('User AS {alias}_der ON '
          'Issue.derived_owner_id = {alias}_der.user_id', [])],
        left_joins)
    self.assertEqual(
        [('(ISNULL({alias}_exp.email) AND ISNULL({alias}_der.email)) '
          '{sort_dir}', []),
         ('CONCAT({alias}_exp.email, {alias}_der.email) {sort_dir}', [])],
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

  def testProcessCustomAndLabelSD_PhaseField(self):
    harmonized_labels = []
    bear_fd = tracker_pb2.FieldDef(
        field_id=1, field_name='DropBear', project_id=789,
        field_type=tracker_pb2.FieldTypes.INT_TYPE)
    bear2_fd = tracker_pb2.FieldDef(
        field_id=2, field_name='DropBear', project_id=788,
        field_type=tracker_pb2.FieldTypes.STR_TYPE)
    koala_fd = tracker_pb2.FieldDef(
        field_id=3, field_name='koala', project_id=789,
        field_type=tracker_pb2.FieldTypes.INT_TYPE)
    bear_app_fd = tracker_pb2.FieldDef(
        field_id=4, field_name='dropbear', project_id=789,
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    harmonized_fields = [bear_fd, bear2_fd, koala_fd, bear_app_fd]
    phase_name = 'stable'
    alias = 'Sort0'
    sort_dir = 'DESC'
    sd = 'stable.dropbear'
    left_joins, order_by = ast2sort._ProcessCustomAndLabelSD(
        sd, harmonized_labels, harmonized_fields, alias, sort_dir,
        self.fmt)

    expected_joins = []
    expected_order = []
    int_left_joins, int_order_by = ast2sort._CustomFieldSortClauses(
        [bear_fd, bear2_fd], tracker_pb2.FieldTypes.INT_TYPE, 'int_value',
        alias, sort_dir, phase_name=phase_name)
    str_left_joins, str_order_by = ast2sort._CustomFieldSortClauses(
        [bear_fd, bear2_fd], tracker_pb2.FieldTypes.STR_TYPE, 'str_value',
        alias, sort_dir, phase_name=phase_name)
    user_left_joins, user_order_by = ast2sort._CustomFieldSortClauses(
        [bear_fd, bear2_fd], tracker_pb2.FieldTypes.USER_TYPE, 'user_id',
        alias, sort_dir, phase_name=phase_name)
    label_left_joinss, label_order_by = ast2sort._LabelSortClauses(
        sd, harmonized_labels, self.fmt)
    expected_joins.extend(
        int_left_joins + str_left_joins + user_left_joins + label_left_joinss)
    expected_order.extend(
        int_order_by + str_order_by + user_order_by + label_order_by)
    self.assertEqual(left_joins, expected_joins)
    self.assertEqual(order_by, expected_order)

  def testApprovalFieldSortClauses_Status(self):
    approval_fd_list = [
        tracker_pb2.FieldDef(field_id=2, project_id=789,
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
        tracker_pb2.FieldDef(field_id=4, project_id=788,
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    ]
    left_joins, order_by = ast2sort._ApprovalFieldSortClauses(
        approval_fd_list, '-status', self.fmt)

    self.assertEqual(
        [('{tbl_name} AS {alias}_approval '
          'ON Issue.id = {alias}_approval.issue_id '
          'AND {alias}_approval.approval_id IN ({approval_ids_ph})', [2, 4])],
        left_joins)

    self.assertEqual(
        [('FIELD({alias}_approval.status, {approval_status_ph}) {rev_sort_dir}',
          ast2sort.APPROVAL_STATUS_SORT_ORDER)],
        order_by)

  def testApprovalFieldSortClauses_Approver(self):
    approval_fd_list = [
        tracker_pb2.FieldDef(field_id=2, project_id=789,
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
        tracker_pb2.FieldDef(field_id=4, project_id=788,
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    ]
    left_joins, order_by = ast2sort._ApprovalFieldSortClauses(
        approval_fd_list, '-approver', self.fmt)

    self.assertEqual(
        [('{tbl_name} AS {alias}_approval '
          'ON Issue.id = {alias}_approval.issue_id '
          'AND {alias}_approval.approval_id IN ({approval_ids_ph})', [2, 4]),
         ('User AS {alias}_approval_user '
          'ON {alias}_approval.approver_id = {alias}_approval_user.user_id',
          [])],
        left_joins)

    self.assertEqual(
        [('ISNULL({alias}_approval_user.email) {sort_dir}', []),
         ('{alias}_approval_user.email {sort_dir}', [])],
        order_by)

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

  def testCustomFieldSortClauses_Normal(self):
    fd_list = [
      tracker_pb2.FieldDef(field_id=1, project_id=789,
                           field_type=tracker_pb2.FieldTypes.INT_TYPE),
      tracker_pb2.FieldDef(field_id=2, project_id=788,
                           field_type=tracker_pb2.FieldTypes.STR_TYPE),
    ]
    left_joins, order_by = ast2sort._CustomFieldSortClauses(
        fd_list, tracker_pb2.FieldTypes.INT_TYPE, 'int_value', 'Sort0', 'DESC')

    self.assertEqual(
        left_joins, [
            ('Issue2FieldValue AS Sort0_int_value '
             'ON Issue.id = Sort0_int_value.issue_id '
             'AND Sort0_int_value.field_id IN (%s)', [1]),
        ])
    self.assertEqual(
        order_by, [
            ('ISNULL(Sort0_int_value.int_value) DESC', []),
            ('Sort0_int_value.int_value DESC', []),
        ])

  def testCustomFieldSortClauses_PhaseUser(self):
    fd_list = [
      tracker_pb2.FieldDef(field_id=1, project_id=789,
                           field_type=tracker_pb2.FieldTypes.INT_TYPE),
      tracker_pb2.FieldDef(field_id=2, project_id=788,
                           field_type=tracker_pb2.FieldTypes.STR_TYPE),
      tracker_pb2.FieldDef(field_id=3, project_id=788,
                           field_type=tracker_pb2.FieldTypes.USER_TYPE),
    ]
    left_joins, order_by = ast2sort._CustomFieldSortClauses(
        fd_list, tracker_pb2.FieldTypes.USER_TYPE, 'user_id', 'Sort0', 'DESC',
        phase_name='Stable')

    self.assertEqual(
        left_joins, [
            ('Issue2FieldValue AS Sort0_user_id '
             'ON Issue.id = Sort0_user_id.issue_id '
             'AND Sort0_user_id.field_id IN (%s)', [3]),
            ('IssuePhaseDef AS Sort0_user_id_phase '
             'ON Sort0_user_id.phase_id = Sort0_user_id_phase.id '
             'AND LOWER(Sort0_user_id_phase.name) = LOWER(%s)', ['Stable']),
            ('User AS Sort0_user_id_user '
             'ON Sort0_user_id.user_id = Sort0_user_id_user.user_id', []),
        ])
    self.assertEqual(
        order_by, [
            ('ISNULL(Sort0_user_id_user.email) DESC', []),
            ('Sort0_user_id_user.email DESC', []),
        ])

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
