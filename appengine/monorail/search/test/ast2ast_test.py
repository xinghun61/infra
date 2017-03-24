# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the ast2ast module."""

import unittest

from proto import ast_pb2
from proto import tracker_pb2
from search import ast2ast
from search import query2ast
from services import service_manager
from testing import fake
from tracker import tracker_bizobj


BUILTIN_ISSUE_FIELDS = query2ast.BUILTIN_ISSUE_FIELDS
ANY_FIELD = query2ast.BUILTIN_ISSUE_FIELDS['any_field']
OWNER_FIELD = query2ast.BUILTIN_ISSUE_FIELDS['owner']
OWNER_ID_FIELD = query2ast.BUILTIN_ISSUE_FIELDS['owner_id']


class AST2ASTTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.config.component_defs.append(
        tracker_bizobj.MakeComponentDef(
            101, 789, 'UI', 'doc', False, [], [], 0, 0))
    self.config.component_defs.append(
        tracker_bizobj.MakeComponentDef(
            102, 789, 'UI>Search', 'doc', False, [], [], 0, 0))
    self.config.component_defs.append(
        tracker_bizobj.MakeComponentDef(
            201, 789, 'DB', 'doc', False, [], [], 0, 0))
    self.config.component_defs.append(
        tracker_bizobj.MakeComponentDef(
            301, 789, 'Search', 'doc', False, [], [], 0, 0))
    self.services = service_manager.Services(
        user=fake.UserService(),
        project=fake.ProjectService(),
        issue=fake.IssueService(),
        config=fake.ConfigService())
    self.services.user.TestAddUser('a@example.com', 111L)

  def testPreprocessAST_EmptyAST(self):
    ast = ast_pb2.QueryAST()  # No conjunctions in it.
    new_ast = ast2ast.PreprocessAST(
        self.cnxn, ast, [789], self.services, self.config)
    self.assertEqual(ast, new_ast)

  def testPreprocessAST_Normal(self):
    open_field = BUILTIN_ISSUE_FIELDS['open']
    label_field = BUILTIN_ISSUE_FIELDS['label']
    label_id_field = BUILTIN_ISSUE_FIELDS['label_id']
    status_id_field = BUILTIN_ISSUE_FIELDS['status_id']
    conds = [
        ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [open_field], [], []),
        ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [label_field], ['Hot'], [])]

    ast = ast_pb2.QueryAST()
    ast.conjunctions.append(ast_pb2.Conjunction(conds=conds))
    new_ast = ast2ast.PreprocessAST(
        self.cnxn, ast, [789], self.services, self.config)
    self.assertEqual(2, len(new_ast.conjunctions[0].conds))
    new_cond_1, new_cond_2 = new_ast.conjunctions[0].conds
    self.assertEqual(ast_pb2.QueryOp.NE, new_cond_1.op)
    self.assertEqual([status_id_field], new_cond_1.field_defs)
    self.assertEqual([7, 8, 9], new_cond_1.int_values)
    self.assertEqual([], new_cond_1.str_values)
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond_2.op)
    self.assertEqual([label_id_field], new_cond_2.field_defs)
    self.assertEqual([0], new_cond_2.int_values)
    self.assertEqual([], new_cond_2.str_values)

  def testPreprocessIsOpenCond(self):
    open_field = BUILTIN_ISSUE_FIELDS['open']
    status_id_field = BUILTIN_ISSUE_FIELDS['status_id']

    # is:open  -> status_id!=closed_status_ids
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [open_field], [], [])
    new_cond = ast2ast._PreprocessIsOpenCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.NE, new_cond.op)
    self.assertEqual([status_id_field], new_cond.field_defs)
    self.assertEqual([7, 8, 9], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

    # -is:open  -> status_id=closed_status_ids
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NE, [open_field], [], [])
    new_cond = ast2ast._PreprocessIsOpenCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual([status_id_field], new_cond.field_defs)
    self.assertEqual([7, 8, 9], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

  def testPreprocessBlockedOnCond_WithSingleProjectID(self):
    blockedon_field = BUILTIN_ISSUE_FIELDS['blockedon']
    blockedon_id_field = BUILTIN_ISSUE_FIELDS['blockedon_id']
    self.services.project.TestAddProject('Project1', project_id=1)
    issue1 = fake.MakeTestIssue(
        project_id=1, local_id=1, summary='sum', status='new', owner_id=2,
        issue_id=101)
    issue2 = fake.MakeTestIssue(
        project_id=1, local_id=2, summary='sum', status='new', owner_id=2,
        issue_id=102)
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)

    for local_ids, expected in (
        (['1'], [101]),  # One existing issue.
        (['Project1:1'], [101]),  # One existing issue with project prefix.
        (['1', '2'], [101, 102]),  # Two existing issues.
        (['3'], [])):  # Non-existant issue.
      cond = ast_pb2.MakeCond(
          ast_pb2.QueryOp.TEXT_HAS, [blockedon_field], local_ids, [])
      new_cond = ast2ast._PreprocessBlockedOnCond(
          self.cnxn, cond, [1], self.services, None)
      self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
      self.assertEqual([blockedon_id_field], new_cond.field_defs)
      self.assertEqual(expected, new_cond.int_values)
      self.assertEqual([], new_cond.str_values)

  def testPreprocessBlockedOnCond_WithMultipleProjectIDs(self):
    blockedon_field = BUILTIN_ISSUE_FIELDS['blockedon']
    blockedon_id_field = BUILTIN_ISSUE_FIELDS['blockedon_id']
    self.services.project.TestAddProject('Project1', project_id=1)
    self.services.project.TestAddProject('Project2', project_id=2)
    issue1 = fake.MakeTestIssue(
        project_id=1, local_id=1, summary='sum', status='new', owner_id=2,
        issue_id=101)
    issue2 = fake.MakeTestIssue(
        project_id=2, local_id=2, summary='sum', status='new', owner_id=2,
        issue_id=102)
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)

    for local_ids, expected in (
        (['Project1:1'], [101]),
        (['Project1:1', 'Project2:2'], [101, 102])):
      cond = ast_pb2.MakeCond(
          ast_pb2.QueryOp.TEXT_HAS, [blockedon_field], local_ids, [])
      new_cond = ast2ast._PreprocessBlockedOnCond(
          self.cnxn, cond, [1, 2], self.services, None)
      self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
      self.assertEqual([blockedon_id_field], new_cond.field_defs)
      self.assertEqual(expected, new_cond.int_values)
      self.assertEqual([], new_cond.str_values)

  def testPreprocessBlockedOnCond_WithMultipleProjectIDs_NoPrefix(self):
    blockedon_field = BUILTIN_ISSUE_FIELDS['blockedon']
    self.services.project.TestAddProject('Project1', project_id=1)
    self.services.project.TestAddProject('Project2', project_id=2)
    issue1 = fake.MakeTestIssue(
        project_id=1, local_id=1, summary='sum', status='new', owner_id=2,
        issue_id=101)
    issue2 = fake.MakeTestIssue(
        project_id=2, local_id=2, summary='sum', status='new', owner_id=2,
        issue_id=102)
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)

    for local_ids in (['1'], ['1', '2'], ['3']):
      cond = ast_pb2.MakeCond(
          ast_pb2.QueryOp.TEXT_HAS, [blockedon_field], local_ids, [])
      with self.assertRaises(ValueError) as cm:
        ast2ast._PreprocessBlockedOnCond(
            self.cnxn, cond, [1, 2], self.services, None)
      self.assertEquals(
          'Searching for issues accross multiple/all projects without '
          'project prefixes is ambiguous and is currently not supported.',
          cm.exception.message)

  def testPreprocessIsBlockedCond(self):
    blocked_field = BUILTIN_ISSUE_FIELDS['blockedon_id']
    for input_op, expected_op in (
        (ast_pb2.QueryOp.EQ, ast_pb2.QueryOp.IS_DEFINED),
        (ast_pb2.QueryOp.NE, ast_pb2.QueryOp.IS_NOT_DEFINED)):
      cond = ast_pb2.MakeCond(
          input_op, [blocked_field], [], [])
      new_cond = ast2ast._PreprocessIsBlockedCond(
          self.cnxn, cond, [100], self.services, None)
      self.assertEqual(expected_op, new_cond.op)
      self.assertEqual([blocked_field], new_cond.field_defs)
      self.assertEqual([], new_cond.int_values)
      self.assertEqual([], new_cond.str_values)

  def testPreprocessHasBlockedOnCond(self):
    blocked_field = BUILTIN_ISSUE_FIELDS['blockedon_id']
    for op in (ast_pb2.QueryOp.IS_DEFINED, ast_pb2.QueryOp.IS_NOT_DEFINED):
      cond = ast_pb2.MakeCond(op, [blocked_field], [], [])
      new_cond = ast2ast._PreprocessBlockedOnCond(
          self.cnxn, cond, [100], self.services, None)
      self.assertEqual(op, op)
      self.assertEqual([blocked_field], new_cond.field_defs)
      self.assertEqual([], new_cond.int_values)
      self.assertEqual([], new_cond.str_values)

  def testPreprocessHasBlockingCond(self):
    blocking_field = BUILTIN_ISSUE_FIELDS['blocking_id']
    for op in (ast_pb2.QueryOp.IS_DEFINED, ast_pb2.QueryOp.IS_NOT_DEFINED):
      cond = ast_pb2.MakeCond(op, [blocking_field], [], [])
      new_cond = ast2ast._PreprocessBlockingCond(
          self.cnxn, cond, [100], self.services, None)
      self.assertEqual(op, op)
      self.assertEqual([blocking_field], new_cond.field_defs)
      self.assertEqual([], new_cond.int_values)
      self.assertEqual([], new_cond.str_values)

  def testPreprocessBlockingCond_WithSingleProjectID(self):
    blocking_field = BUILTIN_ISSUE_FIELDS['blocking']
    blocking_id_field = BUILTIN_ISSUE_FIELDS['blocking_id']
    self.services.project.TestAddProject('Project1', project_id=1)
    issue1 = fake.MakeTestIssue(
        project_id=1, local_id=1, summary='sum', status='new', owner_id=2,
        issue_id=101)
    issue2 = fake.MakeTestIssue(
        project_id=1, local_id=2, summary='sum', status='new', owner_id=2,
        issue_id=102)
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)

    for local_ids, expected in (
        (['1'], [101]),  # One existing issue.
        (['Project1:1'], [101]),  # One existing issue with project prefix.
        (['1', '2'], [101, 102]),  # Two existing issues.
        (['3'], [])):  # Non-existant issue.
      cond = ast_pb2.MakeCond(
          ast_pb2.QueryOp.TEXT_HAS, [blocking_field], local_ids, [])
      new_cond = ast2ast._PreprocessBlockingCond(
          self.cnxn, cond, [1], self.services, None)
      self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
      self.assertEqual([blocking_id_field], new_cond.field_defs)
      self.assertEqual(expected, new_cond.int_values)
      self.assertEqual([], new_cond.str_values)

  def testPreprocessBlockingCond_WithMultipleProjectIDs(self):
    blocking_field = BUILTIN_ISSUE_FIELDS['blocking']
    blocking_id_field = BUILTIN_ISSUE_FIELDS['blocking_id']
    self.services.project.TestAddProject('Project1', project_id=1)
    self.services.project.TestAddProject('Project2', project_id=2)
    issue1 = fake.MakeTestIssue(
        project_id=1, local_id=1, summary='sum', status='new', owner_id=2,
        issue_id=101)
    issue2 = fake.MakeTestIssue(
        project_id=2, local_id=2, summary='sum', status='new', owner_id=2,
        issue_id=102)
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)

    for local_ids, expected in (
        (['Project1:1'], [101]),
        (['Project1:1', 'Project2:2'], [101, 102])):
      cond = ast_pb2.MakeCond(
          ast_pb2.QueryOp.TEXT_HAS, [blocking_field], local_ids, [])
      new_cond = ast2ast._PreprocessBlockingCond(
          self.cnxn, cond, [1, 2], self.services, None)
      self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
      self.assertEqual([blocking_id_field], new_cond.field_defs)
      self.assertEqual(expected, new_cond.int_values)
      self.assertEqual([], new_cond.str_values)

  def testPreprocessBlockingCond_WithMultipleProjectIDs_NoPrefix(self):
    blocking_field = BUILTIN_ISSUE_FIELDS['blocking']
    self.services.project.TestAddProject('Project1', project_id=1)
    self.services.project.TestAddProject('Project2', project_id=2)
    issue1 = fake.MakeTestIssue(
        project_id=1, local_id=1, summary='sum', status='new', owner_id=2,
        issue_id=101)
    issue2 = fake.MakeTestIssue(
        project_id=2, local_id=2, summary='sum', status='new', owner_id=2,
        issue_id=102)
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)

    for local_ids in (['1'], ['1', '2'], ['3']):
      cond = ast_pb2.MakeCond(
          ast_pb2.QueryOp.TEXT_HAS, [blocking_field], local_ids, [])
      with self.assertRaises(ValueError) as cm:
        ast2ast._PreprocessBlockingCond(
            self.cnxn, cond, [1, 2], self.services, None)
      self.assertEquals(
        'Searching for issues accross multiple/all projects without '
        'project prefixes is ambiguous and is currently not supported.',
        cm.exception.message)

  def testPreprocessMergedIntoCond_WithSingleProjectID(self):
    field = BUILTIN_ISSUE_FIELDS['mergedinto']
    id_field = BUILTIN_ISSUE_FIELDS['mergedinto_id']
    self.services.project.TestAddProject('Project1', project_id=1)
    issue1 = fake.MakeTestIssue(
        project_id=1, local_id=1, summary='sum', status='new', owner_id=2,
        issue_id=101)
    issue2 = fake.MakeTestIssue(
        project_id=1, local_id=2, summary='sum', status='new', owner_id=2,
        issue_id=102)
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)

    for local_ids, expected in (
        (['1'], [101]),  # One existing issue.
        (['Project1:1'], [101]),  # One existing issue with project prefix.
        (['1', '2'], [101, 102]),  # Two existing issues.
        (['3'], [])):  # Non-existant issue.
      cond = ast_pb2.MakeCond(
          ast_pb2.QueryOp.TEXT_HAS, [field], local_ids, [])
      new_cond = ast2ast._PreprocessMergedIntoCond(
          self.cnxn, cond, [1], self.services, None)
      self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
      self.assertEqual([id_field], new_cond.field_defs)
      self.assertEqual(expected, new_cond.int_values)
      self.assertEqual([], new_cond.str_values)

  def testPreprocessIsSpamCond(self):
    spam_field = BUILTIN_ISSUE_FIELDS['spam']
    is_spam_field = BUILTIN_ISSUE_FIELDS['is_spam']
    for input_op, int_values in (
        (ast_pb2.QueryOp.EQ, [1]), (ast_pb2.QueryOp.NE, [0])):
      cond = ast_pb2.MakeCond(
          input_op, [spam_field], [], [])
      new_cond = ast2ast._PreprocessIsSpamCond(
          self.cnxn, cond, [789], self.services, None)
      self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
      self.assertEqual([is_spam_field], new_cond.field_defs)
      self.assertEqual(int_values, new_cond.int_values)
      self.assertEqual([], new_cond.str_values)

  def testPreprocessStatusCond(self):
    status_field = BUILTIN_ISSUE_FIELDS['status']
    status_id_field = BUILTIN_ISSUE_FIELDS['status_id']

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.IS_DEFINED, [status_field], [], [])
    new_cond = ast2ast._PreprocessStatusCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.IS_DEFINED, new_cond.op)
    self.assertEqual([status_id_field], new_cond.field_defs)
    self.assertEqual([], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [status_field], ['New', 'Assigned'], [])
    new_cond = ast2ast._PreprocessStatusCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual([status_id_field], new_cond.field_defs)
    self.assertEqual([0, 1], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [status_field], [], [])
    new_cond = ast2ast._PreprocessStatusCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual([], new_cond.int_values)

  def testPrefixRegex(self):
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.IS_DEFINED, [BUILTIN_ISSUE_FIELDS['label']],
        ['Priority', 'Severity'], [])
    regex = ast2ast._MakePrefixRegex(cond)
    self.assertRegexpMatches('Priority-1', regex)
    self.assertRegexpMatches('Severity-3', regex)
    self.assertNotRegexpMatches('My-Priority', regex)

  def testKeyValueRegex(self):
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.KEY_HAS, [BUILTIN_ISSUE_FIELDS['label']],
        ['Type-Feature', 'Type-Security'], [])
    regex = ast2ast._MakeKeyValueRegex(cond)
    self.assertRegexpMatches('Type-Feature', regex)
    self.assertRegexpMatches('Type-Bug-Security', regex)
    self.assertNotRegexpMatches('Type-Bug', regex)
    self.assertNotRegexpMatches('Security-Feature', regex)

  def testKeyValueRegex_multipleKeys(self):
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.KEY_HAS, [BUILTIN_ISSUE_FIELDS['label']],
        ['Type-Bug', 'Security-Bug'], [])
    with self.assertRaises(ValueError):
      ast2ast._MakeKeyValueRegex(cond)

  def testWordBoundryRegex(self):
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [BUILTIN_ISSUE_FIELDS['label']],
        ['Type-Bug'], [])
    regex = ast2ast._MakeKeyValueRegex(cond)
    self.assertRegexpMatches('Type-Bug-Security', regex)
    self.assertNotRegexpMatches('Type-BugSecurity', regex)

  def testPreprocessLabelCond(self):
    label_field = BUILTIN_ISSUE_FIELDS['label']
    label_id_field = BUILTIN_ISSUE_FIELDS['label_id']

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.IS_DEFINED, [label_field], ['Priority'], [])
    new_cond = ast2ast._PreprocessLabelCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.IS_DEFINED, new_cond.op)
    self.assertEqual([label_id_field], new_cond.field_defs)
    self.assertEqual([1, 2, 3], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [label_field],
        ['Priority-Low', 'Priority-High'], [])
    new_cond = ast2ast._PreprocessLabelCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual([label_id_field], new_cond.field_defs)
    self.assertEqual([0, 1], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.KEY_HAS, [label_field],
        ['Priority-Low', 'Priority-High'], [])
    new_cond = ast2ast._PreprocessLabelCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual([label_id_field], new_cond.field_defs)
    self.assertEqual([1, 2, 3], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

  def testPreprocessComponentCond_QuickOR(self):
    component_field = BUILTIN_ISSUE_FIELDS['component']
    component_id_field = BUILTIN_ISSUE_FIELDS['component_id']

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.IS_DEFINED, [component_field], ['UI', 'DB'], [])
    new_cond = ast2ast._PreprocessComponentCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.IS_DEFINED, new_cond.op)
    self.assertEqual([component_id_field], new_cond.field_defs)
    self.assertEqual([101, 102, 201], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [component_field], ['UI', 'DB'], [])
    new_cond = ast2ast._PreprocessComponentCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual([component_id_field], new_cond.field_defs)
    self.assertEqual([101, 102, 201], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [component_field], [], [])
    new_cond = ast2ast._PreprocessComponentCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual([], new_cond.int_values)

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [component_field], ['unknown@example.com'],
        [])
    new_cond = ast2ast._PreprocessComponentCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual([], new_cond.int_values)

  def testPreprocessComponentCond_RootedAndNonRooted(self):
    component_field = BUILTIN_ISSUE_FIELDS['component']
    component_id_field = BUILTIN_ISSUE_FIELDS['component_id']

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [component_field], ['UI'], [])
    new_cond = ast2ast._PreprocessComponentCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual([component_id_field], new_cond.field_defs)
    self.assertEqual([101, 102], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [component_field], ['UI'], [])
    new_cond = ast2ast._PreprocessComponentCond(
        self.cnxn, cond, [789], self.services, self.config)
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual([component_id_field], new_cond.field_defs)
    self.assertEqual([101], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

  def testPreprocessExactUsers_IsDefined(self):
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.IS_DEFINED, [OWNER_FIELD], ['a@example.com'], [])
    new_cond = ast2ast._PreprocessExactUsers(
        self.cnxn, cond, self.services.user, [OWNER_ID_FIELD])
    self.assertEqual(ast_pb2.QueryOp.IS_DEFINED, new_cond.op)
    self.assertEqual([OWNER_ID_FIELD], new_cond.field_defs)
    self.assertEqual([], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

  def testPreprocessExactUsers_UserFound(self):
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [OWNER_FIELD], ['a@example.com'], [])
    new_cond = ast2ast._PreprocessExactUsers(
        self.cnxn, cond, self.services.user, [OWNER_ID_FIELD])
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual([OWNER_ID_FIELD], new_cond.field_defs)
    self.assertEqual([111L], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

  def testPreprocessExactUsers_UserSpecifiedByID(self):
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [OWNER_FIELD], ['123'], [])
    new_cond = ast2ast._PreprocessExactUsers(
        self.cnxn, cond, self.services.user, [OWNER_ID_FIELD])
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual([OWNER_ID_FIELD], new_cond.field_defs)
    self.assertEqual([123L], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

  def testPreprocessExactUsers_NonEquality(self):
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.GE, [OWNER_ID_FIELD], ['111'], [])
    new_cond = ast2ast._PreprocessExactUsers(
        self.cnxn, cond, self.services.user, [OWNER_ID_FIELD])
    self.assertEqual(cond, new_cond)

  def testPreprocessExactUsers_UserNotFound(self):
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [OWNER_FIELD], ['unknown@example.com'], [])
    new_cond = ast2ast._PreprocessExactUsers(
        self.cnxn, cond, self.services.user, [OWNER_ID_FIELD])
    self.assertEqual(cond, new_cond)

  def testPreprocessCustomCond_User(self):
    fd = tracker_pb2.FieldDef(
        field_id=1, field_name='TPM',
        field_type=tracker_pb2.FieldTypes.USER_TYPE)
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['a@example.com'], [])
    new_cond = ast2ast._PreprocessCustomCond(self.cnxn, cond, self.services)
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual(cond.field_defs, new_cond.field_defs)
    self.assertEqual([111L], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['111'], [])
    new_cond = ast2ast._PreprocessCustomCond(self.cnxn, cond, self.services)
    self.assertEqual(ast_pb2.QueryOp.EQ, new_cond.op)
    self.assertEqual(cond.field_defs, new_cond.field_defs)
    self.assertEqual([111L], new_cond.int_values)
    self.assertEqual([], new_cond.str_values)

    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['unknown@example.com'], [])
    new_cond = ast2ast._PreprocessCustomCond(self.cnxn, cond, self.services)
    self.assertEqual(cond, new_cond)

  def testPreprocessCustomCond_NonUser(self):
    fd = tracker_pb2.FieldDef(
        field_id=1, field_name='TPM',
        field_type=tracker_pb2.FieldTypes.INT_TYPE)
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['foo'], [123])
    new_cond = ast2ast._PreprocessCustomCond(self.cnxn, cond, self.services)
    self.assertEqual(cond, new_cond)

    fd.field_type = tracker_pb2.FieldTypes.STR_TYPE
    new_cond = ast2ast._PreprocessCustomCond(self.cnxn, cond, self.services)
    self.assertEqual(cond, new_cond)

  def testPreprocessCond_NoChange(self):
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.TEXT_HAS, [ANY_FIELD], ['foo'], [])
    self.assertEqual(
        cond, ast2ast._PreprocessCond(self.cnxn, cond, [], None, None))

  def testTextOpToIntOp(self):
    self.assertEqual(ast_pb2.QueryOp.EQ,
                     ast2ast._TextOpToIntOp(ast_pb2.QueryOp.TEXT_HAS))
    self.assertEqual(ast_pb2.QueryOp.EQ,
                     ast2ast._TextOpToIntOp(ast_pb2.QueryOp.KEY_HAS))
    self.assertEqual(ast_pb2.QueryOp.NE,
                     ast2ast._TextOpToIntOp(ast_pb2.QueryOp.NOT_TEXT_HAS))

    for enum_name, _enum_id in ast_pb2.QueryOp.to_dict().iteritems():
      no_change_op = ast_pb2.QueryOp(enum_name)
      if no_change_op not in (
          ast_pb2.QueryOp.TEXT_HAS,
          ast_pb2.QueryOp.NOT_TEXT_HAS,
          ast_pb2.QueryOp.KEY_HAS):
        self.assertEqual(no_change_op,
                         ast2ast._TextOpToIntOp(no_change_op))
