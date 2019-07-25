# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from google.appengine.ext import ndb

from findit_v2.model.gitiles_commit import GitilesCommit
from findit_v2.model.test_failure import TestFailure
from findit_v2.model.test_failure import TestFailureAnalysis
from findit_v2.model.test_failure import TestFailureGroup
from findit_v2.model.test_failure import TestFailureInRerunBuild
from findit_v2.model.test_failure import TestRerunBuild
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.services.failure_type import StepTypeEnum
from waterfall.test import wf_testcase


class TestFailureTest(wf_testcase.WaterfallTestCase):

  def _CreateLuciBuild(self, build_id):
    build = LuciFailedBuild.Create(
        luci_project='chromium',
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=build_id,
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
        build_failure_type=StepTypeEnum.TEST)
    build.put()
    return build

  def setUp(self):
    super(TestFailureTest, self).setUp()
    self.build_id = 9876543210
    self.build = self._CreateLuciBuild(self.build_id)

  def testCreateTestFailure(self):
    step_ui_name = 'step_ui_name'
    test_name = 'test1'
    new_failure = TestFailure.Create(self.build.key, step_ui_name, test_name)
    new_failure.put()

    test_failures = TestFailure.query(TestFailure.test == test_name).fetch()
    self.assertEqual(1, len(test_failures))
    self.assertEqual(new_failure, test_failures[0])

  def testCreateTestFailureNoTest(self):
    step_ui_name = 'step_ui_name2'
    additional_properies = {'failure_type': 'xx_test_failures'}
    new_failure = TestFailure.Create(
        self.build.key, step_ui_name, None, properties=additional_properies)
    new_failure.put()

    test_failures = TestFailure.query(
        TestFailure.step_ui_name == step_ui_name).fetch()
    self.assertEqual(1, len(test_failures))
    self.assertEqual(new_failure, test_failures[0])
    self.assertEqual(additional_properies, test_failures[0].properties)

  def testGetMergedFailureKeyNoTestLevelInfo(self):
    step_ui_name = 'step_ui_name3'
    first_failure = TestFailure.Create(self.build.key, step_ui_name, None)
    first_failure.put()

    self.assertEqual(
        first_failure.key,
        TestFailure.GetMergedFailureKey({}, self.build_id, step_ui_name,
                                        frozenset([])))

  def testGetMergedFailureKey(self):
    step_ui_name = 'step_ui_name4'
    test_name = 'test'

    base_build = self._CreateLuciBuild(8765432109)
    base_failure = TestFailure.Create(base_build.key, step_ui_name, test_name)
    base_failure.put()

    first_failure = TestFailure.Create(self.build.key, step_ui_name, test_name)
    first_failure.merged_failure_key = base_failure.key
    first_failure.put()

    self.assertEqual(
        base_failure.key,
        TestFailure.GetMergedFailureKey({}, self.build_id, step_ui_name,
                                        frozenset([test_name])))

  def testGetMergedFailureForFirstFailureInGroup(self):
    failure = TestFailure.Create(self.build.key, 'step1',
                                 'test_in_first_failure')
    failure.first_failed_build_id = self.build_id
    failure.failure_group_build_id = self.build_id
    self.assertEqual(failure, failure.GetMergedFailure())

  def testGetMergedFailureWithSavedMergedFailure(self):
    step_name = 'step'
    test_name = 'test_with_merged_failure'
    dummy_merged_failure = TestFailure.Create(
        ndb.Key(LuciFailedBuild, 9876543201), step_name, test_name)
    dummy_merged_failure.put()
    failure = TestFailure.Create(self.build.key, step_name, test_name)
    failure.merged_failure_key = dummy_merged_failure.key
    self.assertEqual(dummy_merged_failure, failure.GetMergedFailure())

  def testGetMergedFailureForNonFirstFailure(self):
    first_failed_build_id = 9876543201
    step_name = 'step'
    test_name = 'test_for_non_first_failure'
    dummy_merged_failure = TestFailure.Create(
        ndb.Key(LuciFailedBuild, first_failed_build_id), step_name, test_name)
    dummy_merged_failure.put()
    failure = TestFailure.Create(self.build.key, step_name, test_name)
    failure.first_failed_build_id = first_failed_build_id
    self.assertEqual(dummy_merged_failure, failure.GetMergedFailure())

  def testTestFailureGroup(self):
    failure1 = TestFailure.Create(self.build.key, 'step1', 'test1')
    failure1.put()

    failure2 = TestFailure.Create(self.build.key, 'step2', None)
    failure2.put()

    TestFailureGroup.Create(
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
        test_failure_keys=[failure1.key, failure2.key]).put()

    group = TestFailureGroup.get_by_id(self.build_id)
    expected_test_failures = {
        'step1': {
            'tests': ['test1'],
            'properties': None
        },
        'step2': {
            'tests': [],
            'properties': None
        }
    }
    self.assertItemsEqual(expected_test_failures, group.test_failures)

  def _CreateTestFailureAnalysis(self):
    test_failure = TestFailure.Create(self.build.key, 'step', 'test')
    test_failure.put()

    analysis = TestFailureAnalysis.Create(
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
        test_failure_keys=[test_failure.key])
    analysis.Save()
    return analysis

  def testTestFailureAnalysis(self):
    self._CreateTestFailureAnalysis()
    analysis = TestFailureAnalysis.GetVersion(self.build_id)
    self.assertIsNotNone(analysis)

  def _CreateTestRerunBuild(self, build_id, commit_position, analysis_key):
    build = TestRerunBuild.Create(
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

  def testLuciRerunBuildGetFailedTests(self):
    build_id = 1234567890
    commit_position = 65432
    analysis = self._CreateTestFailureAnalysis()
    self._CreateTestRerunBuild(build_id, commit_position, analysis.key)

    rerun_build = TestRerunBuild.get_by_id(build_id, parent=analysis.key)
    rerun_build.results = []
    result = TestFailureInRerunBuild(step_ui_name='step_ui_name', test='test1')
    rerun_build.failures.append(result)

    self.assertItemsEqual({
        'step_ui_name': ['test1']
    }, rerun_build.GetFailuresInBuild())

  def testLuciRerunBuildSearch(self):
    build_id = 1234567890
    commit_position = 65432
    commit = GitilesCommit(
        gitiles_host='chromium.googlesource.com',
        gitiles_project='chromium/src',
        gitiles_ref='refs/heads/master',
        gitiles_id='git_hash',
        commit_position=commit_position)
    analysis = self._CreateTestFailureAnalysis()
    self._CreateTestRerunBuild(build_id, commit_position, analysis.key)

    rerun_builds = TestRerunBuild.SearchBuildOnCommit(analysis.key, commit)
    self.assertEqual(1, len(rerun_builds))
    self.assertEqual(build_id, rerun_builds[0].build_id)
