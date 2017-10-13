# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the frontendsearchpipeline module."""

import mox
import unittest

from google.appengine.api import memcache
from google.appengine.api import modules
from google.appengine.ext import testbed
from google.appengine.api import urlfetch

import settings
from framework import sorting
from framework import urls
from proto import ast_pb2
from proto import project_pb2
from proto import tracker_pb2
from search import frontendsearchpipeline
from search import searchpipeline
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


# Just an example timestamp.  The value does not matter.
NOW = 2444950132


class FrontendSearchPipelineTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.services = service_manager.Services(
        user=fake.UserService(),
        project=fake.ProjectService(),
        issue=fake.IssueService(),
        config=fake.ConfigService(),
        cache_manager=fake.CacheManager())
    self.services.user.TestAddUser('a@example.com', 111L)
    self.project = self.services.project.TestAddProject('proj', project_id=789)
    self.mr = testing_helpers.MakeMonorailRequest(
      path='/p/proj/issues/list', project=self.project)
    self.mr.me_user_id = 111L

    self.issue_1 = fake.MakeTestIssue(
      789, 1, 'one', 'New', 111L, labels=['Priority-High'])
    self.services.issue.TestAddIssue(self.issue_1)
    self.issue_2 = fake.MakeTestIssue(
      789, 2, 'two', 'New', 111L, labels=['Priority-Low'])
    self.services.issue.TestAddIssue(self.issue_2)
    self.issue_3 = fake.MakeTestIssue(
      789, 3, 'three', 'New', 111L, labels=['Priority-Medium'])
    self.services.issue.TestAddIssue(self.issue_3)
    self.mr.sort_spec = 'Priority'

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

  def testSearchForIIDs_AllResultsCached_AllAtRiskCached(self):
    unfiltered_iids = {(1, 'p:v'): [1001, 1011]}
    nonviewable_iids = {1: set()}
    self.mox.StubOutWithMock(frontendsearchpipeline, '_StartBackendSearch')
    frontendsearchpipeline._StartBackendSearch(
      self.mr, ['proj'], [789], mox.IsA(tracker_pb2.ProjectIssueConfig),
      unfiltered_iids, {}, nonviewable_iids, set(), self.services).AndReturn([])
    self.mox.StubOutWithMock(frontendsearchpipeline, '_FinishBackendSearch')
    frontendsearchpipeline._FinishBackendSearch([])
    self.mox.ReplayAll()

    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    pipeline.unfiltered_iids = unfiltered_iids
    pipeline.nonviewable_iids = nonviewable_iids
    pipeline.SearchForIIDs()
    self.mox.VerifyAll()
    self.assertEqual(2, pipeline.total_count)
    self.assertEqual([1001, 1011], pipeline.filtered_iids[(1, 'p:v')])

  def testSearchForIIDs_CrossProject_AllViewable(self):
    self.services.project.TestAddProject('other', project_id=790)
    unfiltered_iids = {(1, 'p:v'): [1001, 1011, 2001]}
    nonviewable_iids = {1: set()}
    self.mr.query_project_names = ['other']
    self.mox.StubOutWithMock(frontendsearchpipeline, '_StartBackendSearch')
    frontendsearchpipeline._StartBackendSearch(
      self.mr, ['other', 'proj'], [789, 790],
      mox.IsA(tracker_pb2.ProjectIssueConfig),
      unfiltered_iids, {}, nonviewable_iids, set(), self.services).AndReturn([])
    self.mox.StubOutWithMock(frontendsearchpipeline, '_FinishBackendSearch')
    frontendsearchpipeline._FinishBackendSearch([])
    self.mox.ReplayAll()

    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    pipeline.unfiltered_iids = unfiltered_iids
    pipeline.nonviewable_iids = nonviewable_iids
    pipeline.SearchForIIDs()
    self.mox.VerifyAll()
    self.assertEqual(3, pipeline.total_count)
    self.assertEqual([1001, 1011, 2001], pipeline.filtered_iids[(1, 'p:v')])

  def testSearchForIIDs_CrossProject_MembersOnlyOmitted(self):
    self.services.project.TestAddProject(
        'other', project_id=790, access=project_pb2.ProjectAccess.MEMBERS_ONLY)
    unfiltered_iids = {(1, 'p:v'): [1001, 1011]}
    nonviewable_iids = {1: set()}
    # project 'other' gets filtered out before the backend call.
    self.mr.query_project_names = ['other']
    self.mox.StubOutWithMock(frontendsearchpipeline, '_StartBackendSearch')
    frontendsearchpipeline._StartBackendSearch(
      self.mr, ['proj'], [789],
      mox.IsA(tracker_pb2.ProjectIssueConfig),
      unfiltered_iids, {}, nonviewable_iids, set(), self.services).AndReturn([])
    self.mox.StubOutWithMock(frontendsearchpipeline, '_FinishBackendSearch')
    frontendsearchpipeline._FinishBackendSearch([])
    self.mox.ReplayAll()

    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    pipeline.unfiltered_iids = unfiltered_iids
    pipeline.nonviewable_iids = nonviewable_iids
    pipeline.SearchForIIDs()
    self.mox.VerifyAll()
    self.assertEqual(2, pipeline.total_count)
    self.assertEqual([1001, 1011], pipeline.filtered_iids[(1, 'p:v')])

  def testMergeAndSortIssues_EmptyResult(self):
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    pipeline.filtered_iids = {0: [], 1: [], 2: []}

    pipeline.MergeAndSortIssues()
    self.assertEqual([], pipeline.allowed_iids)
    self.assertEqual([], pipeline.allowed_results)
    self.assertEqual({}, pipeline.users_by_id)

  def testMergeAndSortIssues_Normal(self):
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    # In this unit test case we are not calling SearchForIIDs(), instead just
    # set pipeline.filtered_iids directly.
    pipeline.filtered_iids = {
      0: [],
      1: [self.issue_1.issue_id],
      2: [self.issue_2.issue_id],
      3: [self.issue_3.issue_id]
      }

    pipeline.MergeAndSortIssues()
    self.assertEqual(
      [self.issue_1.issue_id, self.issue_2.issue_id, self.issue_3.issue_id],
      pipeline.allowed_iids)
    self.assertEqual(
      [self.issue_1, self.issue_3, self.issue_2],  # high, medium, low.
      pipeline.allowed_results)
    self.assertEqual([111L], pipeline.users_by_id.keys())

  def testDetermineIssuePosition_Normal(self):
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    # In this unit test case we are not calling SearchForIIDs(), instead just
    # set pipeline.filtered_iids directly.
    pipeline.filtered_iids = {
      0: [],
      1: [self.issue_1.issue_id],
      2: [self.issue_2.issue_id],
      3: [self.issue_3.issue_id]
      }

    prev_iid, index, next_iid = pipeline.DetermineIssuePosition(self.issue_3)
    # The total ordering is issue_1, issue_3, issue_2 for high, med, low.
    self.assertEqual(self.issue_1.issue_id, prev_iid)
    self.assertEqual(1, index)
    self.assertEqual(self.issue_2.issue_id, next_iid)

  def testDetermineIssuePosition_NotInResults(self):
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    # In this unit test case we are not calling SearchForIIDs(), instead just
    # set pipeline.filtered_iids directly.
    pipeline.filtered_iids = {
      0: [],
      1: [self.issue_1.issue_id],
      2: [self.issue_2.issue_id],
      3: []
      }

    prev_iid, index, next_iid = pipeline.DetermineIssuePosition(self.issue_3)
    # The total ordering is issue_1, issue_3, issue_2 for high, med, low.
    self.assertEqual(None, prev_iid)
    self.assertEqual(None, index)
    self.assertEqual(None, next_iid)

  def testDetermineIssuePositionInShard_IssueIsInShard(self):
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    # Let's assume issues 1, 2, and 3 are all in the same shard.
    pipeline.filtered_iids = {
      0: [self.issue_1.issue_id, self.issue_2.issue_id, self.issue_3.issue_id],
      }

    # The total ordering is issue_1, issue_3, issue_2 for high, med, low.
    prev_cand, index, next_cand = pipeline._DetermineIssuePositionInShard(
      0, self.issue_1, {})
    self.assertEqual(None, prev_cand)
    self.assertEqual(0, index)
    self.assertEqual(self.issue_3, next_cand)

    prev_cand, index, next_cand = pipeline._DetermineIssuePositionInShard(
      0, self.issue_3, {})
    self.assertEqual(self.issue_1, prev_cand)
    self.assertEqual(1, index)
    self.assertEqual(self.issue_2, next_cand)

    prev_cand, index, next_cand = pipeline._DetermineIssuePositionInShard(
      0, self.issue_2, {})
    self.assertEqual(self.issue_3, prev_cand)
    self.assertEqual(2, index)
    self.assertEqual(None, next_cand)

  def testDetermineIssuePositionInShard_IssueIsNotInShard(self):
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)

    # The total ordering is issue_1, issue_3, issue_2 for high, med, low.
    pipeline.filtered_iids = {
      0: [self.issue_2.issue_id, self.issue_3.issue_id],
      }
    prev_cand, index, next_cand = pipeline._DetermineIssuePositionInShard(
      0, self.issue_1, {})
    self.assertEqual(None, prev_cand)
    self.assertEqual(0, index)
    self.assertEqual(self.issue_3, next_cand)

    pipeline.filtered_iids = {
      0: [self.issue_1.issue_id, self.issue_2.issue_id],
      }
    prev_cand, index, next_cand = pipeline._DetermineIssuePositionInShard(
      0, self.issue_3, {})
    self.assertEqual(self.issue_1, prev_cand)
    self.assertEqual(1, index)
    self.assertEqual(self.issue_2, next_cand)

    pipeline.filtered_iids = {
      0: [self.issue_1.issue_id, self.issue_3.issue_id],
      }
    prev_cand, index, next_cand = pipeline._DetermineIssuePositionInShard(
      0, self.issue_2, {})
    self.assertEqual(self.issue_3, prev_cand)
    self.assertEqual(2, index)
    self.assertEqual(None, next_cand)

  def testFetchAllSamples_Empty(self):
    filtered_iids = {}
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
        self.mr, self.services, 100)
    samples_by_shard, sample_iids_to_shard = pipeline._FetchAllSamples(
        filtered_iids)
    self.assertEqual({}, samples_by_shard)
    self.assertEqual({}, sample_iids_to_shard)

  def testFetchAllSamples_SmallResultsPerShard(self):
    filtered_iids = {
        0: [100, 110, 120],
        1: [101, 111, 121],
        }
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
        self.mr, self.services, 100)

    samples_by_shard, sample_iids_to_shard = pipeline._FetchAllSamples(
        filtered_iids)
    self.assertEqual(2, len(samples_by_shard))
    self.assertEqual(0, len(sample_iids_to_shard))

  def testFetchAllSamples_Normal(self):
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
        self.mr, self.services, 100)
    issues = self.MakeIssues(23)
    filtered_iids = {
        0: [issue.issue_id for issue in issues],
        }

    samples_by_shard, sample_iids_to_shard = pipeline._FetchAllSamples(
        filtered_iids)
    self.assertEqual(1, len(samples_by_shard))
    self.assertEqual(2, len(samples_by_shard[0]))
    self.assertEqual(2, len(sample_iids_to_shard))
    for sample_iid in sample_iids_to_shard:
      shard_key = sample_iids_to_shard[sample_iid]
      self.assertIn(sample_iid, filtered_iids[shard_key])

  def testChooseSampleIssues_Empty(self):
    """When the search gave no results, there cannot be any samples."""
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    issue_ids = []
    on_hand_issues, needed_iids = pipeline._ChooseSampleIssues(issue_ids)
    self.assertEqual({}, on_hand_issues)
    self.assertEqual([], needed_iids)

  def testChooseSampleIssues_Small(self):
    """When the search gave few results, don't bother with samples."""
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    issue_ids = [78901, 78902]
    on_hand_issues, needed_iids = pipeline._ChooseSampleIssues(issue_ids)
    self.assertEqual({}, on_hand_issues)
    self.assertEqual([], needed_iids)

  def MakeIssues(self, num_issues):
    issues = []
    for i in range(num_issues):
      issue = fake.MakeTestIssue(789, 100 + i, 'samp test', 'New', 111L)
      issues.append(issue)
      self.services.issue.TestAddIssue(issue)
    return issues

  def testChooseSampleIssues_Normal(self):
    """We will choose at least one sample for every 10 results in a shard."""
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    issues = self.MakeIssues(23)
    issue_ids = [issue.issue_id for issue in issues]
    on_hand_issues, needed_iids = pipeline._ChooseSampleIssues(issue_ids)
    self.assertEqual({}, on_hand_issues)
    self.assertEqual(2, len(needed_iids))
    for sample_iid in needed_iids:
      self.assertIn(sample_iid, issue_ids)

  def testLookupNeededUsers(self):
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)

    pipeline._LookupNeededUsers([])
    self.assertEqual([], pipeline.users_by_id.keys())

    pipeline._LookupNeededUsers([self.issue_1, self.issue_2, self.issue_3])
    self.assertEqual([111L], pipeline.users_by_id.keys())

  def testPaginate_Grid(self):
    self.mr.mode = 'grid'
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    pipeline.allowed_iids = [
      self.issue_1.issue_id, self.issue_2.issue_id, self.issue_3.issue_id]
    pipeline.allowed_results = [self.issue_1, self.issue_2, self.issue_3]
    pipeline.total_count = len(pipeline.allowed_results)
    pipeline.Paginate()
    self.assertEqual(
      [self.issue_1, self.issue_2, self.issue_3],
      pipeline.visible_results)

  def testPaginate_List(self):
    pipeline = frontendsearchpipeline.FrontendSearchPipeline(
      self.mr, self.services, 100)
    pipeline.allowed_iids = [
      self.issue_1.issue_id, self.issue_2.issue_id, self.issue_3.issue_id]
    pipeline.allowed_results = [self.issue_1, self.issue_2, self.issue_3]
    pipeline.total_count = len(pipeline.allowed_results)
    pipeline.Paginate()
    self.assertEqual(
      [self.issue_1, self.issue_2, self.issue_3],
      pipeline.visible_results)
    self.assertFalse(pipeline.pagination.limit_reached)


class FrontendSearchPipelineMethodsTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.testbed.init_memcache_stub()

    self.project_id = 789
    self.default_config = tracker_bizobj.MakeDefaultProjectIssueConfig(
        self.project_id)
    self.services = service_manager.Services(
        project=fake.ProjectService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=self.project_id)

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testMakeBackendCallback(self):
    called_with = []

    def func(a, b):
      called_with.append((a, b))

    callback = frontendsearchpipeline._MakeBackendCallback(func, 10, 20)
    callback()
    self.assertEqual([(10, 20)], called_with)

  def testParseUserQuery_CheckQuery(self):
    warnings = []
    msg = frontendsearchpipeline._CheckQuery(
        'cnxn', self.services, 'ok query', self.default_config,
        [self.project_id], warnings=warnings)
    self.assertIsNone(msg)
    self.assertEqual([], warnings)

    warnings = []
    msg = frontendsearchpipeline._CheckQuery(
        'cnxn', self.services, 'modified:0-0-0', self.default_config,
        [self.project_id], warnings=warnings)
    self.assertEqual(
        'Could not parse date: 0-0-0',
        msg)

    warnings = []
    msg = frontendsearchpipeline._CheckQuery(
        'cnxn', self.services, 'foo (bar)', self.default_config,
        [self.project_id], warnings=warnings)
    self.assertIsNone(msg)
    self.assertEqual(
        ['Parentheses are ignored in user queries.'],
        warnings)

    warnings = []
    msg = frontendsearchpipeline._CheckQuery(
        'cnxn', self.services, 'blocking:3.14', self.default_config,
        [self.project_id], warnings=warnings)
    self.assertEqual(
        'Could not parse issue reference: 3.14',
        msg)
    self.assertEqual([], warnings)

  def testStartBackendSearch(self):
    # TODO(jrobbins): write this test.
    pass

  def testFinishBackendSearch(self):
    # TODO(jrobbins): write this test.
    pass

  def testGetProjectTimestamps_NoneSet(self):
    project_shard_timestamps = frontendsearchpipeline._GetProjectTimestamps(
      [], [])
    self.assertEqual({}, project_shard_timestamps)

    project_shard_timestamps = frontendsearchpipeline._GetProjectTimestamps(
      [], [(0, (0, 'p:v')), (1, (1, 'p:v')), (2, (2, 'p:v'))])
    self.assertEqual({}, project_shard_timestamps)

    project_shard_timestamps = frontendsearchpipeline._GetProjectTimestamps(
      [789], [(0, (0, 'p:v')), (1, (1, 'p:v')), (2, (2, 'p:v'))])
    self.assertEqual({}, project_shard_timestamps)

  def testGetProjectTimestamps_SpecificProjects(self):
    memcache.set('789;0', NOW)
    memcache.set('789;1', NOW - 1000)
    memcache.set('789;2', NOW - 3000)
    project_shard_timestamps = frontendsearchpipeline._GetProjectTimestamps(
      [789], [(0, (0, 'p:v')), (1, (1, 'p:v')), (2, (2, 'p:v'))])
    self.assertEqual(
      { (789, 0): NOW,
        (789, 1): NOW - 1000,
        (789, 2): NOW - 3000,
        },
      project_shard_timestamps)

    memcache.set('790;0', NOW)
    memcache.set('790;1', NOW - 10000)
    memcache.set('790;2', NOW - 30000)
    project_shard_timestamps = frontendsearchpipeline._GetProjectTimestamps(
      [789, 790], [(0, (0, 'p:v')), (1, (1, 'p:v')), (2, (2, 'p:v'))])
    self.assertEqual(
      { (789, 0): NOW,
        (789, 1): NOW - 1000,
        (789, 2): NOW - 3000,
        (790, 0): NOW,
        (790, 1): NOW - 10000,
        (790, 2): NOW - 30000,
        },
      project_shard_timestamps)

  def testGetProjectTimestamps_SiteWide(self):
    memcache.set('all;0', NOW)
    memcache.set('all;1', NOW - 10000)
    memcache.set('all;2', NOW - 30000)
    project_shard_timestamps = frontendsearchpipeline._GetProjectTimestamps(
      [], [(0, (0, 'p:v')), (1, (1, 'p:v')), (2, (2, 'p:v'))])
    self.assertEqual(
      { ('all', 0): NOW,
        ('all', 1): NOW - 10000,
        ('all', 2): NOW - 30000,
        },
      project_shard_timestamps)

  def testGetNonviewableIIDs_SearchMissSoNoOp(self):
    """If search cache missed, don't bother looking up nonviewable IIDs."""
    unfiltered_iids_dict = {}  # No cached search results found.
    rpc_tuples = []  # Nothing should accumulate here in this case.
    nonviewable_iids = {}  # Nothing should accumulate here in this case.
    processed_invalidations_up_to = 12345
    frontendsearchpipeline._GetNonviewableIIDs(
        [789], 111L, unfiltered_iids_dict.keys(), rpc_tuples, nonviewable_iids,
        {}, processed_invalidations_up_to, True)
    self.assertEqual([], rpc_tuples)
    self.assertEqual({}, nonviewable_iids)

  def testGetNonviewableIIDs_SearchHitThenNonviewableHit(self):
    """If search cache hit, get nonviewable info from cache."""
    unfiltered_iids_dict = {
      1: [10001, 10021],
      2: ['the search result issue_ids do not matter'],
      }
    rpc_tuples = []  # Nothing should accumulate here in this case.
    nonviewable_iids = {}  # Our mock results should end up here.
    processed_invalidations_up_to = 12345
    memcache.set('nonviewable:789;111;1',
                 ([10001, 10031], processed_invalidations_up_to - 10))
    memcache.set('nonviewable:789;111;2',
                 ([10002, 10042], processed_invalidations_up_to - 30))

    project_shard_timestamps = {
      (789, 1): 0,  # not stale
      (789, 2): 0,  # not stale
      }
    frontendsearchpipeline._GetNonviewableIIDs(
        [789], 111L, unfiltered_iids_dict.keys(), rpc_tuples, nonviewable_iids,
        project_shard_timestamps, processed_invalidations_up_to, True)
    self.assertEqual([], rpc_tuples)
    self.assertEqual({1: {10001, 10031}, 2: {10002, 10042}}, nonviewable_iids)

  def testGetNonviewableIIDs_SearchHitNonviewableMissSoStartRPC(self):
    """If search hit and n-v miss, create RPCs to get nonviewable info."""
    self.mox.StubOutWithMock(
        frontendsearchpipeline, '_StartBackendNonviewableCall')
    unfiltered_iids_dict = {
      2: ['the search result issue_ids do not matter'],
      }
    rpc_tuples = []  # One RPC object should accumulate here.
    nonviewable_iids = {}  # This will stay empty until RPCs complete.
    processed_invalidations_up_to = 12345
    # Nothing is set in memcache for this case.
    a_fake_rpc = testing_helpers.Blank(callback=None)
    frontendsearchpipeline._StartBackendNonviewableCall(
      789, 111L, 2, processed_invalidations_up_to).AndReturn(a_fake_rpc)
    self.mox.ReplayAll()

    frontendsearchpipeline._GetNonviewableIIDs(
        [789], 111L, unfiltered_iids_dict.keys(), rpc_tuples, nonviewable_iids,
        {}, processed_invalidations_up_to, True)
    self.mox.VerifyAll()
    _, sid_0, rpc_0 = rpc_tuples[0]
    self.assertEqual(2, sid_0)
    self.assertEqual({}, nonviewable_iids)
    self.assertEqual(a_fake_rpc, rpc_0)
    self.assertIsNotNone(a_fake_rpc.callback)

  def testAccumulateNonviewableIIDs_MemcacheHitForProject(self):
    processed_invalidations_up_to = 12345
    cached_dict = {
      '789;111;2': ([10002, 10042], processed_invalidations_up_to - 10),
      '789;111;3': ([10003, 10093], processed_invalidations_up_to - 30),
      }
    rpc_tuples = []  # Nothing should accumulate here.
    nonviewable_iids = {1: {10001}}  # This will gain the shard 2 values.
    project_shard_timestamps = {
      (789, 1): 0,  # not stale
      (789, 2): 0,  # not stale
      }
    frontendsearchpipeline._AccumulateNonviewableIIDs(
      789, 111L, 2, cached_dict, nonviewable_iids, project_shard_timestamps,
      rpc_tuples, processed_invalidations_up_to)
    self.assertEqual([], rpc_tuples)
    self.assertEqual({1: {10001}, 2: {10002, 10042}}, nonviewable_iids)

  def testAccumulateNonviewableIIDs_MemcacheStaleForProject(self):
    self.mox.StubOutWithMock(
      frontendsearchpipeline, '_StartBackendNonviewableCall')
    processed_invalidations_up_to = 12345
    cached_dict = {
      '789;111;2': ([10002, 10042], processed_invalidations_up_to - 10),
      '789;111;3': ([10003, 10093], processed_invalidations_up_to - 30),
      }
    rpc_tuples = []  # Nothing should accumulate here.
    nonviewable_iids = {1: {10001}}  # Nothing added here until RPC completes
    project_shard_timestamps = {
      (789, 1): 0,  # not stale
      (789, 2): processed_invalidations_up_to,  # stale!
      }
    a_fake_rpc = testing_helpers.Blank(callback=None)
    frontendsearchpipeline._StartBackendNonviewableCall(
      789, 111L, 2, processed_invalidations_up_to).AndReturn(a_fake_rpc)
    self.mox.ReplayAll()

    frontendsearchpipeline._AccumulateNonviewableIIDs(
      789, 111L, 2, cached_dict, nonviewable_iids, project_shard_timestamps,
      rpc_tuples, processed_invalidations_up_to)
    self.mox.VerifyAll()
    _, sid_0, rpc_0 = rpc_tuples[0]
    self.assertEqual(2, sid_0)
    self.assertEqual(a_fake_rpc, rpc_0)
    self.assertIsNotNone(a_fake_rpc.callback)
    self.assertEqual({1: {10001}}, nonviewable_iids)

  def testAccumulateNonviewableIIDs_MemcacheHitForWholeSite(self):
    processed_invalidations_up_to = 12345
    cached_dict = {
      'all;111;2': ([10002, 10042], processed_invalidations_up_to - 10),
      'all;111;3': ([10003, 10093], processed_invalidations_up_to - 30),
      }
    rpc_tuples = []  # Nothing should accumulate here.
    nonviewable_iids = {1: {10001}}  # This will gain the shard 2 values.
    project_shard_timestamps = {
      (None, 1): 0,  # not stale
      (None, 2): 0,  # not stale
      }
    frontendsearchpipeline._AccumulateNonviewableIIDs(
      None, 111L, 2, cached_dict, nonviewable_iids, project_shard_timestamps,
      rpc_tuples, processed_invalidations_up_to)
    self.assertEqual([], rpc_tuples)
    self.assertEqual({1: {10001}, 2: {10002, 10042}}, nonviewable_iids)

  def testAccumulateNonviewableIIDs_MemcacheMissSoStartRPC(self):
    self.mox.StubOutWithMock(
        frontendsearchpipeline, '_StartBackendNonviewableCall')
    cached_dict = {}  # Nothing here, so it is an at-risk cache miss.
    rpc_tuples = []  # One RPC should accumulate here.
    nonviewable_iids = {1: {10001}}  # Nothing added here until RPC completes.
    processed_invalidations_up_to = 12345
    a_fake_rpc = testing_helpers.Blank(callback=None)
    frontendsearchpipeline._StartBackendNonviewableCall(
      789, 111L, 2, processed_invalidations_up_to).AndReturn(a_fake_rpc)
    self.mox.ReplayAll()

    frontendsearchpipeline._AccumulateNonviewableIIDs(
      789, 111L, 2, cached_dict, nonviewable_iids, {}, rpc_tuples,
      processed_invalidations_up_to)
    self.mox.VerifyAll()
    _, sid_0, rpc_0 = rpc_tuples[0]
    self.assertEqual(2, sid_0)
    self.assertEqual(a_fake_rpc, rpc_0)
    self.assertIsNotNone(a_fake_rpc.callback)
    self.assertEqual({1: {10001}}, nonviewable_iids)

  def testGetCachedSearchResults(self):
    # TODO(jrobbins): Write this test.
    pass

  def testMakeBackendRequestHeaders(self):
    headers = frontendsearchpipeline._MakeBackendRequestHeaders(False)
    self.assertNotIn('X-AppEngine-FailFast', headers)
    headers = frontendsearchpipeline._MakeBackendRequestHeaders(True)
    self.assertEqual('Yes', headers['X-AppEngine-FailFast'])

  def testStartBackendSearchCall(self):
    self.mox.StubOutWithMock(urlfetch, 'create_rpc')
    self.mox.StubOutWithMock(urlfetch, 'make_fetch_call')
    self.mox.StubOutWithMock(modules, 'get_hostname')
    a_fake_rpc = testing_helpers.Blank(callback=None)
    urlfetch.create_rpc(deadline=settings.backend_deadline).AndReturn(
      a_fake_rpc)
    modules.get_hostname(module='besearch')
    urlfetch.make_fetch_call(
      a_fake_rpc, mox.StrContains(urls.BACKEND_SEARCH), follow_redirects=False,
      headers=mox.IsA(dict))
    self.mox.ReplayAll()

    processed_invalidations_up_to = 12345
    mr = testing_helpers.MakeMonorailRequest(path='/p/proj/issues/list?q=foo')
    mr.me_user_id = 111L
    frontendsearchpipeline._StartBackendSearchCall(
      mr, ['proj'], (2, 'priority=high'), processed_invalidations_up_to)
    self.mox.VerifyAll()

  def testStartBackendNonviewableCall(self):
    self.mox.StubOutWithMock(urlfetch, 'create_rpc')
    self.mox.StubOutWithMock(urlfetch, 'make_fetch_call')
    self.mox.StubOutWithMock(modules, 'get_hostname')
    a_fake_rpc = testing_helpers.Blank(callback=None)
    urlfetch.create_rpc(deadline=settings.backend_deadline).AndReturn(
      a_fake_rpc)
    modules.get_hostname(module='besearch')
    urlfetch.make_fetch_call(
      a_fake_rpc, mox.StrContains(urls.BACKEND_NONVIEWABLE),
      follow_redirects=False, headers=mox.IsA(dict))
    self.mox.ReplayAll()

    processed_invalidations_up_to = 12345
    frontendsearchpipeline._StartBackendNonviewableCall(
      789, 111L, 2, processed_invalidations_up_to)
    self.mox.VerifyAll()

  def testHandleBackendSearchResponse_500(self):
    response_str = 'There was a problem processing the query.'
    rpc = testing_helpers.Blank(
      get_result=lambda: testing_helpers.Blank(
          content=response_str, status_code=500))
    rpc_tuple = (NOW, 2, rpc)
    rpc_tuples = []  # Nothing should be added for this case.
    filtered_iids = {}  # Search results should accumlate here, per-shard.
    search_limit_reached = {}  # Booleans accumulate here, per-shard.
    processed_invalidations_up_to = 12345

    mr = testing_helpers.MakeMonorailRequest(path='/p/proj/issues/list?q=foo')
    mr.me_user_id = 111L
    error_responses = set()

    self.mox.StubOutWithMock(frontendsearchpipeline, '_StartBackendSearchCall')
    frontendsearchpipeline._HandleBackendSearchResponse(
     mr, ['proj'], rpc_tuple, rpc_tuples, 0, filtered_iids,
      search_limit_reached, processed_invalidations_up_to, error_responses)
    self.assertEqual([], rpc_tuples)
    self.assertIn(2, error_responses)

  def testHandleBackendSearchResponse_Error(self):
    response_str = (
      '})]\'\n'
      '{'
      ' "unfiltered_iids": [],'
      ' "search_limit_reached": false,'
      ' "error": "Invalid query"'
      '}'
      )
    rpc = testing_helpers.Blank(
      get_result=lambda: testing_helpers.Blank(
          content=response_str, status_code=200))
    rpc_tuple = (NOW, 2, rpc)
    rpc_tuples = []  # Nothing should be added for this case.
    filtered_iids = {}  # Search results should accumlate here, per-shard.
    search_limit_reached = {}  # Booleans accumulate here, per-shard.
    processed_invalidations_up_to = 12345

    mr = testing_helpers.MakeMonorailRequest(path='/p/proj/issues/list?q=foo')
    mr.me_user_id = 111L
    error_responses = set()
    frontendsearchpipeline._HandleBackendSearchResponse(
      mr, ['proj'], rpc_tuple, rpc_tuples, 2, filtered_iids,
      search_limit_reached, processed_invalidations_up_to, error_responses)
    self.assertEqual([], rpc_tuples)
    self.assertEqual({2: []}, filtered_iids)
    self.assertEqual({2: False}, search_limit_reached)
    self.assertEqual({2}, error_responses)


  def testHandleBackendSearchResponse_Normal(self):
    response_str = (
      '})]\'\n'
      '{'
      ' "unfiltered_iids": [10002, 10042],'
      ' "search_limit_reached": false'
      '}'
      )
    rpc = testing_helpers.Blank(
      get_result=lambda: testing_helpers.Blank(
          content=response_str, status_code=200))
    rpc_tuple = (NOW, 2, rpc)
    rpc_tuples = []  # Nothing should be added for this case.
    filtered_iids = {}  # Search results should accumlate here, per-shard.
    search_limit_reached = {}  # Booleans accumulate here, per-shard.
    processed_invalidations_up_to = 12345

    mr = testing_helpers.MakeMonorailRequest(path='/p/proj/issues/list?q=foo')
    mr.me_user_id = 111L
    error_responses = set()
    frontendsearchpipeline._HandleBackendSearchResponse(
      mr, ['proj'], rpc_tuple, rpc_tuples, 2, filtered_iids,
      search_limit_reached, processed_invalidations_up_to, error_responses)
    self.assertEqual([], rpc_tuples)
    self.assertEqual({2: [10002, 10042]}, filtered_iids)
    self.assertEqual({2: False}, search_limit_reached)


  def testHandleBackendSearchResponse_TriggersRetry(self):
    response_str = None
    rpc = testing_helpers.Blank(
      get_result=lambda: testing_helpers.Blank(content=response_str))
    rpc_tuple = (NOW, 2, rpc)
    rpc_tuples = []  # New RPC should be appended here
    filtered_iids = {}  # No change here until retry completes.
    search_limit_reached = {}  # No change here until retry completes.
    processed_invalidations_up_to = 12345
    error_responses = set()

    mr = testing_helpers.MakeMonorailRequest(path='/p/proj/issues/list?q=foo')
    mr.me_user_id = 111L

    self.mox.StubOutWithMock(frontendsearchpipeline, '_StartBackendSearchCall')
    a_fake_rpc = testing_helpers.Blank(callback=None)
    rpc = frontendsearchpipeline._StartBackendSearchCall(
      mr, ['proj'], 2, processed_invalidations_up_to, failfast=False
      ).AndReturn(a_fake_rpc)
    self.mox.ReplayAll()

    frontendsearchpipeline._HandleBackendSearchResponse(
      mr, ['proj'], rpc_tuple, rpc_tuples, 2, filtered_iids,
      search_limit_reached, processed_invalidations_up_to, error_responses)
    self.mox.VerifyAll()
    _, retry_shard_id, retry_rpc = rpc_tuples[0]
    self.assertEqual(2, retry_shard_id)
    self.assertEqual(a_fake_rpc, retry_rpc)
    self.assertIsNotNone(retry_rpc.callback)
    self.assertEqual({}, filtered_iids)
    self.assertEqual({}, search_limit_reached)

  def testHandleBackendNonviewableResponse_Error(self):
    response_str = 'There was an error.'
    rpc = testing_helpers.Blank(
      get_result=lambda: testing_helpers.Blank(
          content=response_str,
          status_code=500
      ))
    rpc_tuple = (NOW, 2, rpc)
    rpc_tuples = []  # Nothing should be added for this case.
    nonviewable_iids = {}  # At-risk issue IDs should accumlate here, per-shard.
    processed_invalidations_up_to = 12345

    self.mox.StubOutWithMock(
        frontendsearchpipeline, '_StartBackendNonviewableCall')
    frontendsearchpipeline._HandleBackendNonviewableResponse(
      789, 111L, 2, rpc_tuple, rpc_tuples, 0, nonviewable_iids,
      processed_invalidations_up_to)
    self.assertEqual([], rpc_tuples)
    self.assertNotEqual({2: {10002, 10042}}, nonviewable_iids)

  def testHandleBackendNonviewableResponse_Normal(self):
    response_str = (
      '})]\'\n'
      '{'
      ' "nonviewable": [10002, 10042]'
      '}'
      )
    rpc = testing_helpers.Blank(
      get_result=lambda: testing_helpers.Blank(
          content=response_str,
          status_code=200
      ))
    rpc_tuple = (NOW, 2, rpc)
    rpc_tuples = []  # Nothing should be added for this case.
    nonviewable_iids = {}  # At-risk issue IDs should accumlate here, per-shard.
    processed_invalidations_up_to = 12345

    frontendsearchpipeline._HandleBackendNonviewableResponse(
      789, 111L, 2, rpc_tuple, rpc_tuples, 2, nonviewable_iids,
      processed_invalidations_up_to)
    self.assertEqual([], rpc_tuples)
    self.assertEqual({2: {10002, 10042}}, nonviewable_iids)

  def testHandleBackendAtRiskResponse_TriggersRetry(self):
    response_str = None
    rpc = testing_helpers.Blank(
      get_result=lambda: testing_helpers.Blank(content=response_str))
    rpc_tuple = (NOW, 2, rpc)
    rpc_tuples = []  # New RPC should be appended here
    nonviewable_iids = {}  # No change here until retry completes.
    processed_invalidations_up_to = 12345

    self.mox.StubOutWithMock(
      frontendsearchpipeline, '_StartBackendNonviewableCall')
    a_fake_rpc = testing_helpers.Blank(callback=None)
    rpc = frontendsearchpipeline._StartBackendNonviewableCall(
      789, 111L, 2, processed_invalidations_up_to, failfast=False
      ).AndReturn(a_fake_rpc)
    self.mox.ReplayAll()

    frontendsearchpipeline._HandleBackendNonviewableResponse(
      789, 111L, 2, rpc_tuple, rpc_tuples, 2, nonviewable_iids,
      processed_invalidations_up_to)
    self.mox.VerifyAll()
    _, retry_shard_id, retry_rpc = rpc_tuples[0]
    self.assertEqual(2, retry_shard_id)
    self.assertIsNotNone(retry_rpc.callback)
    self.assertEqual(a_fake_rpc, retry_rpc)
    self.assertEqual({}, nonviewable_iids)

  def testSortIssues(self):
    services = service_manager.Services(
        cache_manager=fake.CacheManager())
    sorting.InitializeArtValues(services)

    mr = testing_helpers.MakeMonorailRequest(path='/p/proj/issues/list?q=foo')
    mr.sort_spec = 'priority'
    issue_1 = fake.MakeTestIssue(
      789, 1, 'one', 'New', 111L, labels=['Priority-High'])
    issue_2 = fake.MakeTestIssue(
      789, 2, 'two', 'New', 111L, labels=['Priority-Low'])
    issue_3 = fake.MakeTestIssue(
      789, 3, 'three', 'New', 111L, labels=['Priority-Medium'])
    issues = [issue_1, issue_2, issue_3]
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

    sorted_issues = frontendsearchpipeline._SortIssues(mr, issues, config, {})

    self.assertEqual(
      [issue_1, issue_3, issue_2],  # Order is high, medium, low.
      sorted_issues)


