# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the fulltext_helpers module."""

import unittest

import mox

from google.appengine.api import search

from proto import ast_pb2
from proto import tracker_pb2
from search import query2ast
from services import fulltext_helpers


TEXT_HAS = ast_pb2.QueryOp.TEXT_HAS
NOT_TEXT_HAS = ast_pb2.QueryOp.NOT_TEXT_HAS
GE = ast_pb2.QueryOp.GE


class MockResult(object):

  def __init__(self, doc_id):
    self.doc_id = doc_id


class MockSearchResponse(object):
  """Mock object that can be iterated over in batches."""

  def __init__(self, results, cursor):
    """Constructor.

    Args:
      results: list of strings for document IDs.
      cursor: search.Cursor object, if there are more results to
          retrieve in another round-trip. Or, None if there are not.
    """
    self.results = [MockResult(r) for r in results]
    self.cursor = cursor

  def __iter__(self):
    """The response itself is an iterator over the results."""
    return self.results.__iter__()


class FulltextHelpersTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.any_field_fd = tracker_pb2.FieldDef(
        field_name='any_field', field_type=tracker_pb2.FieldTypes.STR_TYPE)
    self.summary_fd = tracker_pb2.FieldDef(
        field_name='summary', field_type=tracker_pb2.FieldTypes.STR_TYPE)
    self.milestone_fd = tracker_pb2.FieldDef(
        field_name='milestone', field_type=tracker_pb2.FieldTypes.STR_TYPE,
        field_id=123)
    self.fulltext_fields = ['summary']

    self.mock_index = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(search, 'Index')
    self.query = None

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def RecordQuery(self, query):
    self.query = query

  def testBuildFTSQuery_EmptyQueryConjunction(self):
    query_ast_conj = ast_pb2.Conjunction()
    fulltext_query = fulltext_helpers.BuildFTSQuery(
        query_ast_conj, self.fulltext_fields)
    self.assertEqual(None, fulltext_query)

  def testBuildFTSQuery_NoFullTextConditions(self):
    estimated_hours_fd = tracker_pb2.FieldDef(
        field_name='estimate', field_type=tracker_pb2.FieldTypes.INT_TYPE,
        field_id=124)
    query_ast_conj = ast_pb2.Conjunction(conds=[
        ast_pb2.MakeCond(TEXT_HAS, [estimated_hours_fd], [], [40])])
    fulltext_query = fulltext_helpers.BuildFTSQuery(
        query_ast_conj, self.fulltext_fields)
    self.assertEqual(None, fulltext_query)

  def testBuildFTSQuery_Normal(self):
    query_ast_conj = ast_pb2.Conjunction(conds=[
        ast_pb2.MakeCond(TEXT_HAS, [self.summary_fd], ['needle'], []),
        ast_pb2.MakeCond(TEXT_HAS, [self.milestone_fd], ['Q3', 'Q4'], [])])
    fulltext_query = fulltext_helpers.BuildFTSQuery(
        query_ast_conj, self.fulltext_fields)
    self.assertEqual(
        '(summary:"needle") (custom_123:"Q3" OR custom_123:"Q4")',
        fulltext_query)

  def testBuildFTSQuery_WithQuotes(self):
    query_ast_conj = ast_pb2.Conjunction(conds=[
        ast_pb2.MakeCond(TEXT_HAS, [self.summary_fd], ['"needle haystack"'],
                         [])])
    fulltext_query = fulltext_helpers.BuildFTSQuery(
        query_ast_conj, self.fulltext_fields)
    self.assertEqual('(summary:"needle haystack")', fulltext_query)

  def testBuildFTSQuery_IngoreColonInText(self):
    query_ast_conj = ast_pb2.Conjunction(conds=[
        ast_pb2.MakeCond(TEXT_HAS, [self.summary_fd], ['"needle:haystack"'],
                         [])])
    fulltext_query = fulltext_helpers.BuildFTSQuery(
        query_ast_conj, self.fulltext_fields)
    self.assertEqual('(summary:"needle haystack")', fulltext_query)

  def testBuildFTSQuery_InvalidQuery(self):
    query_ast_conj = ast_pb2.Conjunction(conds=[
        ast_pb2.MakeCond(TEXT_HAS, [self.summary_fd], ['haystack"needle'], []),
        ast_pb2.MakeCond(TEXT_HAS, [self.milestone_fd], ['Q3', 'Q4'], [])])
    with self.assertRaises(AssertionError):
      fulltext_helpers.BuildFTSQuery(
          query_ast_conj, self.fulltext_fields)

  def testBuildFTSQuery_SpecialPrefixQuery(self):
    special_prefix = query2ast.NON_OP_PREFIXES[0]

    # Test with summary field.
    query_ast_conj = ast_pb2.Conjunction(conds=[
        ast_pb2.MakeCond(TEXT_HAS, [self.summary_fd],
                         ['%s//google.com' % special_prefix], []),
        ast_pb2.MakeCond(TEXT_HAS, [self.milestone_fd], ['Q3', 'Q4'], [])])
    fulltext_query = fulltext_helpers.BuildFTSQuery(
        query_ast_conj, self.fulltext_fields)
    self.assertEqual(
        '(summary:"%s//google.com") (custom_123:"Q3" OR custom_123:"Q4")' % (
            special_prefix),
        fulltext_query)

    # Test with any field.
    any_fd = tracker_pb2.FieldDef(
        field_name=ast_pb2.ANY_FIELD,
        field_type=tracker_pb2.FieldTypes.STR_TYPE)
    query_ast_conj = ast_pb2.Conjunction(conds=[
        ast_pb2.MakeCond(
            TEXT_HAS, [any_fd], ['%s//google.com' % special_prefix], []),
        ast_pb2.MakeCond(TEXT_HAS, [self.milestone_fd], ['Q3', 'Q4'], [])])
    fulltext_query = fulltext_helpers.BuildFTSQuery(
        query_ast_conj, self.fulltext_fields)
    self.assertEqual(
        '("%s//google.com") (custom_123:"Q3" OR custom_123:"Q4")' % (
            special_prefix),
        fulltext_query)

  def testBuildFTSCondition_IgnoredOperator(self):
    query_cond = ast_pb2.MakeCond(
        GE, [self.summary_fd], ['needle'], [])
    fulltext_query_clause = fulltext_helpers._BuildFTSCondition(
        query_cond, self.fulltext_fields)
    self.assertEqual('', fulltext_query_clause)

  def testBuildFTSCondition_BuiltinField(self):
    query_cond = ast_pb2.MakeCond(
        TEXT_HAS, [self.summary_fd], ['needle'], [])
    fulltext_query_clause = fulltext_helpers._BuildFTSCondition(
        query_cond, self.fulltext_fields)
    self.assertEqual('(summary:"needle")', fulltext_query_clause)

  def testBuildFTSCondition_NonStringField(self):
    est_days_fd = tracker_pb2.FieldDef(
      field_name='EstDays', field_id=123,
      field_type=tracker_pb2.FieldTypes.INT_TYPE)
    query_cond = ast_pb2.MakeCond(
        TEXT_HAS, [est_days_fd], ['needle'], [])
    fulltext_query_clause = fulltext_helpers._BuildFTSCondition(
        query_cond, self.fulltext_fields)
    # Ignore in FTS, this search condition is done in SQL.
    self.assertEqual('', fulltext_query_clause)

  def testBuildFTSCondition_Negatation(self):
    query_cond = ast_pb2.MakeCond(
        NOT_TEXT_HAS, [self.summary_fd], ['needle'], [])
    fulltext_query_clause = fulltext_helpers._BuildFTSCondition(
        query_cond, self.fulltext_fields)
    self.assertEqual('NOT (summary:"needle")', fulltext_query_clause)

  def testBuildFTSCondition_QuickOR(self):
    query_cond = ast_pb2.MakeCond(
        TEXT_HAS, [self.summary_fd], ['needle', 'pin'], [])
    fulltext_query_clause = fulltext_helpers._BuildFTSCondition(
        query_cond, self.fulltext_fields)
    self.assertEqual(
        '(summary:"needle" OR summary:"pin")',
        fulltext_query_clause)

  def testBuildFTSCondition_NegatedQuickOR(self):
    query_cond = ast_pb2.MakeCond(
        NOT_TEXT_HAS, [self.summary_fd], ['needle', 'pin'], [])
    fulltext_query_clause = fulltext_helpers._BuildFTSCondition(
        query_cond, self.fulltext_fields)
    self.assertEqual(
        'NOT (summary:"needle" OR summary:"pin")',
        fulltext_query_clause)

  def testBuildFTSCondition_AnyField(self):
    query_cond = ast_pb2.MakeCond(
        TEXT_HAS, [self.any_field_fd], ['needle'], [])
    fulltext_query_clause = fulltext_helpers._BuildFTSCondition(
        query_cond, self.fulltext_fields)
    self.assertEqual('("needle")', fulltext_query_clause)

  def testBuildFTSCondition_NegatedAnyField(self):
    query_cond = ast_pb2.MakeCond(
        NOT_TEXT_HAS, [self.any_field_fd], ['needle'], [])
    fulltext_query_clause = fulltext_helpers._BuildFTSCondition(
        query_cond, self.fulltext_fields)
    self.assertEqual('NOT ("needle")', fulltext_query_clause)

  def testBuildFTSCondition_CrossProjectWithMultipleFieldDescriptors(self):
    other_milestone_fd = tracker_pb2.FieldDef(
        field_name='milestone', field_type=tracker_pb2.FieldTypes.STR_TYPE,
        field_id=456)
    query_cond = ast_pb2.MakeCond(
        TEXT_HAS, [self.milestone_fd, other_milestone_fd], ['needle'], [])
    fulltext_query_clause = fulltext_helpers._BuildFTSCondition(
        query_cond, self.fulltext_fields)
    self.assertEqual(
        '(custom_123:"needle" OR custom_456:"needle")', fulltext_query_clause)

  def SetUpComprehensiveSearch(self):
    search.Index(name='search index name').AndReturn(
        self.mock_index)
    self.mock_index.search(mox.IgnoreArg()).WithSideEffects(
        self.RecordQuery).AndReturn(
            MockSearchResponse(['123', '234'], search.Cursor()))
    self.mock_index.search(mox.IgnoreArg()).WithSideEffects(
        self.RecordQuery).AndReturn(MockSearchResponse(['345'], None))

  def testComprehensiveSearch(self):
    self.SetUpComprehensiveSearch()
    self.mox.ReplayAll()
    project_ids = fulltext_helpers.ComprehensiveSearch(
        'browser', 'search index name')
    self.mox.VerifyAll()
    self.assertItemsEqual([123, 234, 345], project_ids)
