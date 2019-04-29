# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from google.appengine.ext import ndb

from findit_v2.model.compile_failure import CompileFailure
from findit_v2.model.compile_failure import CompileFailureAnalysis
from findit_v2.model.compile_failure import CompileFailureGroup
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.services.failure_type import StepTypeEnum
from waterfall.test import wf_testcase


class CompileFailureTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(CompileFailureTest, self).setUp()
    self.build_id = 9876543210
    self.edges = [
        (['target1.o'], 'CXX'),
        (['target2.o'], 'ACTION'),
    ]
    build = LuciFailedBuild.Create(
        luci_project='chromium',
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=self.build_id,
        legacy_build_number=12345,
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        gitiles_id='git_hash',
        commit_position=65450,
        status=20,
        create_time=datetime(2019, 3, 28),
        start_time=datetime(2019, 3, 28, 0, 1),
        end_time=datetime(2019, 3, 28, 1),
        build_failure_type=StepTypeEnum.COMPILE)
    build.put()

    self.target_entities = []
    for output_targets, rule in self.edges:
      target = CompileFailure.Create(build.key, 'compile', output_targets, rule)
      target.put()
      self.target_entities.append(target)

  def testCompileFailure(self):
    build_key = ndb.Key('LuciFailedBuild', self.build_id)
    failures_in_build = CompileFailure.query(ancestor=build_key).fetch()
    self.assertEqual(2, len(failures_in_build))
    self.assertItemsEqual([['target1.o'], ['target2.o']],
                          [f.output_targets for f in failures_in_build])

  def testCompileFailureGroup(self):
    CompileFailureGroup.Create(
        luci_project='chromium',
        luci_bucket='ci',
        build_id=self.build_id,
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        last_passed_gitiles_id='last_passed_git_hash',
        last_passed_cp=65432,
        first_failed_gitiles_id='first_failure_git_hash',
        first_failed_cp=65450,
        compile_failure_keys=[te.key for te in self.target_entities]).put()

    group = CompileFailureGroup.get_by_id(self.build_id)
    self.assertItemsEqual(['target1.o', 'target2.o'], group.failed_targets)

  def testCompileFailureAnalysis(self):
    analysis = CompileFailureAnalysis.Create(
        luci_project='chromium',
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=self.build_id,
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        last_passed_gitiles_id='last_passed_git_hash',
        last_passed_cp=65432,
        first_failed_gitiles_id='first_failure_git_hash',
        first_failed_cp=65450,
        rerun_builder_id='findit_variables',
        compile_failure_keys=[te.key for te in self.target_entities])
    analysis.Save()

    analysis = CompileFailureAnalysis.GetVersion(self.build_id)
    self.assertIsNotNone(analysis)
