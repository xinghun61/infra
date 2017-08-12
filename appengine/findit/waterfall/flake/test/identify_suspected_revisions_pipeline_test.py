# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.gitiles.blame import Blame
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake.identify_suspected_revisions_pipeline import (
    IdentifySuspectedRevisionsPipeline)
from waterfall.test import wf_testcase


class IdentifySuspectedRevisionsPipelineTest(wf_testcase.WaterfallTestCase):

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

  @mock.patch.object(CachedGitilesRepository, 'GetBlame')
  def testIdentifySuspectedRevisionsPipeline(self, mocked_blame):
    mocked_blame.return_value = [Blame('r1220', 'a.b/cc')]
    test_location = {
        'line': 100,
        'file': 'a/b.cc',
    }

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 122
    analysis.data_points = [
        DataPoint.Create(
            build_number=122,
            commit_position=1220,
            git_hash='r1220',
            previous_build_commit_position=1219,
            blame_list=['r1220']),
    ]
    analysis.Save()

    culprit = FlakeCulprit.Create('chromium', 'r1220', 1220, url='url')
    culprit.put()

    pipeline_job = IdentifySuspectedRevisionsPipeline()
    pipeline_job.run(analysis.key.urlsafe(), test_location)

    analysis = MasterFlakeAnalysis.GetVersion('m', 'b', 123, 's', 't')
    self.assertEqual([culprit.key.urlsafe()],
                     analysis.suspect_urlsafe_keys)

  def testIdentifySuspectedRevisionsPipelineNoTestLocation(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 122
    analysis.data_points = [
        DataPoint.Create(
            build_number=122,
            commit_position=1220,
            git_hash='r1220',
            previous_build_commit_position=1219,
            blame_list=['r1220']),
    ]
    analysis.Save()

    pipeline_job = IdentifySuspectedRevisionsPipeline()
    self.assertEqual([],
                     pipeline_job.run(analysis.key.urlsafe(), {}))
