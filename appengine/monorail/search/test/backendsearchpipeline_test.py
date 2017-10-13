# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the backendsearchpipeline module."""

import mox
import unittest

from google.appengine.api import memcache
from google.appengine.ext import testbed

import settings
from framework import framework_helpers
from framework import sorting
from framework import sql
from proto import ast_pb2
from proto import tracker_pb2
from search import backendsearchpipeline
from search import ast2ast
from search import query2ast
from services import service_manager
from services import tracker_fulltext
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


class BackendSearchPipelineTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        issue=fake.IssueService(),
        config=fake.ConfigService(),
        cache_manager=fake.CacheManager())
    self.services.user.TestAddUser('a@example.com', 111L)
    self.project = self.services.project.TestAddProject('proj', project_id=789)
    self.mr = testing_helpers.MakeMonorailRequest(
      path='/p/proj/issues/list?q=Priority:High',
      project=self.project)
    self.mr.me_user_id = 999L  # This value is not used by backend search
    self.mr.shard_id = 2
    self.mr.invalidation_timestep = 12345

    self.mox = mox.Mox()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.testbed.init_memcache_stub()
    sorting.InitializeArtValues(self.services)

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def SetUpPromises(self, exp_query):
    self.mox.StubOutWithMock(framework_helpers, 'Promise')
    framework_helpers.Promise(
        backendsearchpipeline._GetQueryResultIIDs, self.mr.cnxn,
        self.services, 'is:open', exp_query, [789],
        mox.IsA(tracker_pb2.ProjectIssueConfig), ['project', 'id'],
        ('Issue.shard = %s', [2]), 2, self.mr.invalidation_timestep
        ).AndReturn('fake promise 1')

  def testMakePromises_Anon(self):
    """A backend pipeline does not personalize the query of anon users."""
    self.SetUpPromises('Priority:High')
    self.mox.ReplayAll()
    backendsearchpipeline.BackendSearchPipeline(
      self.mr, self.services, 100, ['proj'], None, None)
    self.mox.VerifyAll()

  def testMakePromises_SignedIn(self):
    """A backend pipeline immediately personalizes and runs the query."""
    self.mr.query = 'owner:me'
    self.SetUpPromises('owner:111')
    self.mox.ReplayAll()
    backendsearchpipeline.BackendSearchPipeline(
      self.mr, self.services, 100, ['proj'], 111L, 111L)
    self.mox.VerifyAll()

  def testSearchForIIDs(self):
    self.SetUpPromises('Priority:High')
    self.mox.ReplayAll()
    be_pipeline = backendsearchpipeline.BackendSearchPipeline(
      self.mr, self.services, 100, ['proj'], 111L, 111L)
    be_pipeline.result_iids_promise = testing_helpers.Blank(
      WaitAndGetValue=lambda: ([10002, 10052], False, None))
    be_pipeline.SearchForIIDs()
    self.mox.VerifyAll()
    self.assertEqual([10002, 10052], be_pipeline.result_iids)
    self.assertEqual(False, be_pipeline.search_limit_reached)


class BackendSearchPipelineMethodsTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        issue=fake.IssueService(),
        config=fake.ConfigService(),
        cache_manager=fake.CacheManager())
    self.services.user.TestAddUser('a@example.com', 111L)
    self.project = self.services.project.TestAddProject('proj', project_id=789)
    self.mr = testing_helpers.MakeMonorailRequest(
      path='/p/proj/issues/list?q=Priority:High',
      project=self.project)

    self.mox = mox.Mox()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.testbed.init_memcache_stub()

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testSearchProjectCan_Normal(self):
    query_ast = query2ast.ParseUserQuery(
      'Priority:High', 'is:open', query2ast.BUILTIN_ISSUE_FIELDS,
      self.config)
    simplified_query_ast = ast2ast.PreprocessAST(
      self.cnxn, query_ast, [789], self.services, self.config)
    conj = simplified_query_ast.conjunctions[0]
    self.mox.StubOutWithMock(tracker_fulltext, 'SearchIssueFullText')
    tracker_fulltext.SearchIssueFullText(
      [789], conj, 2).AndReturn((None, False))
    self.mox.StubOutWithMock(self.services.issue, 'RunIssueQuery')
    self.services.issue.RunIssueQuery(
      self.cnxn, mox.IsA(list), mox.IsA(list), mox.IsA(list),
      shard_id=2).AndReturn(([10002, 10052], False))
    self.mox.ReplayAll()
    result, capped, err = backendsearchpipeline.SearchProjectCan(
      self.cnxn, self.services, [789], query_ast, 2, self.config)
    self.mox.VerifyAll()
    self.assertEqual([10002, 10052], result)
    self.assertFalse(capped)
    self.assertEqual(None, err)

  def testSearchProjectCan_DBCapped(self):
    query_ast = query2ast.ParseUserQuery(
      'Priority:High', 'is:open', query2ast.BUILTIN_ISSUE_FIELDS,
      self.config)
    simplified_query_ast = ast2ast.PreprocessAST(
      self.cnxn, query_ast, [789], self.services, self.config)
    conj = simplified_query_ast.conjunctions[0]
    self.mox.StubOutWithMock(tracker_fulltext, 'SearchIssueFullText')
    tracker_fulltext.SearchIssueFullText(
      [789], conj, 2).AndReturn((None, False))
    self.mox.StubOutWithMock(self.services.issue, 'RunIssueQuery')
    self.services.issue.RunIssueQuery(
      self.cnxn, mox.IsA(list), mox.IsA(list), mox.IsA(list),
      shard_id=2).AndReturn(([10002, 10052], True))
    self.mox.ReplayAll()
    result, capped, err = backendsearchpipeline.SearchProjectCan(
      self.cnxn, self.services, [789], query_ast, 2, self.config)
    self.mox.VerifyAll()
    self.assertEqual([10002, 10052], result)
    self.assertTrue(capped)
    self.assertEqual(None, err)

  def testSearchProjectCan_FTSCapped(self):
    query_ast = query2ast.ParseUserQuery(
      'Priority:High', 'is:open', query2ast.BUILTIN_ISSUE_FIELDS,
      self.config)
    simplified_query_ast = ast2ast.PreprocessAST(
      self.cnxn, query_ast, [789], self.services, self.config)
    conj = simplified_query_ast.conjunctions[0]
    self.mox.StubOutWithMock(tracker_fulltext, 'SearchIssueFullText')
    tracker_fulltext.SearchIssueFullText(
      [789], conj, 2).AndReturn(([10002, 10052], True))
    self.mox.StubOutWithMock(self.services.issue, 'RunIssueQuery')
    self.services.issue.RunIssueQuery(
      self.cnxn, mox.IsA(list), mox.IsA(list), mox.IsA(list),
      shard_id=2).AndReturn(([10002, 10052], False))
    self.mox.ReplayAll()
    result, capped, err = backendsearchpipeline.SearchProjectCan(
      self.cnxn, self.services, [789], query_ast, 2, self.config)
    self.mox.VerifyAll()
    self.assertEqual([10002, 10052], result)
    self.assertTrue(capped)
    self.assertEqual(None, err)

  def testGetQueryResultIIDs(self):
    sd = ['project', 'id']
    slice_term = ('Issue.shard = %s', [2])
    query_ast = query2ast.ParseUserQuery(
      'Priority:High', 'is:open', query2ast.BUILTIN_ISSUE_FIELDS,
      self.config)
    query_ast = backendsearchpipeline._FilterSpam(query_ast)

    self.mox.StubOutWithMock(backendsearchpipeline, 'SearchProjectCan')
    backendsearchpipeline.SearchProjectCan(
      self.cnxn, self.services, [789], query_ast, 2, self.config,
      sort_directives=sd, where=[slice_term],
      query_desc='getting query issue IDs'
      ).AndReturn(([10002, 10052], False, None))
    self.mox.ReplayAll()
    result, capped, err = backendsearchpipeline._GetQueryResultIIDs(
      self.cnxn, self.services, 'is:open', 'Priority:High',
      [789], self.config, sd, slice_term, 2, 12345)
    self.mox.VerifyAll()
    self.assertEqual([10002, 10052], result)
    self.assertFalse(capped)
    self.assertEqual(None, err)
    self.assertEqual(
      ([10002, 10052], 12345),
      memcache.get('789;is:open;Priority:High;project id;2'))

  def testGetSpamQueryResultIIDs(self):
    sd = ['project', 'id']
    slice_term = ('Issue.shard = %s', [2])
    query_ast = query2ast.ParseUserQuery(
      'Priority:High is:spam', 'is:open', query2ast.BUILTIN_ISSUE_FIELDS,
      self.config)

    query_ast = backendsearchpipeline._FilterSpam(query_ast)

    self.mox.StubOutWithMock(backendsearchpipeline, 'SearchProjectCan')
    backendsearchpipeline.SearchProjectCan(
      self.cnxn, self.services, [789], query_ast, 2, self.config,
      sort_directives=sd, where=[slice_term],
      query_desc='getting query issue IDs'
      ).AndReturn(([10002, 10052], False, None))
    self.mox.ReplayAll()
    result, capped, err = backendsearchpipeline._GetQueryResultIIDs(
      self.cnxn, self.services, 'is:open', 'Priority:High is:spam',
      [789], self.config, sd, slice_term, 2, 12345)
    self.mox.VerifyAll()
    self.assertEqual([10002, 10052], result)
    self.assertFalse(capped)
    self.assertEqual(None, err)
    self.assertEqual(
      ([10002, 10052], 12345),
      memcache.get('789;is:open;Priority:High is:spam;project id;2'))
