# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake import heuristic_analysis_util
from waterfall.test import wf_testcase


class HeuristicAnalysisUtilTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.policy = datastore_stub_util.PseudoRandomHRConsistencyPolicy(
        probability=0)
    self.testbed.init_datastore_v3_stub(consistency_policy=self.policy)
    self.testbed.init_memcache_stub()
    ndb.get_context().clear_cache()

  def tearDown(self):
    self.testbed.deactivate()

  def testGenerateSuspectedRanges(self):
    self.assertEqual([(None, 'r1')],
                     heuristic_analysis_util.GenerateSuspectedRanges(
                         ['r1'], ['r1', 'r2']))
    self.assertEqual([('r1', 'r2')],
                     heuristic_analysis_util.GenerateSuspectedRanges(
                         ['r2'], ['r1', 'r2']))
    self.assertEqual([(None, 'r1'), ('r3', 'r4'), ('r4', 'r5')],
                     heuristic_analysis_util.GenerateSuspectedRanges(
                         ['r1', 'r4', 'r5'], ['r1', 'r2', 'r3', 'r4', 'r5']))
    self.assertEqual([], heuristic_analysis_util.GenerateSuspectedRanges([],
                                                                         []))

  def testGetSuspectedRevisions(self):
    region_1 = Region(1, 5, 'r1', 'a', 'a@email.com', '2017-08-11 19:38:42')
    region_2 = Region(6, 10, 'r2', 'b', 'b@email.com', '2017-08-12 19:38:42')
    blame = Blame('r2', 'a.cc')
    blame.AddRegion(region_1)
    blame.AddRegion(region_2)
    revision_range = ['r2', 'r3']
    expected_suspected_revisions = ['r2']

    self.assertEqual(expected_suspected_revisions,
                     heuristic_analysis_util.GetSuspectedRevisions(
                         blame, revision_range))
    self.assertEqual([],
                     heuristic_analysis_util.GetSuspectedRevisions([], ['r1']))
    self.assertEqual([],
                     heuristic_analysis_util.GetSuspectedRevisions(
                         blame, ['r4']))

  def testListCommitPositionsFromSuspectedRanges(self):
    self.assertEqual(  # No heuristic results.
        [],
        heuristic_analysis_util.ListCommitPositionsFromSuspectedRanges({}, []))
    self.assertEqual(  # Blame list not available.
        [],
        heuristic_analysis_util.ListCommitPositionsFromSuspectedRanges(
            {}, [('r1', 'r2')]))
    self.assertEqual(  # Blame list available. This should be the expected case.
        [1, 2],
        heuristic_analysis_util.ListCommitPositionsFromSuspectedRanges({
            'r1': 1,
            'r2': 2,
        }, [('r1', 'r2')]))
    self.assertEqual(  # First revision is suspected.
        [1],
        heuristic_analysis_util.ListCommitPositionsFromSuspectedRanges({
            'r1': 1,
            'r2': 2,
        }, [(None, 'r1')]))
    self.assertEqual(  # Two suspects in a row 'r3' and 'r4'.
        [1, 2, 3, 4],
        heuristic_analysis_util.ListCommitPositionsFromSuspectedRanges({
            'r1': 1,
            'r2': 2,
            'r3': 3,
            'r4': 4,
        }, [(None, 'r1'), ('r2', 'r3'), ('r3', 'r4')]))

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testSaveFlakeCulpritsForSuspectedRevisions(self, mocked_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    suspected_revision = 'r1'
    suspected_revisions = [suspected_revision]

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.suspected_flake_build_number = 122
    analysis.data_points = [
        DataPoint.Create(
            build_number=122,
            commit_position=1000,
            previous_build_commit_position=999,
            git_hash=suspected_revision,
            blame_list=[suspected_revision])
    ]
    analysis.Save()

    mocked_fn.return_value = ChangeLog(
        None,
        None,
        suspected_revision,
        None,
        None,
        None,
        None,
        code_review_url='url')

    git_repo = CachedGitilesRepository(None, None)
    heuristic_analysis_util.SaveFlakeCulpritsForSuspectedRevisions(
        git_repo, analysis.key.urlsafe(), suspected_revisions)

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    suspect = FlakeCulprit.Get('chromium', suspected_revision)
    self.assertIsNotNone(suspect)
    self.assertIn(suspect.key.urlsafe(), analysis.suspect_urlsafe_keys)

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testSaveFlakeCulpritsForSuspectedRevisionsNoChangeLog(self, mocked_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    suspected_revision = 'r1'
    suspected_revisions = [suspected_revision]

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.suspected_flake_build_number = 122
    analysis.data_points = [
        DataPoint.Create(
            build_number=122,
            commit_position=1000,
            previous_build_commit_position=999,
            git_hash=suspected_revision,
            blame_list=[suspected_revision])
    ]
    analysis.Save()

    mocked_fn.return_value = None
    git_repo = CachedGitilesRepository(None, None)
    heuristic_analysis_util.SaveFlakeCulpritsForSuspectedRevisions(
        git_repo, analysis.key.urlsafe(), suspected_revisions)

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    suspect = FlakeCulprit.Get('chromium', suspected_revision)
    self.assertIsNone(suspect)

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testSaveFlakeCulpritsForSuspectedRevisionsExistingCulprit(
      self, mocked_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    suspected_revision = 'r1'
    suspected_revisions = [suspected_revision]

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.suspected_flake_build_number = 122
    analysis.data_points = [
        DataPoint.Create(
            build_number=122,
            commit_position=1000,
            previous_build_commit_position=999,
            git_hash=suspected_revision,
            blame_list=[suspected_revision])
    ]

    suspect = FlakeCulprit.Create('chromium', suspected_revision, 1000)
    suspect.url = 'url'
    suspect.put()

    analysis.suspect_urlsafe_keys = [suspect.key.urlsafe()]
    analysis.Save()

    mocked_fn.return_value = None
    git_repo = CachedGitilesRepository(None, None)
    heuristic_analysis_util.SaveFlakeCulpritsForSuspectedRevisions(
        git_repo, analysis.key.urlsafe(), suspected_revisions)

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)

    self.assertIn(suspect.key.urlsafe(), analysis.suspect_urlsafe_keys)
