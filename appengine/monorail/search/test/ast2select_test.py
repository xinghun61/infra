# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the ast2select module."""

import unittest

from proto import ast_pb2
from proto import tracker_pb2
from search import ast2select
from search import query2ast
from tracker import tracker_bizobj


BUILTIN_ISSUE_FIELDS = query2ast.BUILTIN_ISSUE_FIELDS
ANY_FIELD = query2ast.BUILTIN_ISSUE_FIELDS['any_field']


class AST2SelectTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

  def testBuildSQLQuery_EmptyAST(self):
    ast = ast_pb2.QueryAST(conjunctions=[ast_pb2.Conjunction()])  # No conds
    left_joins, where = ast2select.BuildSQLQuery(ast)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)

  def testBuildSQLQuery_Normal(self):
    owner_field = BUILTIN_ISSUE_FIELDS['owner']
    reporter_id_field = BUILTIN_ISSUE_FIELDS['reporter_id']
    conds = [
        ast_pb2.MakeCond(
            ast_pb2.QueryOp.TEXT_HAS, [owner_field], ['example.com'], []),
        ast_pb2.MakeCond(
            ast_pb2.QueryOp.EQ, [reporter_id_field], [], [111L])]
    ast = ast_pb2.QueryAST(conjunctions=[ast_pb2.Conjunction(conds=conds)])
    left_joins, where = ast2select.BuildSQLQuery(ast)
    self.assertEqual(
        [('User AS Cond0 ON (Issue.owner_id = Cond0.user_id '
          'OR Issue.derived_owner_id = Cond0.user_id)', [])],
        left_joins)
    self.assertEqual(
        [('(LOWER(Cond0.email) LIKE %s)', ['%example.com%']),
         ('Issue.reporter_id = %s', [111L])],
        where)

  def testBlockingIDCond_SingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [fd], ['1'], [])
    num_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1L])

    for cond, expected in ((txt_cond, '1'), (num_cond, 1L)):
      left_joins, where = ast2select._ProcessBlockingIDCond(
          cond, 'Cond1', 'Issue1')
      self.assertEqual(
          [('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
            'Cond1.kind = %s AND Cond1.issue_id = %s',
            ['blockedon', expected])],
          left_joins)
      self.assertEqual(
          [('Cond1.dst_issue_id IS NOT NULL', [])],
          where)

  def testBlockingIDCond_NegatedSingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NE, [fd], ['1'], [])
    num_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1L])

    for cond, expected in ((txt_cond, '1'), (num_cond, 1L)):
      left_joins, where = ast2select._ProcessBlockingIDCond(
          cond, 'Cond1', 'Issue1')
      self.assertEqual(
          [('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
            'Cond1.kind = %s AND Cond1.issue_id = %s',
            ['blockedon', expected])],
          left_joins)
      self.assertEqual(
          [('Cond1.dst_issue_id IS NULL', [])],
          where)

  def testBlockingIDCond_MultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [fd], ['1', '2', '3'], [])
    num_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1L, 2L, 3L])

    for cond, expected in ((txt_cond, ['1', '2', '3']),
                           (num_cond, [1L, 2L, 3L])):
      left_joins, where = ast2select._ProcessBlockingIDCond(
          cond, 'Cond1', 'Issue1')
      self.assertEqual(
          [('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
            'Cond1.kind = %s AND Cond1.issue_id IN (%s,%s,%s)',
            ['blockedon'] + expected)],
          left_joins)
      self.assertEqual(
          [('Cond1.dst_issue_id IS NOT NULL', [])],
          where)

  def testBlockingIDCond_NegatedMultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NE, [fd], ['1', '2', '3'], [])
    num_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1L, 2L, 3L])

    for cond, expected in ((txt_cond, ['1', '2', '3']),
                           (num_cond, [1L, 2L, 3L])):
      left_joins, where = ast2select._ProcessBlockingIDCond(
          cond, 'Cond1', 'Issue1')
      self.assertEqual(
          [('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
            'Cond1.kind = %s AND Cond1.issue_id IN (%s,%s,%s)',
            ['blockedon'] + expected)],
          left_joins)
      self.assertEqual(
          [('Cond1.dst_issue_id IS NULL', [])],
          where)

  def testBlockedOnIDCond_SingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [fd], ['1'], [])
    num_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1L])

    for cond, expected in ((txt_cond, '1'), (num_cond, 1L)):
      left_joins, where = ast2select._ProcessBlockedOnIDCond(
          cond, 'Cond1', 'Issue1')
      self.assertEqual(
          [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
            'Cond1.kind = %s AND Cond1.dst_issue_id = %s',
            ['blockedon', expected])],
          left_joins)
      self.assertEqual(
          [('Cond1.issue_id IS NOT NULL', [])],
          where)

  def testBlockedOnIDCond_NegatedSingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NE, [fd], ['1'], [])
    num_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1L])

    for cond, expected in ((txt_cond, '1'), (num_cond, 1L)):
      left_joins, where = ast2select._ProcessBlockedOnIDCond(
          cond, 'Cond1', 'Issue1')
      self.assertEqual(
          [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
            'Cond1.kind = %s AND Cond1.dst_issue_id = %s',
            ['blockedon', expected])],
          left_joins)
      self.assertEqual(
          [('Cond1.issue_id IS NULL', [])],
          where)

  def testBlockedIDCond_MultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [fd], ['1', '2', '3'], [])
    num_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1L, 2L, 3L])

    for cond, expected in ((txt_cond, ['1', '2', '3']),
                           (num_cond, [1L, 2L, 3L])):
      left_joins, where = ast2select._ProcessBlockedOnIDCond(
          cond, 'Cond1', 'Issue1')
      self.assertEqual(
          [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
            'Cond1.kind = %s AND Cond1.dst_issue_id IN (%s,%s,%s)',
            ['blockedon'] + expected)],
          left_joins)
      self.assertEqual(
          [('Cond1.issue_id IS NOT NULL', [])],
          where)

  def testBlockedIDCond_NegatedMultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NE, [fd], ['1', '2', '3'], [])
    num_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1L, 2L, 3L])

    for cond, expected in ((txt_cond, ['1', '2', '3']),
                           (num_cond, [1L, 2L, 3L])):
      left_joins, where = ast2select._ProcessBlockedOnIDCond(
          cond, 'Cond1', 'Issue1')
      self.assertEqual(
          [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
            'Cond1.kind = %s AND Cond1.dst_issue_id IN (%s,%s,%s)',
            ['blockedon'] + expected)],
          left_joins)
      self.assertEqual(
          [('Cond1.issue_id IS NULL', [])],
          where)

  def testHasBlockedCond(self):
    for op, expected in ((ast_pb2.QueryOp.IS_DEFINED, 'IS NOT NULL'),
                         (ast_pb2.QueryOp.IS_NOT_DEFINED, 'IS NULL')):
      fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
      cond = ast_pb2.MakeCond(op, [fd], [], [])

      left_joins, where = ast2select._ProcessBlockedOnIDCond(
          cond, 'Cond1', None)
      self.assertEqual(
          [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
            'Cond1.kind = %s', ['blockedon'])],
          left_joins)
      self.assertEqual([('Cond1.issue_id %s' % expected, [])], where)

  def testHasBlockingCond(self):
    for op, expected in ((ast_pb2.QueryOp.IS_DEFINED, 'IS NOT NULL'),
                         (ast_pb2.QueryOp.IS_NOT_DEFINED, 'IS NULL')):
      fd = BUILTIN_ISSUE_FIELDS['blocking_id']
      cond = ast_pb2.MakeCond(op, [fd], [], [])

      left_joins, where = ast2select._ProcessBlockingIDCond(cond, 'Cond1', None)
      self.assertEqual(
          [('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
            'Cond1.kind = %s', ['blockedon'])],
          left_joins)
      self.assertEqual([('Cond1.dst_issue_id %s' % expected, [])], where)

  def testProcessOwnerCond(self):
    fd = BUILTIN_ISSUE_FIELDS['owner']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where = ast2select._ProcessOwnerCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('User AS Cond1 ON (Issue.owner_id = Cond1.user_id '
          'OR Issue.derived_owner_id = Cond1.user_id)', [])],
        left_joins)
    self.assertEqual(
        [('(LOWER(Cond1.email) LIKE %s)', ['%example.com%'])],
        where)

  def testProcessOwnerIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['owner_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111L])
    left_joins, where = ast2select._ProcessOwnerIDCond(cond, 'Cond1', 'User1')
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('(Issue.owner_id = %s OR Issue.derived_owner_id = %s)',
          [111L, 111L])],
        where)

  def testProcessReporterCond(self):
    fd = BUILTIN_ISSUE_FIELDS['reporter']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where = ast2select._ProcessReporterCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('User AS Cond1 ON Issue.reporter_id = Cond1.user_id', [])],
        left_joins)
    self.assertEqual(
        [('(LOWER(Cond1.email) LIKE %s)', ['%example.com%'])],
        where)

  def testProcessReporterIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['reporter_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111L])
    left_joins, where = ast2select._ProcessReporterIDCond(
        cond, 'Cond1', 'User1')
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('Issue.reporter_id = %s', [111L])],
        where)

  def testProcessCcCond_SinglePositive(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where = ast2select._ProcessCcCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('(Issue2Cc AS Cond1 JOIN User AS User1 '
          'ON Cond1.cc_id = User1.user_id AND (LOWER(User1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id AND Issue.shard = Cond1.issue_shard',
          ['%example.com%'])],
        left_joins)
    self.assertEqual(
        [('User1.email IS NOT NULL', [])],
        where)

  def testProcessCcCond_MultiplePositive(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['.com', '.org'], [])
    left_joins, where = ast2select._ProcessCcCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('(Issue2Cc AS Cond1 JOIN User AS User1 '
          'ON Cond1.cc_id = User1.user_id AND '
          '(LOWER(User1.email) LIKE %s OR LOWER(User1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id AND Issue.shard = Cond1.issue_shard',
          ['%.com%', '%.org%'])],
        left_joins)
    self.assertEqual(
        [('User1.email IS NOT NULL', [])],
        where)

  def testProcessCcCond_SingleNegative(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NOT_TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where = ast2select._ProcessCcCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('(Issue2Cc AS Cond1 JOIN User AS User1 '
          'ON Cond1.cc_id = User1.user_id AND (LOWER(User1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id AND Issue.shard = Cond1.issue_shard',
          ['%example.com%'])],
        left_joins)
    self.assertEqual(
        [('User1.email IS NULL', [])],
        where)

  def testProcessCcCond_Multiplenegative(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NOT_TEXT_HAS, [fd], ['.com', '.org'], [])
    left_joins, where = ast2select._ProcessCcCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('(Issue2Cc AS Cond1 JOIN User AS User1 '
          'ON Cond1.cc_id = User1.user_id AND '
          '(LOWER(User1.email) LIKE %s OR LOWER(User1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id AND Issue.shard = Cond1.issue_shard',
          ['%.com%', '%.org%'])],
        left_joins)
    self.assertEqual(
        [('User1.email IS NULL', [])],
        where)

  def testProcessCcIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['cc_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111L])
    left_joins, where = ast2select._ProcessCcIDCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('Issue2Cc AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.cc_id = %s',
         [111L])],
        left_joins)
    self.assertEqual(
        [('Cond1.cc_id IS NOT NULL', [])],
        where)

  def testProcessStarredByCond(self):
    fd = BUILTIN_ISSUE_FIELDS['starredby']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where = ast2select._ProcessStarredByCond(
        cond, 'Cond1', 'User1')
    self.assertEqual(
        [('(IssueStar AS Cond1 JOIN User AS User1 '
          'ON Cond1.user_id = User1.user_id AND (LOWER(User1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id', ['%example.com%'])],
        left_joins)
    self.assertEqual(
        [('User1.email IS NOT NULL', [])],
        where)

  def testProcessStarredByIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['starredby_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111L])
    left_joins, where = ast2select._ProcessStarredByIDCond(
        cond, 'Cond1', 'User1')
    self.assertEqual(
        [('IssueStar AS Cond1 ON Issue.id = Cond1.issue_id '
          'AND Cond1.user_id = %s', [111L])],
        left_joins)
    self.assertEqual(
        [('Cond1.user_id IS NOT NULL', [])],
        where)

  def testProcessCommentByCond(self):
    fd = BUILTIN_ISSUE_FIELDS['commentby']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where = ast2select._ProcessCommentByCond(
        cond, 'Cond1', 'User1')
    self.assertEqual(
        [('(Comment AS Cond1 JOIN User AS User1 '
          'ON Cond1.commenter_id = User1.user_id '
          'AND (LOWER(User1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id', ['%example.com%'])],
        left_joins)
    self.assertEqual(
        [('User1.email IS NOT NULL', [])],
        where)

  def testProcessCommentByIDCond_EqualsUserID(self):
    fd = BUILTIN_ISSUE_FIELDS['commentby_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111L])
    left_joins, where = ast2select._ProcessCommentByIDCond(
        cond, 'Cond1', 'User1')
    self.assertEqual(
        [('Comment AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.commenter_id = %s',
          [111L])],
        left_joins)
    self.assertEqual(
        [('Cond1.commenter_id IS NOT NULL', [])],
        where)

  def testProcessCommentByIDCond_NotEqualsUserID(self):
    fd = BUILTIN_ISSUE_FIELDS['commentby_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [111L])
    left_joins, where = ast2select._ProcessCommentByIDCond(
        cond, 'Cond1', 'User1')
    self.assertEqual(
        [('Comment AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.commenter_id = %s',
          [111L])],
        left_joins)
    self.assertEqual(
        [('Cond1.commenter_id IS NULL', [])],
        where)

  def testProcessStatusIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['status_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [2])
    left_joins, where = ast2select._ProcessStatusIDCond(cond, 'Cond1', 'User1')
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('(Issue.status_id = %s OR Issue.derived_status_id = %s)', [2, 2])],
        where)

  def testProcessLabelIDCond_NoValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [])
    with self.assertRaises(ast2select.NoPossibleResults):
      ast2select._ProcessLabelIDCond(cond, 'Cond1', 'User1')

  def testProcessLabelIDCond_SingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1])
    left_joins, where = ast2select._ProcessLabelIDCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('Issue2Label AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.label_id = %s', [1])],
        left_joins)
    self.assertEqual(
        [('Cond1.label_id IS NOT NULL', [])],
        where)

  def testProcessLabelIDCond_MultipleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1, 2])
    left_joins, where = ast2select._ProcessLabelIDCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('Issue2Label AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.label_id IN (%s,%s)', [1, 2])],
        left_joins)
    self.assertEqual(
        [('Cond1.label_id IS NOT NULL', [])],
        where)

  def testProcessLabelIDCond_NegatedNoValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [])
    left_joins, where = ast2select._ProcessLabelIDCond(cond, 'Cond1', 'User1')
    self.assertEqual([], left_joins)
    self.assertEqual([], where)

  def testProcessLabelIDCond_NegatedSingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1])
    left_joins, where = ast2select._ProcessLabelIDCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('Issue2Label AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.label_id = %s', [1])],
        left_joins)
    self.assertEqual(
        [('Cond1.label_id IS NULL', [])],
        where)

  def testProcessLabelIDCond_NegatedMultipleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1, 2])
    left_joins, where = ast2select._ProcessLabelIDCond(cond, 'Cond1', 'User1')
    self.assertEqual(
        [('Issue2Label AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.label_id IN (%s,%s)', [1, 2])],
        left_joins)
    self.assertEqual(
        [('Cond1.label_id IS NULL', [])],
        where)

  def testProcessComponentIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['component_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [101])
    left_joins, where = ast2select._ProcessComponentIDCond(
        cond, 'Cond1', 'User1')
    self.assertEqual(
        [('Issue2Component AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.component_id = %s', [101])],
        left_joins)
    self.assertEqual(
        [('Cond1.component_id IS NOT NULL', [])],
        where)

  def testProcessCustomFieldCond(self):
    pass  # TODO(jrobbins): fill in this test case.

  def testProcessAttachmentCond_HasAttachment(self):
    fd = BUILTIN_ISSUE_FIELDS['attachment']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.IS_DEFINED, [fd], [], [])
    left_joins, where = ast2select._ProcessAttachmentCond(
        cond, 'Cond1', 'User1')
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('(Issue.attachment_count IS NOT NULL AND '
          'Issue.attachment_count != %s)',
          [0])],
        where)

    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.IS_NOT_DEFINED, [fd], [], [])
    left_joins, where = ast2select._ProcessAttachmentCond(
        cond, 'Cond1', 'User1')
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('(Issue.attachment_count IS NULL OR '
          'Issue.attachment_count = %s)',
          [0])],
        where)

  def testProcessAttachmentCond_TextHas(self):
    fd = BUILTIN_ISSUE_FIELDS['attachment']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.TEXT_HAS, [fd], ['jpg'], [])
    left_joins, where = ast2select._ProcessAttachmentCond(
        cond, 'Cond1', 'User1')
    self.assertEqual(
        [('Attachment AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.deleted = %s',
          [False])],
        left_joins)
    self.assertEqual(
        [('(Cond1.filename LIKE %s)', ['%jpg%'])],
        where)

  def testCompare_IntTypes(self):
    val_type = tracker_pb2.FieldTypes.INT_TYPE
    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.IS_DEFINED, val_type, 'col', [1, 2])
    self.assertEqual('(Alias.col IS NOT NULL AND Alias.col != %s)', cond_str)
    self.assertEqual([0], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.EQ, val_type, 'col', [1])
    self.assertEqual('Alias.col = %s', cond_str)
    self.assertEqual([1], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.EQ, val_type, 'col', [1, 2])
    self.assertEqual('Alias.col IN (%s,%s)', cond_str)
    self.assertEqual([1, 2], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', [])
    self.assertEqual('TRUE', cond_str)
    self.assertEqual([], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', [1])
    self.assertEqual('(Alias.col IS NULL OR Alias.col != %s)', cond_str)
    self.assertEqual([1], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', [1, 2])
    self.assertEqual('(Alias.col IS NULL OR Alias.col NOT IN (%s,%s))',
                     cond_str)
    self.assertEqual([1, 2], cond_args)

  def testCompare_STRTypes(self):
    val_type = tracker_pb2.FieldTypes.STR_TYPE
    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.IS_DEFINED, val_type, 'col', ['a', 'b'])
    self.assertEqual('(Alias.col IS NOT NULL AND Alias.col != %s)', cond_str)
    self.assertEqual([''], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.EQ, val_type, 'col', ['a'])
    self.assertEqual('Alias.col = %s', cond_str)
    self.assertEqual(['a'], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.EQ, val_type, 'col', ['a', 'b'])
    self.assertEqual('Alias.col IN (%s,%s)', cond_str)
    self.assertEqual(['a', 'b'], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', [])
    self.assertEqual('TRUE', cond_str)
    self.assertEqual([], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', ['a'])
    self.assertEqual('(Alias.col IS NULL OR Alias.col != %s)', cond_str)
    self.assertEqual(['a'], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', ['a', 'b'])
    self.assertEqual('(Alias.col IS NULL OR Alias.col NOT IN (%s,%s))',
                     cond_str)
    self.assertEqual(['a', 'b'], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.TEXT_HAS, val_type, 'col', ['a'])
    self.assertEqual('(Alias.col LIKE %s)', cond_str)
    self.assertEqual(['%a%'], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NOT_TEXT_HAS, val_type, 'col', ['a'])
    self.assertEqual('(Alias.col IS NULL OR Alias.col NOT LIKE %s)', cond_str)
    self.assertEqual(['%a%'], cond_args)

  def testCompareAlreadyJoined(self):
    cond_str, cond_args = ast2select._CompareAlreadyJoined(
        'Alias', ast_pb2.QueryOp.EQ, 'col')
    self.assertEqual('Alias.col IS NOT NULL', cond_str)
    self.assertEqual([], cond_args)

    cond_str, cond_args = ast2select._CompareAlreadyJoined(
        'Alias', ast_pb2.QueryOp.NE, 'col')
    self.assertEqual('Alias.col IS NULL', cond_str)
    self.assertEqual([], cond_args)