class FrontendSearchPipelineShardMethodsTest(unittest.TestCase):

  def setUp(self):
    self.sharded_iids = {
      (0, 'p:v'): [10, 20, 30, 40, 50],
      (1, 'p:v'): [21, 41, 61, 81],
      (2, 'p:v'): [42, 52, 62, 72, 102],
      (3, 'p:v'): [],
      }

  def testTotalLength_Empty(self):
    """If there were no results, the length of the sharded list is zero."""
    self.assertEqual(0, frontendsearchpipeline._TotalLength({}))

  def testTotalLength_Normal(self):
    """The length of the sharded list is the sum of the shard lengths."""
    self.assertEqual(
        14, frontendsearchpipeline._TotalLength(self.sharded_iids))

  def testReverseShards_Empty(self):
    """Reversing an empty sharded list is still empty."""
    empty_sharded_iids = {}
    frontendsearchpipeline._ReverseShards(empty_sharded_iids)
    self.assertEqual({}, empty_sharded_iids)

  def testReverseShards_Normal(self):
    """Reversing a sharded list reverses each shard."""
    frontendsearchpipeline._ReverseShards(self.sharded_iids)
    self.assertEqual(
        {(0, 'p:v'): [50, 40, 30, 20, 10],
         (1, 'p:v'): [81, 61, 41, 21],
         (2, 'p:v'): [102, 72, 62, 52, 42],
         (3, 'p:v'): [],
         },
        self.sharded_iids)

  def testTrimShardedIIDs_Empty(self):
    """If the sharded list is empty, trimming it makes no change."""
    empty_sharded_iids = {}
    frontendsearchpipeline._TrimEndShardedIIDs(empty_sharded_iids, [], 12)
    self.assertEqual({}, empty_sharded_iids)

    frontendsearchpipeline._TrimEndShardedIIDs(
        empty_sharded_iids,
        [(100, (0, 'p:v')), (88, (8, 'p:v')), (99, (9, 'p:v'))],
        12)
    self.assertEqual({}, empty_sharded_iids)

  def testTrimShardedIIDs_NoSamples(self):
    """If there are no samples, we don't trim off any IIDs."""
    orig_sharded_iids = {
      shard_id: iids[:] for shard_id, iids in self.sharded_iids.iteritems()}
    num_trimmed = frontendsearchpipeline._TrimEndShardedIIDs(
        self.sharded_iids, [], 12)
    self.assertEqual(0, num_trimmed)
    self.assertEqual(orig_sharded_iids, self.sharded_iids)

    num_trimmed = frontendsearchpipeline._TrimEndShardedIIDs(
        self.sharded_iids, [], 1)
    self.assertEqual(0, num_trimmed)
    self.assertEqual(orig_sharded_iids, self.sharded_iids)

  def testTrimShardedIIDs_Normal(self):
    """The first 3 samples contribute all needed IIDs, so trim off the rest."""
    samples = [(30, (0, 'p:v')), (41, (1, 'p:v')), (62, (2, 'p:v')),
               (40, (0, 'p:v')), (81, (1, 'p:v'))]
    num_trimmed = frontendsearchpipeline._TrimEndShardedIIDs(
        self.sharded_iids, samples, 5)
    self.assertEqual(2 + 1 + 0 + 0, num_trimmed)
    self.assertEqual(
        {  # shard_id: iids before lower-bound + iids before 1st excess sample.
         (0, 'p:v'): [10, 20] + [30],
         (1, 'p:v'): [21] + [41, 61],
         (2, 'p:v'): [42, 52] + [62, 72, 102],
         (3, 'p:v'): [] + []},
        self.sharded_iids)

  def testCalcSamplePositions_Empty(self):
    sharded_iids = {0: []}
    samples = []
    self.assertEqual(
      [], frontendsearchpipeline._CalcSamplePositions(sharded_iids, samples))

    sharded_iids = {0: [10, 20, 30, 40]}
    samples = []
    self.assertEqual(
      [], frontendsearchpipeline._CalcSamplePositions(sharded_iids, samples))

    sharded_iids = {0: []}
    # E.g., the IIDs 2 and 4 might have been trimmed out in the forward phase.
    # But we still have them in the list for the backwards phase, and they
    # should just not contribute anything to the result.
    samples = [(2, (2, 'p:v')), (4, (4, 'p:v'))]
    self.assertEqual(
      [], frontendsearchpipeline._CalcSamplePositions(sharded_iids, samples))

  def testCalcSamplePositions_Normal(self):
    samples = [(30, (0, 'p:v')), (41, (1, 'p:v')), (62, (2, 'p:v')),
               (40, (0, 'p:v')), (81, (1, 'p:v'))]
    self.assertEqual(
      [(30, (0, 'p:v'), 2),
       (41, (1, 'p:v'), 1),
       (62, (2, 'p:v'), 2),
       (40, (0, 'p:v'), 3),
       (81, (1, 'p:v'), 3)],
      frontendsearchpipeline._CalcSamplePositions(self.sharded_iids, samples))
