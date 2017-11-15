# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for tracker_fulltext module."""

import unittest

import mox

from google.appengine.api import search

import settings
from framework import framework_views
from proto import ast_pb2
from proto import tracker_pb2
from services import fulltext_helpers
from services import tracker_fulltext
from testing import fake
from tracker import tracker_bizobj


class TrackerFulltextTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.mock_index = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(search, 'Index')
    self.docs = None
    self.cnxn = 'fake connection'
    self.user_service = fake.UserService()
    self.user_service.TestAddUser('test@example.com', 111L)
    self.issue_service = fake.IssueService()
    self.config_service = fake.ConfigService()

    self.issue = fake.MakeTestIssue(
        123, 1, 'test summary', 'New', 111L)
    self.issue_service.TestAddIssue(self.issue)
    self.comment = tracker_pb2.IssueComment(
        project_id=789, issue_id=self.issue.issue_id, user_id=111L,
        content='comment content',
        attachments=[
            tracker_pb2.Attachment(filename='hello.c'),
            tracker_pb2.Attachment(filename='hello.h')])
    self.issue_service.TestAddComment(self.comment, 1)
    self.users_by_id = framework_views.MakeAllUserViews(
        self.cnxn, self.user_service, [111L])

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def RecordDocs(self, docs):
    self.docs = docs

  def SetUpIndexIssues(self):
    search.Index(name=settings.search_index_name_format % 1).AndReturn(
        self.mock_index)
    self.mock_index.put(mox.IgnoreArg()).WithSideEffects(self.RecordDocs)

  def testIndexIssues(self):
    self.SetUpIndexIssues()
    self.mox.ReplayAll()
    tracker_fulltext.IndexIssues(
        self.cnxn, [self.issue], self.user_service, self.issue_service,
        self.config_service)
    self.mox.VerifyAll()
    self.assertEqual(1, len(self.docs))
    issue_doc = self.docs[0]
    self.assertEqual(123, issue_doc.fields[0].value)
    self.assertEqual('test summary', issue_doc.fields[1].value)

  def SetUpCreateIssueSearchDocuments(self):
    self.mox.StubOutWithMock(tracker_fulltext, '_IndexDocsInShard')
    tracker_fulltext._IndexDocsInShard(1, mox.IgnoreArg()).WithSideEffects(
        lambda shard_id, docs: self.RecordDocs(docs))

  def testCreateIssueSearchDocuments_Normal(self):
    self.SetUpCreateIssueSearchDocuments()
    self.mox.ReplayAll()
    config_dict = {123: tracker_bizobj.MakeDefaultProjectIssueConfig(123)}
    tracker_fulltext._CreateIssueSearchDocuments(
        [self.issue], {self.issue.issue_id: [self.comment]}, self.users_by_id,
        config_dict)
    self.mox.VerifyAll()
    self.assertEqual(1, len(self.docs))
    issue_doc = self.docs[0]
    self.assertEqual(5, len(issue_doc.fields))
    self.assertEqual(123, issue_doc.fields[0].value)
    self.assertEqual('test summary', issue_doc.fields[1].value)
    self.assertEqual('test@example.com comment content hello.c hello.h',
                     issue_doc.fields[3].value)
    self.assertEqual('', issue_doc.fields[4].value)

  def testCreateIssueSearchDocuments_NoIndexableComments(self):
    """Sometimes all comments on a issue are spam or deleted."""
    self.SetUpCreateIssueSearchDocuments()
    self.mox.ReplayAll()
    config_dict = {123: tracker_bizobj.MakeDefaultProjectIssueConfig(123)}
    self.comment.deleted_by = 111L
    tracker_fulltext._CreateIssueSearchDocuments(
        [self.issue], {self.issue.issue_id: [self.comment]}, self.users_by_id,
        config_dict)
    self.mox.VerifyAll()
    self.assertEqual(1, len(self.docs))
    issue_doc = self.docs[0]
    self.assertEqual(5, len(issue_doc.fields))
    self.assertEqual(123, issue_doc.fields[0].value)
    self.assertEqual('test summary', issue_doc.fields[1].value)
    self.assertEqual('', issue_doc.fields[3].value)
    self.assertEqual('', issue_doc.fields[4].value)

  def testCreateIssueSearchDocuments_CustomFields(self):
    self.SetUpCreateIssueSearchDocuments()
    self.mox.ReplayAll()
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(123)
    config_dict = {123: tracker_bizobj.MakeDefaultProjectIssueConfig(123)}
    int_field = tracker_bizobj.MakeFieldDef(
        1, 123, 'CustomInt', tracker_pb2.FieldTypes.INT_TYPE, None, False,
        False, False, None, None, None, None, False, None, None, None,
        'no_action', 'A custom int field', False)
    int_field_value = tracker_bizobj.MakeFieldValue(
        1, 42, None, None, False, None, None)
    str_field = tracker_bizobj.MakeFieldDef(
        2, 123, 'CustomStr', tracker_pb2.FieldTypes.STR_TYPE, None, False,
        False, False, None, None, None, None, False, None, None, None,
        'no_action', 'A custom string field', False)
    str_field_value = tracker_bizobj.MakeFieldValue(
        2, None, 'Greetings', None, None, None, False)
    # TODO(jrobbins): user-type field 3
    date_field = tracker_bizobj.MakeFieldDef(
        4, 123, 'CustomDate', tracker_pb2.FieldTypes.DATE_TYPE, None, False,
        False, False, None, None, None, None, False, None, None, None,
        'no_action', 'A custom date field', False)
    date_field_value = tracker_bizobj.MakeFieldValue(
        4, None, None, None, 1234567890, None, False)
    config.field_defs.extend([int_field, str_field, date_field])
    self.issue.field_values.extend([
        int_field_value, str_field_value, date_field_value])

    tracker_fulltext._CreateIssueSearchDocuments(
        [self.issue], {self.issue.issue_id: [self.comment]}, self.users_by_id,
        config_dict)
    self.mox.VerifyAll()
    self.assertEqual(1, len(self.docs))
    issue_doc = self.docs[0]
    metadata = issue_doc.fields[2]
    self.assertEqual(
      u'New test@example.com []  42 Greetings 2009-02-13 ',
      metadata.value)

  def testExtractCommentText(self):
    extracted_text = tracker_fulltext._ExtractCommentText(
        self.comment, self.users_by_id)
    self.assertEqual(
        'test@example.com comment content hello.c hello.h',
        extracted_text)

  def testIndexableComments_Length(self):
    comments = [self.comment]
    indexable = tracker_fulltext._IndexableComments(comments, self.users_by_id)
    self.assertEquals(1, len(indexable))

    comments = [self.comment] * 100
    indexable = tracker_fulltext._IndexableComments(comments, self.users_by_id)
    self.assertEquals(100, len(indexable))

    comments = [self.comment] * 101
    indexable = tracker_fulltext._IndexableComments(comments, self.users_by_id)
    self.assertEquals(101, len(indexable))

    comments = [self.comment] * 600
    indexable = tracker_fulltext._IndexableComments(comments, self.users_by_id)
    self.assertEquals(600, len(indexable))

    comments = [self.comment] * 601
    indexable = tracker_fulltext._IndexableComments(comments, self.users_by_id)
    self.assertEquals(600, len(indexable))
    self.assertNotIn(100, indexable)

  def SetUpUnindexIssues(self):
    search.Index(name=settings.search_index_name_format % 1).AndReturn(
        self.mock_index)
    self.mock_index.delete(['1'])

  def testUnindexIssues(self):
    self.SetUpUnindexIssues()
    self.mox.ReplayAll()
    tracker_fulltext.UnindexIssues([1])
    self.mox.VerifyAll()

  def SetUpSearchIssueFullText(self):
    self.mox.StubOutWithMock(fulltext_helpers, 'ComprehensiveSearch')
    fulltext_helpers.ComprehensiveSearch(
        '(project_id:789) (summary:"test")',
        settings.search_index_name_format % 1).AndReturn([123, 234])

  def testSearchIssueFullText_Normal(self):
    self.SetUpSearchIssueFullText()
    self.mox.ReplayAll()
    summary_fd = tracker_pb2.FieldDef(
        field_name='summary', field_type=tracker_pb2.FieldTypes.STR_TYPE)
    query_ast_conj = ast_pb2.Conjunction(conds=[
        ast_pb2.Condition(
            op=ast_pb2.QueryOp.TEXT_HAS, field_defs=[summary_fd],
            str_values=['test'])])
    issue_ids, capped = tracker_fulltext.SearchIssueFullText(
        [789], query_ast_conj, 1)
    self.mox.VerifyAll()
    self.assertItemsEqual([123, 234], issue_ids)
    self.assertFalse(capped)

  def testSearchIssueFullText_CrossProject(self):
    self.mox.StubOutWithMock(fulltext_helpers, 'ComprehensiveSearch')
    fulltext_helpers.ComprehensiveSearch(
        '(project_id:789 OR project_id:678) (summary:"test")',
        settings.search_index_name_format % 1).AndReturn([123, 234])
    self.mox.ReplayAll()

    summary_fd = tracker_pb2.FieldDef(
        field_name='summary', field_type=tracker_pb2.FieldTypes.STR_TYPE)
    query_ast_conj = ast_pb2.Conjunction(conds=[
        ast_pb2.Condition(
            op=ast_pb2.QueryOp.TEXT_HAS, field_defs=[summary_fd],
            str_values=['test'])])
    issue_ids, capped = tracker_fulltext.SearchIssueFullText(
        [789, 678], query_ast_conj, 1)
    self.mox.VerifyAll()
    self.assertItemsEqual([123, 234], issue_ids)
    self.assertFalse(capped)

  def testSearchIssueFullText_Capped(self):
    try:
      orig = settings.fulltext_limit_per_shard
      settings.fulltext_limit_per_shard = 1
      self.SetUpSearchIssueFullText()
      self.mox.ReplayAll()
      summary_fd = tracker_pb2.FieldDef(
        field_name='summary', field_type=tracker_pb2.FieldTypes.STR_TYPE)
      query_ast_conj = ast_pb2.Conjunction(conds=[
          ast_pb2.Condition(
              op=ast_pb2.QueryOp.TEXT_HAS, field_defs=[summary_fd],
              str_values=['test'])])
      issue_ids, capped = tracker_fulltext.SearchIssueFullText(
          [789], query_ast_conj, 1)
      self.mox.VerifyAll()
      self.assertItemsEqual([123, 234], issue_ids)
      self.assertTrue(capped)
    finally:
      settings.fulltext_limit_per_shard = orig
