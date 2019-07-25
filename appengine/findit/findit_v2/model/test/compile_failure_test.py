# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from buildbucket_proto import common_pb2
from google.appengine.ext import ndb

from findit_v2.model.compile_failure import CompileFailure
from findit_v2.model.compile_failure import CompileFailureAnalysis
from findit_v2.model.compile_failure import CompileFailureGroup
from findit_v2.model.compile_failure import CompileFailureInRerunBuild
from findit_v2.model.compile_failure import CompileRerunBuild
from findit_v2.model.gitiles_commit import GitilesCommit
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.services.failure_type import StepTypeEnum
from libs import analysis_status
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
    self.assertItemsEqual([{'target1.o'}, {'target2.o'}],
                          [f.GetFailureIdentifier() for f in failures_in_build])
    self.assertEqual(self.build_id, failures_in_build[0].build_id)

  def testGetMergedFailureForFirstFailureInGroup(self):
    failure = self.target_entities[0]
    failure.first_failed_build_id = self.build_id
    failure.failure_group_build_id = self.build_id
    self.assertEqual(failure, failure.GetMergedFailure())

  def testGetMergedFailureWithSavedMergedFailure(self):
    dummy_merged_failure = CompileFailure.Create(
        ndb.Key(LuciFailedBuild, 9876543201), 'compile', ['target1.o'])
    dummy_merged_failure.put()
    failure = self.target_entities[0]
    failure.merged_failure_key = dummy_merged_failure.key
    self.assertEqual(dummy_merged_failure, failure.GetMergedFailure())

  def testGetMergedFailureForNonFirstFailure(self):
    first_failed_build_id = 9876543201
    dummy_merged_failure = CompileFailure.Create(
        ndb.Key(LuciFailedBuild, first_failed_build_id), 'compile',
        ['target1.o'])
    dummy_merged_failure.put()
    failure = self.target_entities[0]
    failure.first_failed_build_id = first_failed_build_id
    self.assertEqual(dummy_merged_failure, failure.GetMergedFailure())

  def testCompileFailureGroup(self):
    CompileFailureGroup.Create(
        luci_project='chromium',
        luci_bucket='ci',
        build_id=self.build_id,
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        last_passed_gitiles_id='last_passed_git_hash',
        last_passed_commit_position=65432,
        first_failed_gitiles_id='first_failure_git_hash',
        first_failed_commit_position=65450,
        compile_failure_keys=[te.key for te in self.target_entities]).put()

    group = CompileFailureGroup.get_by_id(self.build_id)
    self.assertItemsEqual({
        'compile': ['target1.o', 'target2.o']
    }, group.failed_targets)

  def _CreateCompileFailureAnalysis(self):
    analysis = CompileFailureAnalysis.Create(
        luci_project='chromium',
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=self.build_id,
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        last_passed_gitiles_id='last_passed_git_hash',
        last_passed_commit_position=65432,
        first_failed_gitiles_id='first_failure_git_hash',
        first_failed_commit_position=65450,
        rerun_builder_id='findit_variables',
        compile_failure_keys=[te.key for te in self.target_entities])
    analysis.Save()
    return analysis

  def testCompileFailureAnalysis(self):
    self._CreateCompileFailureAnalysis()
    analysis = CompileFailureAnalysis.GetVersion(self.build_id)
    self.assertIsNotNone(analysis)
    self.assertItemsEqual({
        'compile': ['target1.o', 'target2.o']
    }, analysis.failed_targets)
    self.assertEqual('chromium', analysis.luci_project)
    self.assertEqual('chromium/ci', analysis.bucket_id)

  def testUpdateCompileFailureAnalysis(self):
    analysis = self._CreateCompileFailureAnalysis()
    analysis.Update(status=analysis_status.COMPLETED)
    analysis = CompileFailureAnalysis.GetVersion(self.build_id)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)

  def _CreateCompileRerunBuild(self, build_id, commit_position, analysis_key):
    build = CompileRerunBuild.Create(
        luci_project='chromium',
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=build_id,
        legacy_build_number=11111,
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        gitiles_id='git_hash',
        commit_position=commit_position,
        status=1,
        create_time=datetime(2019, 3, 28),
        parent_key=analysis_key)
    build.put()

  def testLuciRerunBuild(self):
    build_id = 1234567890
    commit_position = 65432
    analysis = self._CreateCompileFailureAnalysis()
    self._CreateCompileRerunBuild(build_id, commit_position, analysis.key)

    rerun_build = CompileRerunBuild.get_by_id(build_id, parent=analysis.key)
    self.assertIsNotNone(rerun_build)

    detailed_compile_failures = {
        'compile': {
            'failures': {
                frozenset(['target1.o', 'target2.o']): {
                    'properties': {
                        'rule': 'CXX'
                    },
                    'first_failed_build': {
                        'id': 8000000000121,
                        'number': 121,
                        'commit_id': 'git_sha'
                    },
                    'last_passed_build': {
                        'id': 8000000000120,
                        'number': 120,
                        'commit_id': 'git_sha'
                    },
                },
            },
            'first_failed_build': {
                'id': 8000000000121,
                'number': 121,
                'commit_id': 'git_sha'
            },
            'last_passed_build': {
                'id': 8000000000120,
                'number': 120,
                'commit_id': 'git_sha'
            },
        },
    }
    rerun_build.SaveRerunBuildResults(common_pb2.FAILURE,
                                      detailed_compile_failures)
    result = rerun_build.GetFailedTargets()
    self.assertItemsEqual(['target1.o', 'target2.o'], result['compile'])

  def testLuciRerunBuildGetFailedTargets(self):
    build_id = 1234567890
    commit_position = 65432
    analysis = self._CreateCompileFailureAnalysis()
    self._CreateCompileRerunBuild(build_id, commit_position, analysis.key)

    rerun_build = CompileRerunBuild.get_by_id(build_id, parent=analysis.key)
    rerun_build.results = []
    for target in self.target_entities:
      result = CompileFailureInRerunBuild(
          step_ui_name=target.step_ui_name,
          output_targets=target.output_targets)
      rerun_build.failures.append(result)

    result = rerun_build.GetFailedTargets()
    self.assertItemsEqual(['target1.o', 'target2.o'], result['compile'])

  def testLuciRerunBuildSearch(self):
    build_id = 1234567890
    commit_position = 65432
    commit = GitilesCommit(
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        gitiles_id='git_hash',
        commit_position=commit_position)
    analysis = self._CreateCompileFailureAnalysis()
    self._CreateCompileRerunBuild(build_id, commit_position, analysis.key)

    rerun_builds = CompileRerunBuild.SearchBuildOnCommit(analysis.key, commit)
    self.assertEqual(1, len(rerun_builds))
    self.assertEqual(build_id, rerun_builds[0].build_id)

  def testGetMergedFailureKeyNoBuildId(self):
    with self.assertRaises(AssertionError):
      CompileFailure.GetMergedFailureKey({}, None, 's', frozenset([]))

  def testGetMergedFailureKey(self):
    self.assertEqual(
        self.target_entities[0].key,
        CompileFailure.GetMergedFailureKey(
            {}, self.build_id, 'compile',
            self.target_entities[0].GetFailureIdentifier()))

  def testGetMergedFailure(self):
    failure = CompileFailure.Create(
        ndb.Key(LuciFailedBuild, 9876543234), 'compile', ['target1.o'])
    failure.first_failed_build_id = self.build_id
    failure.put()

    self.assertEqual(self.target_entities[0], failure.GetMergedFailure())
