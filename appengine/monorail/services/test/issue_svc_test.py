# -*- coding: utf-8 -*-
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for issue_svc module."""

import logging
import time
import unittest
from mock import patch, Mock, ANY

import mox

from google.appengine.api import search
from google.appengine.ext import testbed

import settings
from framework import exceptions
from framework import sql
from proto import tracker_pb2
from services import caches
from services import chart_svc
from services import issue_svc
from services import service_manager
from services import spam_svc
from services import tracker_fulltext
from testing import fake
from tracker import tracker_bizobj


class MockIndex(object):

  def delete(self, string_list):
    pass


def MakeIssueService(project_service, config_service, cache_manager,
    chart_service, my_mox):
  issue_service = issue_svc.IssueService(
      project_service, config_service, cache_manager, chart_service)
  for table_var in [
      'issue_tbl', 'issuesummary_tbl', 'issue2label_tbl',
      'issue2component_tbl', 'issue2cc_tbl', 'issue2notify_tbl',
      'issue2fieldvalue_tbl', 'issuerelation_tbl', 'danglingrelation_tbl',
      'issueformerlocations_tbl', 'comment_tbl', 'commentcontent_tbl',
      'issueupdate_tbl', 'attachment_tbl', 'reindexqueue_tbl',
      'localidcounter_tbl', 'issuephasedef_tbl', 'issue2approvalvalue_tbl',
      'issueapproval2approver_tbl', 'issueapproval2comment_tbl']:
    setattr(issue_service, table_var, my_mox.CreateMock(sql.SQLTableManager))

  return issue_service


class TestableIssueTwoLevelCache(issue_svc.IssueTwoLevelCache):

  def __init__(self, issue_list):
    cache_manager = fake.CacheManager()
    super(TestableIssueTwoLevelCache, self).__init__(
        cache_manager, None, None, None)
    self.cache = caches.RamCache(cache_manager, 'issue')
    self.memcache_prefix = 'issue:'
    self.pb_class = tracker_pb2.Issue

    self.issue_dict = {
      issue.issue_id: issue
      for issue in issue_list}

  def FetchItems(self, cnxn, issue_ids, shard_id=None):
    return {
      issue_id: self.issue_dict[issue_id]
      for issue_id in issue_ids
      if issue_id in self.issue_dict}


class IssueIDTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = 'fake connection'
    self.project_service = fake.ProjectService()
    self.config_service = fake.ConfigService()
    self.cache_manager = fake.CacheManager()
    self.chart_service = chart_svc.ChartService(self.config_service)
    self.issue_service = MakeIssueService(
        self.project_service, self.config_service, self.cache_manager,
        self.chart_service, self.mox)
    self.issue_id_2lc = self.issue_service.issue_id_2lc
    self.spam_service = fake.SpamService()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testDeserializeIssueIDs_Empty(self):
    issue_id_dict = self.issue_id_2lc._DeserializeIssueIDs([])
    self.assertEqual({}, issue_id_dict)

  def testDeserializeIssueIDs_Normal(self):
    rows = [(789, 1, 78901), (789, 2, 78902), (789, 3, 78903)]
    issue_id_dict = self.issue_id_2lc._DeserializeIssueIDs(rows)
    expected = {
        (789, 1): 78901,
        (789, 2): 78902,
        (789, 3): 78903,
        }
    self.assertEqual(expected, issue_id_dict)

  def SetUpFetchItems(self):
    where = [
        ('(Issue.project_id = %s AND Issue.local_id IN (%s,%s,%s))',
         [789, 1, 2, 3])]
    rows = [(789, 1, 78901), (789, 2, 78902), (789, 3, 78903)]
    self.issue_service.issue_tbl.Select(
        self.cnxn, cols=['project_id', 'local_id', 'id'],
        where=where, or_where_conds=True).AndReturn(rows)

  def testFetchItems(self):
    project_local_ids_list = [(789, 1), (789, 2), (789, 3)]
    issue_ids = [78901, 78902, 78903]
    self.SetUpFetchItems()
    self.mox.ReplayAll()
    issue_dict = self.issue_id_2lc.FetchItems(
        self.cnxn, project_local_ids_list)
    self.mox.VerifyAll()
    self.assertItemsEqual(project_local_ids_list, issue_dict.keys())
    self.assertItemsEqual(issue_ids, issue_dict.values())

  def testKeyToStr(self):
    self.assertEqual('789,1', self.issue_id_2lc._KeyToStr((789, 1)))

  def testStrToKey(self):
    self.assertEqual((789, 1), self.issue_id_2lc._StrToKey('789,1'))


class IssueTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = 'fake connection'
    self.project_service = fake.ProjectService()
    self.config_service = fake.ConfigService()
    self.cache_manager = fake.CacheManager()
    self.chart_service = chart_svc.ChartService(self.config_service)
    self.issue_service = MakeIssueService(
        self.project_service, self.config_service, self.cache_manager,
        self.chart_service, self.mox)
    self.issue_2lc = self.issue_service.issue_2lc

    now = int(time.time())
    self.project_service.TestAddProject('proj', project_id=789)
    self.issue_rows = [
        (78901, 789, 1, 1, 111L, 222L,
         now, now, now, now, now, now,
         0, 0, 0, 1, 0, False)]
    self.summary_rows = [(78901, 'sum')]
    self.label_rows = [(78901, 1, 0)]
    self.component_rows = []
    self.cc_rows = [(78901, 333L, 0)]
    self.notify_rows = []
    self.fieldvalue_rows = []
    self.blocked_on_rows = (
        (78901, 78902, 'blockedon', 20), (78903, 78901, 'blockedon', 10))
    self.blocking_rows = ()
    self.merged_rows = ()
    self.relation_rows = (
        self.blocked_on_rows + self.blocking_rows + self.merged_rows)
    self.dangling_relation_rows = [
        (78901, 'codesite', 5001, 'blocking'),
        (78901, 'codesite', 5002, 'blockedon')]
    self.phase_rows = [(1, 'Canary', 1), (2, 'Stable', 11)]
    self.approvalvalue_rows = [(21, 78901, 1, 'needs_review', None, None),
                               (23, 78901, 1, 'not_set', None, None),
                               (22, 78901, 2, 'not_set', None, None)]
    self.av_approver_rows = [
        (21, 111, 78901), (21, 222, 78901), (21, 333, 78901)]

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testUnpackApprovalValue(self):
    av, issue_id = self.issue_2lc._UnpackApprovalValue(
        self.approvalvalue_rows[0])
    self.assertEqual(av.status, tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    self.assertIsNone(av.setter_id)
    self.assertIsNone(av.set_on)
    self.assertEqual(issue_id, 78901)
    self.assertEqual(av.phase_id, 1)

  def testUnpackApprovalValue_MissingStatus(self):
    av, _issue_id = self.issue_2lc._UnpackApprovalValue(
        (21, 78901, 1, '', None, None))
    self.assertEqual(av.status, tracker_pb2.ApprovalStatus.NOT_SET)

  def testUnpackPhase(self):
    phase = self.issue_2lc._UnpackPhase(
        self.phase_rows[0])
    self.assertEqual(phase.name, 'Canary')
    self.assertEqual(phase.phase_id, 1)
    self.assertEqual(phase.rank, 1)

  def testDeserializeIssues_Empty(self):
    issue_dict = self.issue_2lc._DeserializeIssues(
        self.cnxn, [], [], [], [], [], [], [], [], [], [], [], [])
    self.assertEqual({}, issue_dict)

  def testDeserializeIssues_Normal(self):
    issue_dict = self.issue_2lc._DeserializeIssues(
        self.cnxn, self.issue_rows, self.summary_rows, self.label_rows,
        self.component_rows, self.cc_rows, self.notify_rows,
        self.fieldvalue_rows, self.relation_rows, self.dangling_relation_rows,
        self.phase_rows, self.approvalvalue_rows, self.av_approver_rows)
    self.assertItemsEqual([78901], issue_dict.keys())
    issue = issue_dict[78901]
    self.assertEqual(len(issue.phases), 2)
    self.assertIsNotNone(tracker_bizobj.FindPhaseByID(1, issue.phases))
    av_21 = tracker_bizobj.FindApprovalValueByID(
        21, issue.approval_values)
    self.assertEqual(av_21.phase_id, 1)
    self.assertItemsEqual(av_21.approver_ids, [111, 222, 333])
    self.assertIsNotNone(tracker_bizobj.FindPhaseByID(2, issue.phases))
    self.assertEqual(len(issue.phases), 2)
    av_22 = tracker_bizobj.FindApprovalValueByID(
        22, issue.approval_values)
    self.assertEqual(av_22.phase_id, 2)

  def testDeserializeIssues_UnexpectedLabel(self):
    unexpected_label_rows = [
      (78901, 999, 0)
      ]
    self.assertRaises(
      AssertionError,
      self.issue_2lc._DeserializeIssues,
      self.cnxn, self.issue_rows, self.summary_rows, unexpected_label_rows,
      self.component_rows, self.cc_rows, self.notify_rows,
      self.fieldvalue_rows, self.relation_rows, self.dangling_relation_rows,
      self.phase_rows, self.approvalvalue_rows, self.av_approver_rows)

  def testDeserializeIssues_UnexpectedIssueRelation(self):
    unexpected_relation_rows = [
      (78990, 78999, 'blockedon', None)
      ]
    self.assertRaises(
      AssertionError,
      self.issue_2lc._DeserializeIssues,
      self.cnxn, self.issue_rows, self.summary_rows, self.label_rows,
      self.component_rows, self.cc_rows, self.notify_rows,
      self.fieldvalue_rows, unexpected_relation_rows,
      self.dangling_relation_rows, self.phase_rows, self.approvalvalue_rows,
      self.av_approver_rows)

  def SetUpFetchItems(self, issue_ids):
    shard_id = None
    self.issue_service.issue_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE_COLS, id=issue_ids,
        shard_id=shard_id).AndReturn(self.issue_rows)
    self.issue_service.issuesummary_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUESUMMARY_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.summary_rows)
    self.issue_service.issue2label_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2LABEL_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.label_rows)
    self.issue_service.issue2component_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2COMPONENT_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.component_rows)
    self.issue_service.issue2cc_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2CC_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.cc_rows)
    self.issue_service.issue2notify_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2NOTIFY_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.notify_rows)
    self.issue_service.issue2fieldvalue_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2FIELDVALUE_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.fieldvalue_rows)
    self.issue_service.issuephasedef_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEPHASEDEF_COLS,
        id=[1, 2]).AndReturn(self.phase_rows)
    self.issue_service.issue2approvalvalue_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2APPROVALVALUE_COLS,
        issue_id=issue_ids).AndReturn(self.approvalvalue_rows)
    self.issue_service.issueapproval2approver_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEAPPROVAL2APPROVER_COLS,
        issue_id=issue_ids).AndReturn(self.av_approver_rows)
    self.issue_service.issuerelation_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS,
        issue_id=issue_ids, kind='blockedon',
        order_by=[('issue_id', []), ('rank DESC', []),
                  ('dst_issue_id', [])]).AndReturn(self.blocked_on_rows)
    self.issue_service.issuerelation_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS,
        dst_issue_id=issue_ids, kind='blockedon',
        order_by=[('issue_id', []), ('dst_issue_id', [])]
        ).AndReturn(self.blocking_rows)
    self.issue_service.issuerelation_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS,
        where=[('(issue_id IN (%s) OR dst_issue_id IN (%s))',
                issue_ids + issue_ids),
                ('kind != %s', ['blockedon'])]).AndReturn(self.merged_rows)
    self.issue_service.danglingrelation_tbl.Select(
        self.cnxn, cols=issue_svc.DANGLINGRELATION_COLS,  # Note: no shard
        issue_id=issue_ids).AndReturn(self.dangling_relation_rows)

  def testFetchItems(self):
    issue_ids = [78901]
    self.SetUpFetchItems(issue_ids)
    self.mox.ReplayAll()
    issue_dict = self.issue_2lc.FetchItems(self.cnxn, issue_ids)
    self.mox.VerifyAll()
    self.assertItemsEqual(issue_ids, issue_dict.keys())


class IssueServiceTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.services = service_manager.Services()
    self.services.user = fake.UserService()
    self.reporter = self.services.user.TestAddUser('reporter@example.com', 111L)
    self.services.usergroup = fake.UserGroupService()
    self.services.project = fake.ProjectService()
    self.services.project.TestAddProject('proj', project_id=789)
    self.services.config = fake.ConfigService()
    self.services.features = fake.FeaturesService()
    self.cache_manager = fake.CacheManager()
    self.services.chart = chart_svc.ChartService(self.services.config)
    self.services.issue = MakeIssueService(
        self.services.project, self.services.config, self.cache_manager,
        self.services.chart, self.mox)
    self.services.spam = self.mox.CreateMock(spam_svc.SpamService)
    self.now = int(time.time())
    self.patcher = patch('services.tracker_fulltext.IndexIssues')
    self.patcher.start()
    self.mox.StubOutWithMock(self.services.chart, 'StoreIssueSnapshots')

  def classifierResult(self, score, failed_open=False):
    return {'confidence_is_spam': score,
            'failed_open': failed_open}

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()
    self.patcher.stop()

  ### Issue ID lookups

  def testLookupIssueIDs_Hit(self):
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.services.issue.issue_id_2lc.CacheItem((789, 2), 78902)
    actual, _misses = self.services.issue.LookupIssueIDs(
        self.cnxn, [(789, 1), (789, 2)])
    self.assertEqual([78901, 78902], actual)

  def testLookupIssueID(self):
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    actual = self.services.issue.LookupIssueID(self.cnxn, 789, 1)
    self.assertEqual(78901, actual)

  def testResolveIssueRefs(self):
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.services.issue.issue_id_2lc.CacheItem((789, 2), 78902)
    prefetched_projects = {'proj': fake.Project('proj', project_id=789)}
    refs = [('proj', 1), (None, 2)]
    actual, misses = self.services.issue.ResolveIssueRefs(
        self.cnxn, prefetched_projects, 'proj', refs)
    self.assertEqual(misses, [])
    self.assertEqual([78901, 78902], actual)

  def testLookupIssueRefs_Empty(self):
    actual = self.services.issue.LookupIssueRefs(self.cnxn, [])
    self.assertEqual({}, actual)

  def testLookupIssueRefs_Normal(self):
    issue_1 = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901, project_name='proj')
    self.services.issue.issue_2lc.CacheItem(78901, issue_1)
    actual = self.services.issue.LookupIssueRefs(self.cnxn, [78901])
    self.assertEqual(
        {78901: ('proj', 1)},
        actual)

  ### Issue objects

  def testCreateIssue(self):
    settings.classifier_spam_thresh = 0.9
    av_23 = tracker_pb2.ApprovalValue(
        approval_id=23, phase_id=1, approver_ids=[111L, 222L],
        status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    av_24 = tracker_pb2.ApprovalValue(
        approval_id=24, phase_id=1, approver_ids=[111L])
    approval_values = [av_23, av_24]
    av_rows = [(23, 78901, 1, 'needs_review', None, None),
               (24, 78901, 1, 'not_set', None, None)]
    approver_rows = [(23, 111L, 78901), (23, 222L, 78901), (24, 111L, 78901)]
    ad_23 = tracker_pb2.ApprovalDef(
        approval_id=23, approver_ids=[111L], survey='Question?')
    ad_24 = tracker_pb2.ApprovalDef(
        approval_id=24, approver_ids=[111L], survey='Question?')
    config = self.services.config.GetProjectConfig(
        self.cnxn, 789)
    config.approval_defs.extend([ad_23, ad_24])
    self.services.config.StoreConfig(self.cnxn, config)

    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpInsertIssue(av_rows=av_rows, approver_rows=approver_rows)
    self.SetUpInsertComment(7890101, is_description=True)
    self.SetUpInsertComment(7890101, is_description=True, approval_id=23,
        content='<b>Question?</b>')
    self.SetUpInsertComment(7890101, is_description=True, approval_id=24,
        content='<b>Question?</b>')
    self.services.spam.ClassifyIssue(mox.IgnoreArg(),
        mox.IgnoreArg(), self.reporter, False).AndReturn(
        self.classifierResult(0.0))
    self.services.spam.RecordClassifierIssueVerdict(self.cnxn,
       mox.IsA(tracker_pb2.Issue), False, 1.0, False)
    self.SetUpUpdateIssuesModified(set())
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    actual_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'sum',
        'New', 111L, [], ['Type-Defect'], [], [], 111L, 'content',
        index_now=False, timestamp=self.now, approval_values=approval_values)
    self.mox.VerifyAll()
    self.assertEqual(1, actual_local_id)

  def testCreateIssue_EmptyStringLabels(self):
    settings.classifier_spam_thresh = 0.9
    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpInsertIssue(label_rows=[])
    self.SetUpInsertComment(7890101, is_description=True)
    self.services.spam.ClassifyIssue(mox.IgnoreArg(),
        mox.IgnoreArg(), self.reporter, False).AndReturn(
        self.classifierResult(0.0))
    self.services.spam.RecordClassifierIssueVerdict(self.cnxn,
       mox.IsA(tracker_pb2.Issue), False, 1.0, False)
    self.SetUpUpdateIssuesModified(set(), modified_timestamp=self.now)
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    actual_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'sum',
        'New', 111L, [], [',', '', ' ', ', '], [], [], 111L, 'content',
        index_now=False, timestamp=self.now)
    self.mox.VerifyAll()
    self.assertEqual(1, actual_local_id)

  def SetUpUpdateIssuesModified(self, iids, modified_timestamp=None):
    self.services.issue.issue_tbl.Update(
        self.cnxn, {'modified': modified_timestamp or self.now},
        id=iids, commit=False)

  def testCreateIssue_SpamPredictionFailed(self):
    settings.classifier_spam_thresh = 0.9
    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpInsertSpamIssue()
    self.SetUpInsertComment(7890101, is_description=True)

    self.services.spam.ClassifyIssue(mox.IsA(tracker_pb2.Issue),
        mox.IsA(tracker_pb2.IssueComment), self.reporter, False).AndReturn(
        self.classifierResult(1.0, True))
    self.services.spam.RecordClassifierIssueVerdict(self.cnxn,
       mox.IsA(tracker_pb2.Issue), True, 1.0, True)
    self.SetUpUpdateIssuesModified(set())
    self.SetUpUpdateIssuesApprovals([])
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    actual_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'sum',
        'New', 111L, [], ['Type-Defect'], [], [], 111L, 'content',
        index_now=False, timestamp=self.now)
    self.mox.VerifyAll()
    self.assertEqual(1, actual_local_id)

  def testCreateIssue_Spam(self):
    settings.classifier_spam_thresh = 0.9
    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpInsertSpamIssue()
    self.SetUpInsertComment(7890101, is_description=True)

    self.services.spam.ClassifyIssue(mox.IsA(tracker_pb2.Issue),
        mox.IsA(tracker_pb2.IssueComment), self.reporter, False).AndReturn(
        self.classifierResult(1.0))
    self.services.spam.RecordClassifierIssueVerdict(self.cnxn,
       mox.IsA(tracker_pb2.Issue), True, 1.0, False)
    self.SetUpUpdateIssuesModified(set())
    self.SetUpUpdateIssuesApprovals([])
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    actual_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'sum',
        'New', 111L, [], ['Type-Defect'], [], [], 111L, 'content',
        index_now=False, timestamp=self.now)
    self.mox.VerifyAll()
    self.assertEqual(1, actual_local_id)

  def testGetAllIssuesInProject_NoIssues(self):
    self.SetUpGetHighestLocalID(789, None, None)
    self.mox.ReplayAll()
    issues = self.services.issue.GetAllIssuesInProject(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual([], issues)

  def testGetAnyOnHandIssue(self):
    issue_ids = [78901, 78902, 78903]
    self.SetUpGetIssues()
    issue = self.services.issue.GetAnyOnHandIssue(issue_ids)
    self.assertEqual(78901, issue.issue_id)

  def SetUpGetIssues(self):
    issue_1 = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)
    issue_1.project_name = 'proj'
    issue_2 = fake.MakeTestIssue(
        project_id=789, local_id=2, owner_id=111L, summary='sum',
        status='Fixed', issue_id=78902)
    issue_2.project_name = 'proj'
    self.services.issue.issue_2lc.CacheItem(78901, issue_1)
    self.services.issue.issue_2lc.CacheItem(78902, issue_2)
    return issue_1, issue_2

  def testGetIssuesDict(self):
    issue_ids = [78901, 78902]
    issue_1, issue_2 = self.SetUpGetIssues()
    issues_dict = self.services.issue.GetIssuesDict(self.cnxn, issue_ids)
    self.assertEqual(
        {78901: issue_1, 78902: issue_2},
        issues_dict)

  def testGetIssues(self):
    issue_ids = [78901, 78902]
    issue_1, issue_2 = self.SetUpGetIssues()
    issues = self.services.issue.GetIssues(self.cnxn, issue_ids)
    self.assertEqual([issue_1, issue_2], issues)

  def testGetIssue(self):
    issue_1, _issue_2 = self.SetUpGetIssues()
    actual_issue = self.services.issue.GetIssue(self.cnxn, 78901)
    self.assertEqual(issue_1, actual_issue)

  def testGetIssuesByLocalIDs(self):
    issue_1, issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.services.issue.issue_id_2lc.CacheItem((789, 2), 78902)
    actual_issues = self.services.issue.GetIssuesByLocalIDs(
        self.cnxn, 789, [1, 2])
    self.assertEqual([issue_1, issue_2], actual_issues)

  def testGetIssueByLocalID(self):
    issue_1, _issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    actual_issues = self.services.issue.GetIssueByLocalID(self.cnxn, 789, 1)
    self.assertEqual(issue_1, actual_issues)

  def testGetOpenAndClosedIssues(self):
    issue_1, issue_2 = self.SetUpGetIssues()
    open_issues, closed_issues = self.services.issue.GetOpenAndClosedIssues(
        self.cnxn, [78901, 78902])
    self.assertEqual([issue_1], open_issues)
    self.assertEqual([issue_2], closed_issues)

  def SetUpGetCurrentLocationOfMovedIssue(self, project_id, local_id):
    issue_id = project_id * 100 + local_id
    self.services.issue.issueformerlocations_tbl.SelectValue(
        self.cnxn, 'issue_id', default=0, project_id=project_id,
        local_id=local_id).AndReturn(issue_id)
    self.services.issue.issue_tbl.SelectRow(
        self.cnxn, cols=['project_id', 'local_id'], id=issue_id).AndReturn(
            (project_id + 1, local_id + 1))

  def testGetCurrentLocationOfMovedIssue(self):
    self.SetUpGetCurrentLocationOfMovedIssue(789, 1)
    self.mox.ReplayAll()
    new_project_id, new_local_id = (
        self.services.issue.GetCurrentLocationOfMovedIssue(self.cnxn, 789, 1))
    self.mox.VerifyAll()
    self.assertEqual(789 + 1, new_project_id)
    self.assertEqual(1 + 1, new_local_id)

  def SetUpGetPreviousLocations(self, issue_id, location_rows):
    self.services.issue.issueformerlocations_tbl.Select(
        self.cnxn, cols=['project_id', 'local_id'],
        issue_id=issue_id).AndReturn(location_rows)

  def testGetPreviousLocations(self):
    self.SetUpGetPreviousLocations(78901, [(781, 1), (782, 11), (789, 1)])
    self.mox.ReplayAll()
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)
    locations = self.services.issue.GetPreviousLocations(self.cnxn, issue)
    self.mox.VerifyAll()
    self.assertEqual(locations, [(781, 1), (782, 11)])

  def SetUpInsertIssue(
      self, label_rows=None, av_rows=None, approver_rows=None):
    row = (789, 1, 1, 111L, 111L,
           self.now, 0, self.now, self.now, self.now, self.now,
           None, 0,
           False, 0, 0, False)
    self.services.issue.issue_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUE_COLS[1:], [row],
        commit=False, return_generated_ids=True).AndReturn([78901])
    self.cnxn.Commit()
    self.services.issue.issue_tbl.Update(
        self.cnxn, {'shard': 78901 % settings.num_logical_shards},
        id=78901, commit=False)
    self.SetUpUpdateIssuesSummary()
    self.SetUpUpdateIssuesLabels(label_rows=label_rows)
    self.SetUpUpdateIssuesFields()
    self.SetUpUpdateIssuesComponents()
    self.SetUpUpdateIssuesCc()
    self.SetUpUpdateIssuesNotify()
    self.SetUpUpdateIssuesRelation()
    self.SetUpUpdateIssuesApprovals(
        av_rows=av_rows, approver_rows=approver_rows)
    self.services.chart.StoreIssueSnapshots(self.cnxn, mox.IgnoreArg(),
        commit=False)

  def SetUpInsertSpamIssue(self):
    row = (789, 1, 1, 111L, 111L,
           self.now, 0, self.now, self.now, self.now, self.now,
           None, 0, False, 0, 0, True)
    self.services.issue.issue_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUE_COLS[1:], [row],
        commit=False, return_generated_ids=True).AndReturn([78901])
    self.cnxn.Commit()
    self.services.issue.issue_tbl.Update(
        self.cnxn, {'shard': 78901 % settings.num_logical_shards},
        id=78901, commit=False)
    self.SetUpUpdateIssuesSummary()
    self.SetUpUpdateIssuesLabels()
    self.SetUpUpdateIssuesFields()
    self.SetUpUpdateIssuesComponents()
    self.SetUpUpdateIssuesCc()
    self.SetUpUpdateIssuesNotify()
    self.SetUpUpdateIssuesRelation()
    self.services.chart.StoreIssueSnapshots(self.cnxn, mox.IgnoreArg(),
        commit=False)

  def SetUpUpdateIssuesSummary(self):
    self.services.issue.issuesummary_tbl.InsertRows(
        self.cnxn, ['issue_id', 'summary'],
        [(78901, 'sum')], replace=True, commit=False)

  def SetUpUpdateIssuesLabels(self, label_rows=None):
    if label_rows is None:
      label_rows = [(78901, 1, False, 1)]
    self.services.issue.issue2label_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2label_tbl.InsertRows(
        self.cnxn, ['issue_id', 'label_id', 'derived', 'issue_shard'],
        label_rows, ignore=True, commit=False)

  def SetUpUpdateIssuesFields(self, issue2fieldvalue_rows=None):
    issue2fieldvalue_rows = issue2fieldvalue_rows or []
    self.services.issue.issue2fieldvalue_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2fieldvalue_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUE2FIELDVALUE_COLS + ['issue_shard'],
        issue2fieldvalue_rows, commit=False)

  def SetUpUpdateIssuesComponents(self, issue2component_rows=None):
    issue2component_rows = issue2component_rows or []
    self.services.issue.issue2component_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2component_tbl.InsertRows(
        self.cnxn, ['issue_id', 'component_id', 'derived', 'issue_shard'],
        issue2component_rows, ignore=True, commit=False)

  def SetUpUpdateIssuesCc(self, issue2cc_rows=None):
    issue2cc_rows = issue2cc_rows or []
    self.services.issue.issue2cc_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2cc_tbl.InsertRows(
        self.cnxn, ['issue_id', 'cc_id', 'derived', 'issue_shard'],
        issue2cc_rows, ignore=True, commit=False)

  def SetUpUpdateIssuesNotify(self, notify_rows=None):
    notify_rows = notify_rows or []
    self.services.issue.issue2notify_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2notify_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUE2NOTIFY_COLS,
        notify_rows, ignore=True, commit=False)

  def SetUpUpdateIssuesRelation(
    self, relation_rows=None, dangling_relation_rows=None):
    relation_rows = relation_rows or []
    dangling_relation_rows = dangling_relation_rows or []
    self.services.issue.issuerelation_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS[:-1],
        dst_issue_id=[78901], kind='blockedon').AndReturn([])
    self.services.issue.issuerelation_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issuerelation_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUERELATION_COLS, relation_rows,
        ignore=True, commit=False)
    self.services.issue.danglingrelation_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.danglingrelation_tbl.InsertRows(
        self.cnxn, issue_svc.DANGLINGRELATION_COLS, dangling_relation_rows,
        ignore=True, commit=False)

  def SetUpUpdateIssuesApprovals(self, av_rows=None, approver_rows=None):
    av_rows = av_rows or []
    approver_rows = approver_rows or []
    approval_ids = [row[0] for row in av_rows]
    self.services.issue.issue2approvalvalue_tbl.Delete(
        self.cnxn, issue_id=78901, commit=False)
    self.services.issue.issue2approvalvalue_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUE2APPROVALVALUE_COLS, av_rows, commit=False)
    self.services.issue.issueapproval2approver_tbl.Delete(
        self.cnxn, issue_id=78901, approval_id=approval_ids, commit=False)
    self.services.issue.issueapproval2approver_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUEAPPROVAL2APPROVER_COLS, approver_rows,
        commit=False)

  def testInsertIssue(self):
    self.SetUpInsertIssue()
    self.mox.ReplayAll()
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, reporter_id=111L,
        summary='sum', status='New', labels=['Type-Defect'], issue_id=78901,
        opened_timestamp=self.now, modified_timestamp=self.now)
    actual_issue_id = self.services.issue.InsertIssue(self.cnxn, issue)
    self.mox.VerifyAll()
    self.assertEqual(78901, actual_issue_id)

  def SetUpUpdateIssues(self, given_delta=None):
    delta = given_delta or {
        'project_id': 789,
        'local_id': 1,
        'owner_id': 111L,
        'status_id': 1,
        'opened': 123456789,
        'closed': 0,
        'modified': 123456789,
        'owner_modified': 123456789,
        'status_modified': 123456789,
        'component_modified': 123456789,
        'derived_owner_id': None,
        'derived_status_id': None,
        'deleted': False,
        'star_count': 12,
        'attachment_count': 0,
        'is_spam': False,
        }
    self.services.issue.issue_tbl.Update(
        self.cnxn, delta, id=78901, commit=False)
    if not given_delta:
      self.SetUpUpdateIssuesLabels()
      self.SetUpUpdateIssuesCc()
      self.SetUpUpdateIssuesFields()
      self.SetUpUpdateIssuesComponents()
      self.SetUpUpdateIssuesNotify()
      self.SetUpUpdateIssuesSummary()
      self.SetUpUpdateIssuesRelation()
      self.services.chart.StoreIssueSnapshots(self.cnxn, mox.IgnoreArg(),
          commit=False)

    if given_delta:
      self.services.chart.StoreIssueSnapshots(self.cnxn, mox.IgnoreArg(),
          commit=False)

    self.cnxn.Commit()

  def testUpdateIssues_Empty(self):
    # Note: no setup because DB should not be called.
    self.mox.ReplayAll()
    self.services.issue.UpdateIssues(self.cnxn, [])
    self.mox.VerifyAll()

  def testUpdateIssues_Normal(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', labels=['Type-Defect'], issue_id=78901,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12)
    issue.assume_stale = False
    self.SetUpUpdateIssues()
    self.mox.ReplayAll()
    self.services.issue.UpdateIssues(self.cnxn, [issue])
    self.mox.VerifyAll()

  def testUpdateIssue_Normal(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', labels=['Type-Defect'], issue_id=78901,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12)
    issue.assume_stale = False
    self.SetUpUpdateIssues()
    self.mox.ReplayAll()
    self.services.issue.UpdateIssue(self.cnxn, issue)
    self.mox.VerifyAll()

  def testUpdateIssue_Stale(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', labels=['Type-Defect'], issue_id=78901,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12)
    # Do not set issue.assume_stale = False
    # Do not call self.SetUpUpdateIssues() because nothing should be updated.
    self.mox.ReplayAll()
    self.assertRaises(
        AssertionError, self.services.issue.UpdateIssue, self.cnxn, issue)
    self.mox.VerifyAll()

  def testUpdateIssuesSummary(self):
    issue = fake.MakeTestIssue(
        local_id=1, issue_id=78901, owner_id=111L, summary='sum', status='New',
        project_id=789)
    issue.assume_stale = False
    self.SetUpUpdateIssuesSummary()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesSummary(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesLabels(self):
    issue = fake.MakeTestIssue(
        local_id=1, issue_id=78901, owner_id=111L, summary='sum', status='New',
        labels=['Type-Defect'], project_id=789)
    self.SetUpUpdateIssuesLabels()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesLabels(
      self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesFields_Empty(self):
    issue = fake.MakeTestIssue(
        local_id=1, issue_id=78901, owner_id=111L, summary='sum', status='New',
        project_id=789)
    self.SetUpUpdateIssuesFields()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesFields(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesFields_Some(self):
    issue = fake.MakeTestIssue(
        local_id=1, issue_id=78901, owner_id=111L, summary='sum', status='New',
        project_id=789)
    issue_shard = issue.issue_id % settings.num_logical_shards
    fv1 = tracker_bizobj.MakeFieldValue(345, 679, '', 0L, None, None, False)
    issue.field_values.append(fv1)
    fv2 = tracker_bizobj.MakeFieldValue(346, 0, 'Blue', 0L, None, None, True)
    issue.field_values.append(fv2)
    fv3 = tracker_bizobj.MakeFieldValue(347, 0, '', 0L, 1234567890, None, True)
    issue.field_values.append(fv3)
    fv4 = tracker_bizobj.MakeFieldValue(
        348, 0, '', 0L, None, 'www.google.com', True, phase_id=14)
    issue.field_values.append(fv4)
    self.SetUpUpdateIssuesFields(issue2fieldvalue_rows=[
        (issue.issue_id, fv1.field_id, fv1.int_value, fv1.str_value,
         None, fv1.date_value, fv1.url_value, fv1.derived, None,
         issue_shard),
        (issue.issue_id, fv2.field_id, fv2.int_value, fv2.str_value,
         None, fv2.date_value, fv2.url_value, fv2.derived, None,
         issue_shard),
        (issue.issue_id, fv3.field_id, fv3.int_value, fv3.str_value,
         None, fv3.date_value, fv3.url_value, fv3.derived, None,
         issue_shard),
        (issue.issue_id, fv4.field_id, fv4.int_value, fv4.str_value,
         None, fv4.date_value, fv4.url_value, fv4.derived, 14,
         issue_shard),
        ])
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesFields(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesComponents_Empty(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)
    self.SetUpUpdateIssuesComponents()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesComponents(
        self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesCc_Empty(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)
    self.SetUpUpdateIssuesCc()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesCc(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesCc_Some(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)
    issue.cc_ids = [222L, 333L]
    issue.derived_cc_ids = [888L]
    issue_shard = issue.issue_id % settings.num_logical_shards
    self.SetUpUpdateIssuesCc(issue2cc_rows=[
        (issue.issue_id, 222L, False, issue_shard),
        (issue.issue_id, 333L, False, issue_shard),
        (issue.issue_id, 888L, True, issue_shard),
        ])
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesCc(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesNotify_Empty(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)
    self.SetUpUpdateIssuesNotify()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesNotify(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesRelation_Empty(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)
    self.SetUpUpdateIssuesRelation()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesRelation(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testDeltaUpdateIssue(self):
    pass  # TODO(jrobbins): write more tests

  def testDeltaUpdateIssue_MergedInto(self):
    commenter_id = 222L
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901, project_name='proj')
    target_issue = fake.MakeTestIssue(
        project_id=789, local_id=2, owner_id=111L, summary='sum sum',
        status='Live', issue_id=78902, project_name='proj')
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

    self.mox.StubOutWithMock(self.services.issue, 'GetIssue')
    self.mox.StubOutWithMock(self.services.issue, 'UpdateIssue')
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssueComment')
    self.mox.StubOutWithMock(self.services.issue, '_UpdateIssuesModified')

    self.services.issue.GetIssue(
        self.cnxn, 0).AndRaise(exceptions.NoSuchIssueException)
    self.services.issue.GetIssue(
        self.cnxn, target_issue.issue_id).AndReturn(target_issue)
    self.services.issue.UpdateIssue(
        self.cnxn, issue, commit=False, invalidate=False)
    amendments = [
        tracker_bizobj.MakeMergedIntoAmendment(
            ('proj', 2), None, default_project_name='proj')]
    self.services.issue.CreateIssueComment(
        self.cnxn, issue, commenter_id, 'comment text', attachments=None,
        amendments=amendments, commit=False, is_description=False)
    self.services.issue._UpdateIssuesModified(
        self.cnxn, {issue.issue_id, target_issue.issue_id},
        modified_timestamp=self.now, invalidate=True)
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    delta = tracker_pb2.IssueDelta(merged_into=target_issue.issue_id)
    self.services.issue.DeltaUpdateIssue(
        self.cnxn, self.services, commenter_id, issue.project_id, config,
        issue, delta, comment='comment text',
        index_now=False, timestamp=self.now)
    self.mox.VerifyAll()

  def testApplyIssueComment(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)

    self.mox.StubOutWithMock(self.services.issue, 'GetIssueByLocalID')
    self.mox.StubOutWithMock(self.services.issue, 'UpdateIssues')
    self.mox.StubOutWithMock(self.services.issue, 'GetCommentsForIssue')
    self.mox.StubOutWithMock(self.services.issue, 'SoftDeleteComment')
    self.mox.StubOutWithMock(self.services.issue, "CreateIssueComment")
    self.mox.StubOutWithMock(self.services.issue, "_UpdateIssuesModified")

    self.services.issue.GetIssueByLocalID(
        self.cnxn, issue.project_id, issue.local_id,
        use_cache=False).AndReturn(issue)
    self.services.issue.CreateIssueComment(self.cnxn, issue,
        issue.reporter_id, 'comment text',
        amendments=[], attachments=None, inbound_message=None,
        is_description=False, is_spam=False, kept_attachments=None)
    self.services.issue.UpdateIssues(self.cnxn, [issue],
        just_derived=False, update_cols=None, commit=True, invalidate=True)
    self.services.spam.ham_classification().AndReturn(
        {'confidence_is_spam': 0.0, 'failed_open': False})
    self.services.spam.RecordClassifierCommentVerdict(self.cnxn,
       None, False, 1.0, False)
    self.services.issue._UpdateIssuesModified(
        self.cnxn, set(), modified_timestamp=self.now)
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    self.services.issue.ApplyIssueComment(self.cnxn, self.services,
       issue.reporter_id, issue.project_id, issue.local_id, issue.summary,
       issue.status, issue.owner_id, issue.cc_ids, issue.labels,
       issue.field_values, issue.component_ids, [],
       [], [], [], issue.merged_into, comment='comment text',
       timestamp=self.now, kept_attachments=None)
    self.mox.VerifyAll()

  def testApplyIssueComment_blockedon(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)
    blockedon_issue = fake.MakeTestIssue(
        project_id=789, local_id=2, owner_id=111L, summary='sum',
        status='Live', issue_id=78902)

    self.mox.StubOutWithMock(self.services.issue, "GetIssueByLocalID")
    self.mox.StubOutWithMock(self.services.issue, "UpdateIssues")
    self.mox.StubOutWithMock(self.services.issue, "CreateIssueComment")
    self.mox.StubOutWithMock(self.services.issue, "GetIssues")
    self.mox.StubOutWithMock(self.services.issue, "_UpdateIssuesModified")
    self.mox.StubOutWithMock(self.services.issue, "SortBlockedOn")
    # Call to find added blockedon issues.
    self.services.issue.GetIssues(
        self.cnxn, [blockedon_issue.issue_id]).AndReturn([blockedon_issue])
    # Call to sort blockedon issues.
    self.services.issue.SortBlockedOn(
        self.cnxn, issue, [blockedon_issue.issue_id]).AndReturn(([78902], [0]))
    # Call to find removed blockedon issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])

    self.services.issue.GetIssueByLocalID(
        self.cnxn, 789, 1, use_cache=False).AndReturn(issue)
    self.services.issue.UpdateIssues(self.cnxn, [issue],
        just_derived=False, update_cols=None, commit=True, invalidate=True)
    self.services.spam.ham_classification().AndReturn(
        {'confidence_is_spam': 0.0, 'failed_open': False})
    self.services.spam.RecordClassifierCommentVerdict(self.cnxn,
        mox.IsA(tracker_pb2.IssueComment), False, 1.0, False)
    self.services.issue.CreateIssueComment(self.cnxn, issue,
        issue.reporter_id, 'comment text',
        amendments=[
            tracker_bizobj.MakeBlockedOnAmendment(
                [(blockedon_issue.project_name, blockedon_issue.local_id)], [],
                default_project_name=blockedon_issue.project_name)],
        attachments=None, inbound_message=None, is_spam=False,
        is_description=False,
        kept_attachments=None).AndReturn(tracker_pb2.IssueComment())
    # Add a comment on the blockedon issue.
    self.services.issue.CreateIssueComment(
            self.cnxn, blockedon_issue,
            blockedon_issue.reporter_id, content='',
            amendments=[tracker_bizobj.MakeBlockingAmendment(
                [(issue.project_name, issue.local_id)], [],
                default_project_name=issue.project_name)])
    self.services.issue._UpdateIssuesModified(
        self.cnxn, {blockedon_issue.issue_id}, modified_timestamp=self.now)
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    self.services.issue.ApplyIssueComment(self.cnxn, self.services,
       issue.reporter_id, issue.project_id, issue.local_id, issue.summary,
       issue.status, issue.owner_id, issue.cc_ids, issue.labels,
       issue.field_values, issue.component_ids, [blockedon_issue.issue_id],
       [], [], [], issue.merged_into, comment='comment text',
       timestamp=self.now)
    self.mox.VerifyAll()

  def SetUpMoveIssues_NewProject(self):
    self.services.issue.issueformerlocations_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEFORMERLOCATIONS_COLS, project_id=789,
        issue_id=[78901]).AndReturn([])
    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpUpdateIssues()
    self.services.issue.comment_tbl.Update(
        self.cnxn, {'project_id': 789}, issue_id=[78901], commit=False)

    old_location_rows = [(78901, 711, 2)]
    self.services.issue.issueformerlocations_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUEFORMERLOCATIONS_COLS, old_location_rows,
        ignore=True, commit=False)
    self.cnxn.Commit()

  def testMoveIssues_NewProject(self):
    """Move project 711 issue 2 to become project 789 issue 1."""
    dest_project = fake.Project(project_id=789)
    issue = fake.MakeTestIssue(
        project_id=711, local_id=2, owner_id=111L, summary='sum',
        status='Live', labels=['Type-Defect'], issue_id=78901,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12)
    issue.assume_stale = False
    self.SetUpMoveIssues_NewProject()
    self.mox.ReplayAll()
    self.services.issue.MoveIssues(
        self.cnxn, dest_project, [issue], self.services.user)
    self.mox.VerifyAll()

  # TODO(jrobbins): case where issue is moved back into former project

  def testExpungeFormerLocations(self):
    self.services.issue.issueformerlocations_tbl.Delete(
      self.cnxn, project_id=789)

    self.mox.ReplayAll()
    self.services.issue.ExpungeFormerLocations(self.cnxn, 789)
    self.mox.VerifyAll()

  def testExpungeIssues(self):
    issue_ids = [1, 2]

    self.mox.StubOutWithMock(search, 'Index')
    search.Index(name=settings.search_index_name_format % 1).AndReturn(
        MockIndex())
    search.Index(name=settings.search_index_name_format % 2).AndReturn(
        MockIndex())

    self.services.issue.issuesummary_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issue2label_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issue2component_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issue2cc_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issue2notify_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issueupdate_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.attachment_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.comment_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issuerelation_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issuerelation_tbl.Delete(self.cnxn, dst_issue_id=[1, 2])
    self.services.issue.danglingrelation_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issueformerlocations_tbl.Delete(
        self.cnxn, issue_id=[1, 2])
    self.services.issue.reindexqueue_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issue_tbl.Delete(self.cnxn, id=[1, 2])

    self.mox.ReplayAll()
    self.services.issue.ExpungeIssues(self.cnxn, issue_ids)
    self.mox.VerifyAll()

  def testSoftDeleteIssue(self):
    project = fake.Project(project_id=789)
    issue_1, issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_2lc = TestableIssueTwoLevelCache(
        [issue_1, issue_2])
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    delta = {'deleted': True}
    self.services.issue.issue_tbl.Update(
        self.cnxn, delta, id=78901, commit=False)

    self.services.chart.StoreIssueSnapshots(self.cnxn, mox.IgnoreArg(),
        commit=False)

    self.cnxn.Commit()
    self.mox.ReplayAll()
    self.services.issue.SoftDeleteIssue(
        self.cnxn, project.project_id, 1, True, self.services.user)
    self.mox.VerifyAll()
    self.assertTrue(issue_1.deleted)

  def SetUpDeleteComponentReferences(self, component_id):
    self.services.issue.issue2component_tbl.Delete(
      self.cnxn, component_id=component_id)

  def testDeleteComponentReferences(self):
    self.SetUpDeleteComponentReferences(123)
    self.mox.ReplayAll()
    self.services.issue.DeleteComponentReferences(self.cnxn, 123)
    self.mox.VerifyAll()

  ### Local ID generation

  def SetUpInitializeLocalID(self, project_id):
    self.services.issue.localidcounter_tbl.InsertRow(
        self.cnxn, project_id=project_id, used_local_id=0, used_spam_id=0)

  def testInitializeLocalID(self):
    self.SetUpInitializeLocalID(789)
    self.mox.ReplayAll()
    self.services.issue.InitializeLocalID(self.cnxn, 789)
    self.mox.VerifyAll()

  def SetUpAllocateNextLocalID(
      self, project_id, highest_in_use, highest_former):
    highest_either = max(highest_in_use or 0, highest_former or 0)
    self.services.issue.localidcounter_tbl.IncrementCounterValue(
        self.cnxn, 'used_local_id', project_id=project_id).AndReturn(
            highest_either + 1)

  def testAllocateNextLocalID_NewProject(self):
    self.SetUpAllocateNextLocalID(789, None, None)
    self.mox.ReplayAll()
    next_local_id = self.services.issue.AllocateNextLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(1, next_local_id)

  def testAllocateNextLocalID_HighestInUse(self):
    self.SetUpAllocateNextLocalID(789, 14, None)
    self.mox.ReplayAll()
    next_local_id = self.services.issue.AllocateNextLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(15, next_local_id)

  def testAllocateNextLocalID_HighestWasMoved(self):
    self.SetUpAllocateNextLocalID(789, 23, 66)
    self.mox.ReplayAll()
    next_local_id = self.services.issue.AllocateNextLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(67, next_local_id)

  def SetUpGetHighestLocalID(self, project_id, highest_in_use, highest_former):
    self.services.issue.issue_tbl.SelectValue(
        self.cnxn, 'MAX(local_id)', project_id=project_id).AndReturn(
            highest_in_use)
    self.services.issue.issueformerlocations_tbl.SelectValue(
        self.cnxn, 'MAX(local_id)', project_id=project_id).AndReturn(
            highest_former)

  def testGetHighestLocalID_OnlyActiveLocalIDs(self):
    self.SetUpGetHighestLocalID(789, 14, None)
    self.mox.ReplayAll()
    highest_id = self.services.issue.GetHighestLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(14, highest_id)

  def testGetHighestLocalID_OnlyFormerIDs(self):
    self.SetUpGetHighestLocalID(789, None, 97)
    self.mox.ReplayAll()
    highest_id = self.services.issue.GetHighestLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(97, highest_id)

  def testGetHighestLocalID_BothActiveAndFormer(self):
    self.SetUpGetHighestLocalID(789, 345, 97)
    self.mox.ReplayAll()
    highest_id = self.services.issue.GetHighestLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(345, highest_id)

  def testGetAllLocalIDsInProject(self):
    self.SetUpGetHighestLocalID(789, 14, None)
    self.mox.ReplayAll()
    local_id_range = self.services.issue.GetAllLocalIDsInProject(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(range(1, 15), local_id_range)

  ### Comments

  def testConsolidateAmendments_Empty(self):
    amendments = []
    actual = self.services.issue._ConsolidateAmendments(amendments)
    self.assertEqual([], actual)

  def testConsolidateAmendments_NoOp(self):
    amendments = [
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('STATUS'),
                            oldvalue='New', newvalue='Accepted'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('SUMMARY'),
                            oldvalue='old sum', newvalue='new sum')]
    actual = self.services.issue._ConsolidateAmendments(amendments)
    amendments.sort(key=lambda a: a.field)
    actual.sort(key=lambda a: a.field)
    self.assertEqual(amendments, actual)

  def testConsolidateAmendments_StandardFields(self):
    amendments = [
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('STATUS'),
                            oldvalue='New'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('STATUS'),
                            newvalue='Accepted'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('SUMMARY'),
                            oldvalue='old sum'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('SUMMARY'),
                            newvalue='new sum')]
    actual = self.services.issue._ConsolidateAmendments(amendments)

    expected = [
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('STATUS'),
                            oldvalue='New', newvalue='Accepted'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('SUMMARY'),
                            oldvalue='old sum', newvalue='new sum')]
    expected.sort(key=lambda a: a.field)
    actual.sort(key=lambda a: a.field)
    self.assertEqual(expected, actual)

  def testConsolidateAmendments_CustomFields(self):
    amendments = [
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('CUSTOM'),
                            custom_field_name='a', oldvalue='old a'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('CUSTOM'),
                            custom_field_name='b', oldvalue='old b')]
    actual = self.services.issue._ConsolidateAmendments(amendments)

    amendments.sort(key=lambda a: a.custom_field_name)
    actual.sort(key=lambda a: a.custom_field_name)
    self.assertEqual(amendments, actual)

  def testDeserializeComments_Empty(self):
    comments = self.services.issue._DeserializeComments([], [], [], [], [])
    self.assertEqual([], comments)

  def SetUpCommentRows(self):
    comment_rows = [
        (7890101, 78901, self.now, 789, 111L,
         None, False, False, 'unused_commentcontent_id'),
        (7890102, 78901, self.now, 789, 111L,
         None, False, False, 'unused_commentcontent_id')]
    commentcontent_rows = [(7890101, 'content', 'msg'),
                           (7890102, 'content2', 'msg')]
    amendment_rows = [
        (1, 78901, 7890101, 'cc', 'old', 'new val', 222, None, None)]
    attachment_rows = []
    approval_rows = [(23, 7890102)]
    return (comment_rows, commentcontent_rows, amendment_rows,
            attachment_rows, approval_rows)

  def testDeserializeComments_Normal(self):
    (comment_rows, commentcontent_rows, amendment_rows,
     attachment_rows, approval_rows) = self.SetUpCommentRows()
    commentcontent_rows = [(7890101, 'content', 'msg')]
    comments = self.services.issue._DeserializeComments(
        comment_rows, commentcontent_rows, amendment_rows, attachment_rows,
        approval_rows)
    self.assertEqual(2, len(comments))

  def MockTheRestOfGetCommentsByID(self, comment_ids):
    self.services.issue.commentcontent_tbl.Select = Mock(
        return_value=[
            (cid + 5000, 'content', None) for cid in comment_ids])
    self.services.issue.issueupdate_tbl.Select = Mock(
        return_value=[])
    self.services.issue.attachment_tbl.Select = Mock(
        return_value=[])
    self.services.issue.issueapproval2comment_tbl.Select = Mock(
        return_value=[])

  def testGetCommentsByID_Normal(self):
    """We can load comments by comment_ids."""
    comment_ids = [101001, 101002, 101003]
    self.services.issue.comment_tbl.Select = Mock(
        return_value=[
            (cid, cid - cid % 100, self.now, 789, 111L,
             None, False, False, cid + 5000)
            for cid in comment_ids])
    self.MockTheRestOfGetCommentsByID(comment_ids)

    comments = self.services.issue.GetCommentsByID(
        self.cnxn, comment_ids, [0, 1, 2])

    self.services.issue.comment_tbl.Select.assert_called_with(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        id=comment_ids, shard_id=ANY)

    self.assertEqual(3, len(comments))

  def testGetCommentsByID_CacheReplicationLag(self):
    self._testGetCommentsByID_ReplicationLag(True)

  def testGetCommentsByID_NoCacheReplicationLag(self):
    self._testGetCommentsByID_ReplicationLag(False)

  def _testGetCommentsByID_ReplicationLag(self, use_cache):
    """If not all comments are on the replica, we try the master."""
    comment_ids = [101001, 101002, 101003]
    replica_comment_ids = comment_ids[:-1]

    return_value_1 = [
      (cid, cid - cid % 100, self.now, 789, 111L,
       None, False, False, cid + 5000)
      for cid in replica_comment_ids]
    return_value_2 = [
      (cid, cid - cid % 100, self.now, 789, 111L,
       None, False, False, cid + 5000)
      for cid in comment_ids]
    return_values = [return_value_1, return_value_2]
    self.services.issue.comment_tbl.Select = Mock(
        side_effect=lambda *_args, **_kwargs: return_values.pop(0))

    self.MockTheRestOfGetCommentsByID(comment_ids)

    comments = self.services.issue.GetCommentsByID(
        self.cnxn, comment_ids, [0, 1, 2], use_cache=use_cache)

    self.services.issue.comment_tbl.Select.assert_called_with(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        id=comment_ids, shard_id=ANY)
    self.services.issue.comment_tbl.Select.assert_called_with(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        id=comment_ids, shard_id=ANY)
    self.assertEqual(3, len(comments))

  def testGetAbbrCommentsForIssue(self):
    """Retrieve abbreviated rows for the comments on an issue."""
    issue_id = 100001
    self.services.issue.comment_tbl.Select = Mock(
        return_value=[
            (101001, 111L, None, True),
            (101002, 222L, None, False),
            (101003, 111L, None, False)])

    abbr_comments = self.services.issue.GetAbbrCommentsForIssue(
        self.cnxn, issue_id)

    self.services.issue.comment_tbl.Select.assert_called_once_with(
        self.cnxn, cols=issue_svc.ABBR_COMMENT_COLS,
        issue_id=issue_id, order_by=[('created ASC', [])])
    self.assertEqual(3, len(abbr_comments))

  def SetUpGetComments(self, issue_ids):
    # Assumes one comment per issue.
    cids = [issue_id + 1000 for issue_id in issue_ids]
    self.services.issue.comment_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        where=None, issue_id=issue_ids, order_by=[('created', [])],
        shard_id=mox.IsA(int)).AndReturn([
            (issue_id + 1000, issue_id, self.now, 789, 111L,
             None, False, False, issue_id + 5000)
            for issue_id in issue_ids])
    self.services.issue.commentcontent_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENTCONTENT_COLS,
        id=[issue_id + 5000 for issue_id in issue_ids],
        shard_id=mox.IsA(int)).AndReturn([
        (issue_id + 5000, 'content', None) for issue_id in issue_ids])
    self.services.issue.issueapproval2comment_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEAPPROVAL2COMMENT_COLS,
        comment_id=cids).AndReturn([
            (23, cid) for cid in cids])

    # Assume no amendments or attachment for now.
    self.services.issue.issueupdate_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEUPDATE_COLS,
        comment_id=cids, shard_id=mox.IsA(int)).AndReturn([])
    attachment_rows = []
    if issue_ids:
      attachment_rows = [
          (1234, issue_ids[0], cids[0], 'a_filename', 1024, 'text/plain',
           False, None)]

    self.services.issue.attachment_tbl.Select(
        self.cnxn, cols=issue_svc.ATTACHMENT_COLS,
        comment_id=cids, shard_id=mox.IsA(int)).AndReturn(attachment_rows)

  def testGetComments_Empty(self):
    self.SetUpGetComments([])
    self.mox.ReplayAll()
    comments = self.services.issue.GetComments(
        self.cnxn, issue_id=[])
    self.mox.VerifyAll()
    self.assertEqual(0, len(comments))

  def testGetComments_Normal(self):
    self.SetUpGetComments([100001, 100002])
    self.mox.ReplayAll()
    comments = self.services.issue.GetComments(
        self.cnxn, issue_id=[100001, 100002])
    self.mox.VerifyAll()
    self.assertEqual(2, len(comments))
    self.assertEqual('content', comments[0].content)
    self.assertEqual('content', comments[1].content)
    self.assertEqual(23, comments[0].approval_id)
    self.assertEqual(23, comments[1].approval_id)

  def SetUpGetComment_Found(self, comment_id):
    # Assumes one comment per issue.
    commentcontent_id = comment_id * 10
    self.services.issue.comment_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        where=None, id=comment_id, order_by=[('created', [])],
        shard_id=mox.IsA(int)).AndReturn([
            (comment_id, int(comment_id / 100), self.now, 789, 111L,
             None, False, True, commentcontent_id)])
    self.services.issue.commentcontent_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENTCONTENT_COLS,
        id=[commentcontent_id], shard_id=mox.IsA(int)).AndReturn([
            (commentcontent_id, 'content', None)])
    self.services.issue.issueapproval2comment_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEAPPROVAL2COMMENT_COLS,
        comment_id=[comment_id]).AndReturn([(23, comment_id)])
    # Assume no amendments or attachment for now.
    self.services.issue.issueupdate_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEUPDATE_COLS,
        comment_id=[comment_id], shard_id=mox.IsA(int)).AndReturn([])
    self.services.issue.attachment_tbl.Select(
        self.cnxn, cols=issue_svc.ATTACHMENT_COLS,
        comment_id=[comment_id], shard_id=mox.IsA(int)).AndReturn([])

  def testGetComment_Found(self):
    self.SetUpGetComment_Found(7890101)
    self.mox.ReplayAll()
    comment = self.services.issue.GetComment(self.cnxn, 7890101)
    self.mox.VerifyAll()
    self.assertEqual('content', comment.content)
    self.assertEqual(23, comment.approval_id)

  def SetUpGetComment_Missing(self, comment_id):
    # Assumes one comment per issue.
    self.services.issue.comment_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        where=None, id=comment_id, order_by=[('created', [])],
        shard_id=mox.IsA(int)).AndReturn([])
    self.services.issue.commentcontent_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENTCONTENT_COLS,
        id=[], shard_id=mox.IsA(int)).AndReturn([])
    self.services.issue.issueapproval2comment_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEAPPROVAL2COMMENT_COLS,
        comment_id=[]).AndReturn([])
    # Assume no amendments or attachment for now.
    self.services.issue.issueupdate_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEUPDATE_COLS,
        comment_id=[], shard_id=mox.IsA(int)).AndReturn([])
    self.services.issue.attachment_tbl.Select(
        self.cnxn, cols=issue_svc.ATTACHMENT_COLS, comment_id=[],
        shard_id=mox.IsA(int)).AndReturn([])

  def testGetComment_Missing(self):
    self.SetUpGetComment_Missing(7890101)
    self.mox.ReplayAll()
    self.assertRaises(
        exceptions.NoSuchCommentException,
        self.services.issue.GetComment, self.cnxn, 7890101)
    self.mox.VerifyAll()

  def testGetCommentsForIssue(self):
    issue = fake.MakeTestIssue(789, 1, 'Summary', 'New', 111L)
    self.SetUpGetComments([issue.issue_id])
    self.mox.ReplayAll()
    self.services.issue.GetCommentsForIssue(self.cnxn, issue.issue_id)
    self.mox.VerifyAll()

  def testGetCommentsForIssues(self):
    self.SetUpGetComments([100001, 100002])
    self.mox.ReplayAll()
    self.services.issue.GetCommentsForIssues(
        self.cnxn, issue_ids=[100001, 100002])
    self.mox.VerifyAll()


  def SetUpInsertComment(
      self, comment_id, is_spam=False, is_description=False, approval_id=None,
          content=None):
    content = content or 'content'
    commentcontent_id = comment_id * 10
    self.services.issue.commentcontent_tbl.InsertRow(
        self.cnxn, content=content,
        inbound_message=None, commit=False).AndReturn(commentcontent_id)
    self.services.issue.comment_tbl.InsertRow(
        self.cnxn, issue_id=78901, created=self.now, project_id=789,
        commenter_id=111L, deleted_by=None, is_spam=is_spam,
        is_description=is_description, commentcontent_id=commentcontent_id,
        commit=False).AndReturn(comment_id)

    amendment_rows = []
    self.services.issue.issueupdate_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUEUPDATE_COLS[1:], amendment_rows,
        commit=False)

    attachment_rows = []
    self.services.issue.attachment_tbl.InsertRows(
        self.cnxn, issue_svc.ATTACHMENT_COLS[1:], attachment_rows,
        commit=False)

    if approval_id:
      self.services.issue.issueapproval2comment_tbl.InsertRows(
          self.cnxn, issue_svc.ISSUEAPPROVAL2COMMENT_COLS,
          [(approval_id, comment_id)], commit=False)

    self.cnxn.Commit()

  def testInsertComment(self):
    self.SetUpInsertComment(7890101, approval_id=23)
    self.mox.ReplayAll()
    comment = tracker_pb2.IssueComment(
        issue_id=78901, timestamp=self.now, project_id=789, user_id=111L,
        content='content', approval_id=23)
    self.services.issue.InsertComment(self.cnxn, comment, commit=True)
    self.mox.VerifyAll()
    self.assertEqual(7890101, comment.id)

  def SetUpUpdateComment(self, comment_id, delta=None):
    delta = delta or {
        'commenter_id': 111L,
        'deleted_by': 222L,
        'is_spam': False,
        }
    self.services.issue.comment_tbl.Update(
        self.cnxn, delta, id=comment_id)

  def testUpdateComment(self):
    self.SetUpUpdateComment(7890101)
    self.mox.ReplayAll()
    comment = tracker_pb2.IssueComment(
        id=7890101, issue_id=78901, timestamp=self.now, project_id=789,
        user_id=111L, content='new content', deleted_by=222L,
        is_spam=False)
    self.services.issue._UpdateComment(self.cnxn, comment)
    self.mox.VerifyAll()

  def testMakeIssueComment(self):
    comment = self.services.issue._MakeIssueComment(
        789, 111L, 'content', timestamp=self.now, approval_id=23)
    self.assertEqual('content', comment.content)
    self.assertEqual([], comment.amendments)
    self.assertEqual([], comment.attachments)
    self.assertEqual(comment.approval_id, 23)

  def testMakeIssueComment_NonAscii(self):
    _ = self.services.issue._MakeIssueComment(
        789, 111L, 'content', timestamp=self.now,
        inbound_message=u'sent by написа')

  def testCreateIssueComment_Normal(self):
    issue_1, _issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.SetUpInsertComment(7890101, approval_id=24)
    self.mox.ReplayAll()
    comment = self.services.issue.CreateIssueComment(
        self.cnxn, issue_1, 111L, 'content', timestamp=self.now, approval_id=24)
    self.mox.VerifyAll()
    self.assertEqual('content', comment.content)

  def testCreateIssueComment_EditDescription(self):
    issue_1, _issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.services.issue.attachment_tbl.Select(
        self.cnxn, cols=issue_svc.ATTACHMENT_COLS, id=[123])
    self.SetUpInsertComment(7890101, is_description=True)
    self.mox.ReplayAll()

    comment = self.services.issue.CreateIssueComment(
        self.cnxn, issue_1, 111L, 'content', is_description=True,
        kept_attachments=[123], timestamp=self.now)
    self.mox.VerifyAll()
    self.assertEqual('content', comment.content)

  def testCreateIssueComment_Spam(self):
    issue_1, _issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.SetUpInsertComment(7890101, is_spam=True)
    self.mox.ReplayAll()
    comment = self.services.issue.CreateIssueComment(
        self.cnxn, issue_1, 111L, 'content', timestamp=self.now, is_spam=True)
    self.mox.VerifyAll()
    self.assertEqual('content', comment.content)
    self.assertTrue(comment.is_spam)

  def testSoftDeleteComment(self):
    """Deleting a comment with an attachment marks it and updates count."""
    issue_1, issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_2lc = TestableIssueTwoLevelCache(
        [issue_1, issue_2])
    issue_1.attachment_count = 1
    issue_1.assume_stale = False
    comment = tracker_pb2.IssueComment(id=7890101)
    comment.attachments = [tracker_pb2.Attachment()]
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.SetUpUpdateComment(
        comment.id, delta={'deleted_by': 222L, 'is_spam': False})
    self.SetUpUpdateIssues(given_delta={'attachment_count': 0})
    self.SetUpEnqueueIssuesForIndexing([78901])
    self.mox.ReplayAll()
    self.services.issue.SoftDeleteComment(
        self.cnxn, issue_1, comment, 222L, self.services.user)
    self.mox.VerifyAll()

  ### Approvals

  def testGetIssueApproval(self):
    av_24 = tracker_pb2.ApprovalValue(approval_id=24)
    av_25 = tracker_pb2.ApprovalValue(approval_id=25)
    issue_1 = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901, approval_values=[av_24, av_25])
    issue_1.project_name = 'proj'
    self.services.issue.issue_2lc.CacheItem(78901, issue_1)

    issue, actual_approval_value = self.services.issue.GetIssueApproval(
        self.cnxn, issue_1.issue_id, av_24.approval_id)

    self.assertEqual(av_24, actual_approval_value)
    self.assertEqual(issue, issue_1)

  def testGetIssueApproval_NoSuchApproval(self):
    issue_1 = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)
    issue_1.project_name = 'proj'
    self.services.issue.issue_2lc.CacheItem(78901, issue_1)
    self.assertRaises(
        exceptions.NoSuchIssueApprovalException,
        self.services.issue.GetIssueApproval,
        self.cnxn, issue_1.issue_id, 24)

  def testUpdateIssueApproval(self):
    config = self.services.config.GetProjectConfig(
        self.cnxn, 789)
    config.field_defs = [
      tracker_pb2.FieldDef(
        field_id=1, project_id=789, field_name='EstDays',
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        applicable_type=''),
      tracker_pb2.FieldDef(
        field_id=2, project_id=789, field_name='Tag',
        field_type=tracker_pb2.FieldTypes.STR_TYPE,
        applicable_type=''),
        ]
    self.services.config.StoreConfig(self.cnxn, config)

    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, summary='summary', status='New',
        owner_id=999L, issue_id=78901)
    av = tracker_pb2.ApprovalValue(approval_id=23)
    final_av = tracker_pb2.ApprovalValue(
        approval_id=23, setter_id=111L, set_on=1234,
        status=tracker_pb2.ApprovalStatus.REVIEW_REQUESTED,
        approver_ids=[222L, 444L])
    amendments = [
        tracker_bizobj.MakeApprovalStatusAmendment(
            tracker_pb2.ApprovalStatus.REVIEW_REQUESTED),
        tracker_bizobj.MakeApprovalApproversAmendment([222L, 444L], []),
        tracker_bizobj.MakeFieldAmendment(1, config, [4], []),
        tracker_bizobj.MakeFieldClearedAmendment(2, config)
    ]
    approval_delta = tracker_pb2.ApprovalDelta(
        status=tracker_pb2.ApprovalStatus.REVIEW_REQUESTED,
        approver_ids_add=[222L, 444L], set_on=1234,
        subfield_vals_add=[
          tracker_bizobj.MakeFieldValue(1, 4, None, None, None, None, False)
          ],
        subfields_clear=[2]
    )

    self.services.issue.issue2approvalvalue_tbl.Update = Mock()
    self.services.issue.issueapproval2approver_tbl.Delete = Mock()
    self.services.issue.issueapproval2approver_tbl.InsertRows = Mock()
    self.services.issue.issue2fieldvalue_tbl.Delete = Mock()
    self.services.issue.issue2fieldvalue_tbl.InsertRows = Mock()
    self.services.issue.CreateIssueComment = Mock()
    shard = issue.issue_id % settings.num_logical_shards
    fv_rows = [(78901, 1, 4, None, None, None, None, False, None, shard)]

    self.services.issue.DeltaUpdateIssueApproval(
        self.cnxn, 111L, config, issue, av, approval_delta, 'some comment',
        attachments=[], commit=False)

    self.assertEqual(av, final_av)

    self.services.issue.issue2approvalvalue_tbl.Update.assert_called_once_with(
        self.cnxn,
        {'status': 'review_requested', 'setter_id': 111L, 'set_on': 1234},
        approval_id=23, issue_id=78901, commit=False)
    self.services.issue.issueapproval2approver_tbl.\
        Delete.assert_called_once_with(
            self.cnxn, issue_id=78901, approval_id=23, commit=False)
    self.services.issue.issueapproval2approver_tbl.\
        InsertRows.assert_called_once_with(
            self.cnxn, issue_svc.ISSUEAPPROVAL2APPROVER_COLS,
            [(23, 222, 78901), (23, 444, 78901)], commit=False)
    self.services.issue.issue2fieldvalue_tbl.\
        Delete.assert_called_once_with(
            self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2fieldvalue_tbl.\
        InsertRows.assert_called_once_with(
            self.cnxn, issue_svc.ISSUE2FIELDVALUE_COLS + ['issue_shard'],
            fv_rows, commit=False)
    self.services.issue.CreateIssueComment.assert_called_once_with(
        self.cnxn, issue, 111L, 'some comment', amendments=amendments,
        approval_id=23, is_description=False, attachments=[], commit=False)

  def testUpdateIssueApproval_IsDescription(self):
    config = self.services.config.GetProjectConfig(
        self.cnxn, 789)
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, summary='summary', status='New',
        owner_id=999L, issue_id=78901)
    av = tracker_pb2.ApprovalValue(approval_id=23)
    approval_delta = tracker_pb2.ApprovalDelta()

    self.services.issue.CreateIssueComment = Mock()

    self.services.issue.DeltaUpdateIssueApproval(
        self.cnxn, 111L, config, issue, av, approval_delta, 'better response',
        is_description=True, commit=False)

    self.services.issue.CreateIssueComment.assert_called_once_with(
        self.cnxn, issue, 111L, 'better response', amendments=[],
        approval_id=23, is_description=True, attachments=None, commit=False)

  def testUpdateIssueApprovalStatus(self):
    av = tracker_pb2.ApprovalValue(approval_id=23, setter_id=111L, set_on=1234)

    self.services.issue.issue2approvalvalue_tbl.Update(
        self.cnxn, {'status': 'not_set', 'setter_id': 111L, 'set_on': 1234},
        approval_id=23, issue_id=78901, commit=False)

    self.mox.ReplayAll()
    self.services.issue._UpdateIssueApprovalStatus(
        self.cnxn, 78901, av.approval_id, av.status,
        av.setter_id, av.set_on)
    self.mox.VerifyAll()

  def testUpdateIssueApprovalApprovers(self):
    self.services.issue.issueapproval2approver_tbl.Delete(
        self.cnxn, issue_id=78901, approval_id=23, commit=False)
    self.services.issue.issueapproval2approver_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUEAPPROVAL2APPROVER_COLS,
        [(23, 111, 78901), (23, 222, 78901), (23, 444, 78901)], commit=False)

    self.mox.ReplayAll()
    self.services.issue._UpdateIssueApprovalApprovers(
        self.cnxn, 78901, 23, [111, 222, 444])
    self.mox.VerifyAll()

  ### Attachments

  def testGetAttachmentAndContext(self):
    # TODO(jrobbins): re-implemnent to use Google Cloud Storage.
    pass

  def SetUpUpdateAttachment(self, attachment_id, delta):
    self.services.issue.attachment_tbl.Update(
        self.cnxn, delta, id=attachment_id)

  def testUpdateAttachment(self):
    delta = {
        'filename': 'a_filename',
        'filesize': 1024,
        'mimetype': 'text/plain',
        'deleted': False,
        }
    self.SetUpUpdateAttachment(1234, delta)
    self.mox.ReplayAll()
    attach = tracker_pb2.Attachment(
        attachment_id=1234, filename='a_filename', filesize=1024,
        mimetype='text/plain')
    self.services.issue._UpdateAttachment(self.cnxn, attach)
    self.mox.VerifyAll()

  def testStoreAttachmentBlob(self):
    # TODO(jrobbins): re-implemnent to use Google Cloud Storage.
    pass

  def testSoftDeleteAttachment(self):
    issue_1, issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_2lc = TestableIssueTwoLevelCache(
        [issue_1, issue_2])
    issue_1.attachment_count = 1
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.SetUpGetComments([78901])
    self.SetUpUpdateAttachment(1234, {'deleted': True})
    self.SetUpUpdateIssues(given_delta={'attachment_count': 0})
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    self.services.issue.SoftDeleteAttachment(
        self.cnxn, 789, 1, 0, 1234, self.services.user)
    self.mox.VerifyAll()

  ### Reindex queue

  def SetUpEnqueueIssuesForIndexing(self, issue_ids):
    reindex_rows = [(issue_id,) for issue_id in issue_ids]
    self.services.issue.reindexqueue_tbl.InsertRows(
        self.cnxn, ['issue_id'], reindex_rows, ignore=True)

  def testEnqueueIssuesForIndexing(self):
    self.SetUpEnqueueIssuesForIndexing([78901])
    self.mox.ReplayAll()
    self.services.issue.EnqueueIssuesForIndexing(self.cnxn, [78901])
    self.mox.VerifyAll()

  def SetUpReindexIssues(self, issue_ids):
    self.services.issue.reindexqueue_tbl.Select(
        self.cnxn, order_by=[('created', [])],
        limit=50).AndReturn([(issue_id,) for issue_id in issue_ids])

    if issue_ids:
      _issue_1, _issue_2 = self.SetUpGetIssues()
      self.services.issue.reindexqueue_tbl.Delete(
          self.cnxn, issue_id=issue_ids)

  def testReindexIssues_QueueEmpty(self):
    self.SetUpReindexIssues([])
    self.mox.ReplayAll()
    self.services.issue.ReindexIssues(self.cnxn, 50, self.services.user)
    self.mox.VerifyAll()

  def testReindexIssues_QueueHasTwoIssues(self):
    self.SetUpReindexIssues([78901, 78902])
    self.mox.ReplayAll()
    self.services.issue.ReindexIssues(self.cnxn, 50, self.services.user)
    self.mox.VerifyAll()

  ### Search functions

  def SetUpRunIssueQuery(
      self, rows, limit=settings.search_limit_per_shard):
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, distinct=True, cols=['Issue.id'],
        left_joins=[], where=[('Issue.deleted = %s', [False])], order_by=[],
        limit=limit).AndReturn(rows)

  def testRunIssueQuery_NoResults(self):
    self.SetUpRunIssueQuery([])
    self.mox.ReplayAll()
    result_iids, capped = self.services.issue.RunIssueQuery(
      self.cnxn, [], [], [], shard_id=1)
    self.mox.VerifyAll()
    self.assertEqual([], result_iids)
    self.assertFalse(capped)

  def testRunIssueQuery_Normal(self):
    self.SetUpRunIssueQuery([(1,), (11,), (21,)])
    self.mox.ReplayAll()
    result_iids, capped = self.services.issue.RunIssueQuery(
      self.cnxn, [], [], [], shard_id=1)
    self.mox.VerifyAll()
    self.assertEqual([1, 11, 21], result_iids)
    self.assertFalse(capped)

  def testRunIssueQuery_Capped(self):
    try:
      orig = settings.search_limit_per_shard
      settings.search_limit_per_shard = 3
      self.SetUpRunIssueQuery([(1,), (11,), (21,)], limit=3)
      self.mox.ReplayAll()
      result_iids, capped = self.services.issue.RunIssueQuery(
        self.cnxn, [], [], [], shard_id=1)
      self.mox.VerifyAll()
      self.assertEqual([1, 11, 21], result_iids)
      self.assertTrue(capped)
    finally:
      settings.search_limit_per_shard = orig

  def SetUpGetIIDsByLabelIDs(self):
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['id'],
        left_joins=[('Issue2Label ON Issue.id = Issue2Label.issue_id', [])],
        label_id=[123, 456], project_id=789,
        where=[('shard = %s', [1])]
        ).AndReturn([(1,), (2,), (3,)])

  def testGetIIDsByLabelIDs(self):
    self.SetUpGetIIDsByLabelIDs()
    self.mox.ReplayAll()
    iids = self.services.issue.GetIIDsByLabelIDs(self.cnxn, [123, 456], 789, 1)
    self.mox.VerifyAll()
    self.assertEqual([1, 2, 3], iids)

  def SetUpGetIIDsByParticipant(self):
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['id'],
        reporter_id=[111L, 888L],
        where=[('shard = %s', [1]), ('Issue.project_id IN (%s)', [789])]
        ).AndReturn([(1,)])
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['id'],
        owner_id=[111L, 888L],
        where=[('shard = %s', [1]), ('Issue.project_id IN (%s)', [789])]
        ).AndReturn([(2,)])
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['id'],
        derived_owner_id=[111L, 888L],
        where=[('shard = %s', [1]), ('Issue.project_id IN (%s)', [789])]
        ).AndReturn([(3,)])
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['id'],
        left_joins=[('Issue2Cc ON Issue2Cc.issue_id = Issue.id', [])],
        cc_id=[111L, 888L],
        where=[('shard = %s', [1]), ('Issue.project_id IN (%s)', [789]),
               ('cc_id IS NOT NULL', [])]
        ).AndReturn([(4,)])
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['Issue.id'],
        left_joins=[
            ('Issue2FieldValue ON Issue.id = Issue2FieldValue.issue_id', []),
            ('FieldDef ON Issue2FieldValue.field_id = FieldDef.id', [])],
        user_id=[111L, 888L], grants_perm='View',
        where=[('shard = %s', [1]), ('Issue.project_id IN (%s)', [789]),
               ('user_id IS NOT NULL', [])]
        ).AndReturn([(5,)])

  def testGetIIDsByParticipant(self):
    self.SetUpGetIIDsByParticipant()
    self.mox.ReplayAll()
    iids = self.services.issue.GetIIDsByParticipant(
        self.cnxn, [111L, 888L], [789], 1)
    self.mox.VerifyAll()
    self.assertEqual([1, 2, 3, 4, 5], iids)

  ### Issue Dependency reranking

  def testSortBlockedOn(self):
    issue = self.SetUpSortBlockedOn()
    self.mox.ReplayAll()
    ret = self.services.issue.SortBlockedOn(
        self.cnxn, issue, issue.blocked_on_iids)
    self.mox.VerifyAll()
    self.assertEqual(ret, ([78902, 78903], [20, 10]))

  def SetUpSortBlockedOn(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111L, summary='sum',
        status='Live', issue_id=78901)
    issue.project_name = 'proj'
    issue.blocked_on_iids = [78902, 78903]
    issue.blocked_on_ranks = [20, 10]
    self.services.issue.issue_2lc.CacheItem(78901, issue)
    blocked_on_rows = (
        (78901, 78902, 'blockedon', 20), (78901, 78903, 'blockedon', 10))
    self.services.issue.issuerelation_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS,
        issue_id=issue.issue_id, dst_issue_id=issue.blocked_on_iids,
        kind='blockedon',
        order_by=[('rank DESC', []), ('dst_issue_id', [])]).AndReturn(
            blocked_on_rows)
    return issue

  def testApplyIssueRerank(self):
    blocker_ids = [78902, 78903]
    relations_to_change = zip(blocker_ids, [20, 10])
    self.services.issue.issuerelation_tbl.Delete(
        self.cnxn, issue_id=78901, dst_issue_id=blocker_ids, commit=False)
    insert_rows = [(78901, blocker_id, 'blockedon', rank)
                   for blocker_id, rank in relations_to_change]
    self.services.issue.issuerelation_tbl.InsertRows(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS, row_values=insert_rows,
        commit=True)

    self.mox.StubOutWithMock(self.services.issue, "InvalidateIIDs")

    self.services.issue.InvalidateIIDs(self.cnxn, [78901])
    self.mox.ReplayAll()
    self.services.issue.ApplyIssueRerank(self.cnxn, 78901, relations_to_change)
    self.mox.VerifyAll()


class IssueServiceFunctionsTest(unittest.TestCase):

  def testUpdateClosedTimestamp(self):
    config = tracker_pb2.ProjectIssueConfig()
    config.well_known_statuses.append(tracker_pb2.StatusDef(
        status='New', means_open=True))
    config.well_known_statuses.append(tracker_pb2.StatusDef(
        status='Accepted', means_open=True))
    config.well_known_statuses.append(tracker_pb2.StatusDef(
        status='Old', means_open=False))
    config.well_known_statuses.append(tracker_pb2.StatusDef(
        status='Closed', means_open=False))

    issue = tracker_pb2.Issue()
    issue.local_id = 1234
    issue.status = 'New'

    # ensure the default value is undef
    self.assert_(not issue.closed_timestamp)

    # ensure transitioning to the same and other open states
    # doesn't set the timestamp
    issue.status = 'New'
    issue_svc._UpdateClosedTimestamp(config, issue, 'New')
    self.assert_(not issue.closed_timestamp)

    issue.status = 'Accepted'
    issue_svc._UpdateClosedTimestamp(config, issue, 'New')
    self.assert_(not issue.closed_timestamp)

    # ensure transitioning from open to closed sets the timestamp
    issue.status = 'Closed'
    issue_svc._UpdateClosedTimestamp(config, issue, 'Accepted')
    self.assert_(issue.closed_timestamp)

    # ensure that the timestamp is cleared when transitioning from
    # closed to open
    issue.status = 'New'
    issue_svc._UpdateClosedTimestamp(config, issue, 'Closed')
    self.assert_(not issue.closed_timestamp)
