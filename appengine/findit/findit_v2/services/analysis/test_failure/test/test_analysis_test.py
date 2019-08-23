# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from buildbucket_proto.step_pb2 import Step
from google.appengine.ext import ndb

from findit_v2.model.gitiles_commit import Culprit
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.model.messages import findit_result
from findit_v2.model.test_failure import TestFailure
from findit_v2.model.test_failure import TestFailureAnalysis
from findit_v2.model.test_failure import TestRerunBuild
from findit_v2.services.analysis.test_failure import test_analysis
from findit_v2.services.analysis.test_failure.test_analysis_api import (
    TestAnalysisAPI)
from findit_v2.services.chromeos_api import ChromeOSProjectAPI
from findit_v2.services.context import Context
from findit_v2.services.failure_type import StepTypeEnum
from libs import analysis_status
from waterfall.test import wf_testcase


class TestAnalysisTest(wf_testcase.TestCase):

  def setUp(self):
    super(TestAnalysisTest, self).setUp()
    self.analyzed_build_id = 8000000000000
    self.context = Context(
        luci_project_name='chromeos',
        gitiles_host='gitiles.host.com',
        gitiles_project='project/name',
        gitiles_ref='ref/heads/master',
        gitiles_id='git_sha')

    self.analysis = TestFailureAnalysis.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket='postsubmit',
        luci_builder='Linux Builder',
        build_id=self.analyzed_build_id,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        last_passed_gitiles_id='last_passed_git_hash',
        last_passed_commit_position=65432,
        first_failed_gitiles_id=self.context.gitiles_id,
        first_failed_commit_position=65450,
        rerun_builder_id='chromeos/postsubmit/builder-bisect',
        test_failure_keys=[])
    self.analysis.Save()

    self.test_step_name = 'test'

  def testAnalyzeTestFailureBailoutChromium(self):
    context = Context(luci_project_name='chromium')
    self.assertFalse(test_analysis.AnalyzeTestFailure(context, None, None))

  @mock.patch.object(
      TestAnalysisAPI,
      'GetFirstFailuresInCurrentBuild',
      return_value={'failures': {}})
  @mock.patch.object(TestAnalysisAPI, 'SaveFailures')
  @mock.patch.object(TestAnalysisAPI, 'UpdateFailuresWithFirstFailureInfo')
  @mock.patch.object(ChromeOSProjectAPI, 'GetTestFailures', return_value={})
  def testAnalyzeTestFailureNoFirstFailure(self, mock_failures,
                                           mock_first_failure, *_):
    build = Build()
    test_failures = []
    self.assertFalse(
        test_analysis.AnalyzeTestFailure(self.context, build, test_failures))
    mock_failures.assert_called_once_with(build, test_failures)
    mock_first_failure.assert_called_once_with(self.context, build, {})

  @mock.patch.object(
      TestAnalysisAPI,
      'GetFirstFailuresInCurrentBuildWithoutGroup',
      return_value={
          'failures': {},
          'last_passed_build': None
      })
  @mock.patch.object(
      TestAnalysisAPI,
      'GetFirstFailuresInCurrentBuild',
      return_value={
          'failures': {
              'step_ui_name': {
                  'atomic_failures': ['test4', 'test1', 'test2']
              }
          }
      })
  @mock.patch.object(TestAnalysisAPI, 'SaveFailures')
  @mock.patch.object(TestAnalysisAPI, 'UpdateFailuresWithFirstFailureInfo')
  @mock.patch.object(ChromeOSProjectAPI, 'GetTestFailures', return_value={})
  def testAnalyzeTestFailureAllFoundGroups(self, mock_failures,
                                           mock_first_failure, *_):
    build = Build()
    test_failures = []
    self.assertFalse(
        test_analysis.AnalyzeTestFailure(self.context, build, test_failures))
    mock_failures.assert_called_once_with(build, test_failures)
    mock_first_failure.assert_called_once_with(self.context, build, {})

  @mock.patch.object(TestAnalysisAPI, 'RerunBasedAnalysis')
  @mock.patch.object(TestAnalysisAPI, 'SaveFailureAnalysis')
  @mock.patch.object(TestAnalysisAPI, 'SaveFailures')
  @mock.patch.object(TestAnalysisAPI, 'UpdateFailuresWithFirstFailureInfo')
  @mock.patch.object(ChromeOSProjectAPI, 'GetTestFailures', return_value={})
  @mock.patch.object(TestAnalysisAPI,
                     'GetFirstFailuresInCurrentBuildWithoutGroup')
  @mock.patch.object(TestAnalysisAPI, 'GetFirstFailuresInCurrentBuild')
  def testAnalyzeTestFailure(self, mock_first_failure_in_build, mock_no_group,
                             *_):
    mock_first_failure_in_build.return_value = {
        'failures': {
            self.test_step_name: {
                'atomic_failures': ['test4', 'test1', 'test2']
            }
        }
    }
    mock_no_group.return_value = {
        'failures': {
            self.test_step_name: {
                'atomic_failures': ['test4', 'test1', 'test2']
            }
        }
    }
    self.assertTrue(test_analysis.AnalyzeTestFailure(self.context, Build(), []))

  @mock.patch.object(ChromeOSProjectAPI, 'GetTestFailures')
  def testProcessRerunBuildResult(self, mock_test_failures):
    build_id = 8000000000123
    build_number = 123
    builder = BuilderID(
        project='chromeos', bucket='postsubmit', builder='findit-variable')
    build = Build(
        id=build_id,
        builder=builder,
        number=build_number,
        status=common_pb2.FAILURE,
        tags=[{
            'key': 'analyzed_build_id',
            'value': str(self.analyzed_build_id)
        }])
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha_6543221'
    build.create_time.FromDatetime(datetime(2019, 4, 9))
    build.end_time.FromDatetime(datetime(2019, 4, 9, 0, 30))
    step1 = Step(name='s1', status=common_pb2.SUCCESS)
    step2 = Step(name=self.test_step_name, status=common_pb2.FAILURE)
    build.steps.extend([step1, step2])
    build.output.properties['test_failures'] = {
        'xx_test_failures': [{
            'failed_step': self.test_step_name,
            'test_spec': 'test_spec'
        },],
    }

    mock_test_failures.return_value = {
        self.test_step_name: {
            'failures': {},
            'first_failed_build': {
                'id': build_id,
                'number': build_number,
                'commit_id': 'git_sha_6543221'
            },
            'last_passed_build': None,
            'properties': {}
        },
    }

    TestRerunBuild.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket=build.builder.bucket,
        luci_builder=build.builder.builder,
        build_id=build_id,
        legacy_build_number=build_number,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        gitiles_id='git_sha_6543221',
        commit_position=6543221,
        status=build.status,
        create_time=build.create_time.ToDatetime(),
        parent_key=self.analysis.key).put()

    self.assertTrue(
        test_analysis._ProcessAndSaveRerunBuildResult(
            self.context, self.analyzed_build_id, build))
    rerun_build = TestRerunBuild.get_by_id(build_id, parent=self.analysis.key)
    self.assertItemsEqual({
        self.test_step_name: []
    }, rerun_build.GetFailuresInBuild())
    self.assertEqual(datetime(2019, 4, 9, 0, 30), rerun_build.end_time)

  def testProcessAndSaveRerunBuildResultAnalysisMissing(self):
    build_id = 8000000000123
    build_number = 123
    builder = BuilderID(
        project='chromeos', bucket='postsubmit', builder='findit-variable')
    build = Build(
        id=build_id,
        builder=builder,
        number=build_number,
        status=common_pb2.FAILURE,
        tags=[{
            'key': 'analyzed_build_id',
            'value': '87654321'
        }])
    self.assertFalse(
        test_analysis.OnTestRerunBuildCompletion(self.context, build))

  def testProcessRerunBuildResultNoAnalyzedBuildIdTag(self):
    build_id = 8000000000123
    build_number = 123
    builder = BuilderID(
        project='chromeos', bucket='postsubmit', builder='findit-variable')
    build = Build(
        id=build_id,
        builder=builder,
        number=build_number,
        status=common_pb2.FAILURE)
    self.assertFalse(
        test_analysis.OnTestRerunBuildCompletion(self.context, build))

  def testProcessRerunBuildResultNoEntity(self):
    build_id = 8000000000123
    build_number = 123
    builder = BuilderID(
        project='chromeos', bucket='postsubmit', builder='findit-variable')
    build = Build(
        id=build_id,
        builder=builder,
        number=build_number,
        status=common_pb2.FAILURE,
        tags=[{
            'key': 'analyzed_build_id',
            'value': str(self.analyzed_build_id)
        }])
    self.assertFalse(
        test_analysis.OnTestRerunBuildCompletion(self.context, build))

  @mock.patch.object(TestAnalysisAPI, 'RerunBasedAnalysis')
  @mock.patch.object(ChromeOSProjectAPI, 'GetTestFailures')
  def testProcessRerunBuildResultBuildPassed(self, mock_test_failures,
                                             mock_analysis):
    build_id = 8000000000123
    build_number = 123
    builder = BuilderID(
        project='chromeos', bucket='postsubmit', builder='findit-variable')
    build = Build(
        id=build_id,
        builder=builder,
        number=build_number,
        status=common_pb2.SUCCESS,
        tags=[{
            'key': 'analyzed_build_id',
            'value': str(self.analyzed_build_id)
        }])
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha_6543221'
    build.create_time.FromDatetime(datetime(2019, 4, 9))
    step1 = Step(name='s1', status=common_pb2.SUCCESS)
    step2 = Step(name=self.test_step_name, status=common_pb2.SUCCESS)
    build.steps.extend([step1, step2])

    TestRerunBuild.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket=build.builder.bucket,
        luci_builder=build.builder.builder,
        build_id=build_id,
        legacy_build_number=build_number,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        gitiles_id='git_sha_6543221',
        commit_position=6543221,
        status=build.status,
        create_time=build.create_time.ToDatetime(),
        parent_key=self.analysis.key).put()

    self.assertTrue(
        test_analysis.OnTestRerunBuildCompletion(self.context, build))
    self.assertFalse(mock_test_failures.called)
    rerun_build = TestRerunBuild.get_by_id(build_id, parent=self.analysis.key)
    self.assertEqual({}, rerun_build.GetFailuresInBuild())

    self.assertTrue(mock_analysis.called)

  def testOnTestFailureAnalysisResultRequested(self):
    build_id = 800000000123
    request = findit_result.BuildFailureAnalysisRequest(
        build_id=build_id, failed_steps=[self.test_step_name])

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

    culprit_id = 'git_hash_65432'
    culprit_commit_position = 65432
    culprit = Culprit.Create(
        self.context.gitiles_host, self.context.gitiles_project,
        self.context.gitiles_ref, culprit_id, culprit_commit_position)
    culprit.put()

    test_failure = TestFailure.Create(build.key, self.test_step_name, 'test7')
    test_failure.culprit_commit_key = culprit.key
    test_failure.first_failed_build_id = build.build_id
    test_failure.failure_group_build_id = build.build_id
    test_failure.put()

    analysis = TestFailureAnalysis.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket='postsubmit',
        luci_builder='Linux Builder',
        build_id=build_id,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        last_passed_gitiles_id='last_passed_git_hash',
        last_passed_commit_position=65430,
        first_failed_gitiles_id='git_hash',
        first_failed_commit_position=65450,
        rerun_builder_id='chromeos/postsubmit/builder-bisect',
        test_failure_keys=[test_failure.key])
    analysis.status = analysis_status.COMPLETED
    analysis.Save()

    responses = test_analysis.OnTestFailureAnalysisResultRequested(
        request, build)

    self.assertEqual(1, len(responses))
    self.assertEqual(1, len(responses[0].culprits))
    self.assertEqual(culprit_id, responses[0].culprits[0].commit.id)
    self.assertTrue(responses[0].is_finished)
    self.assertEqual('test7', responses[0].test_name)

  def testOnTestFailureAnalysisResultRequestedAnalysisRunning(self):
    build_id = 800000000123
    request = findit_result.BuildFailureAnalysisRequest(
        build_id=build_id, failed_steps=[self.test_step_name])

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

    test_failure = TestFailure.Create(build.key, self.test_step_name, 'test8')
    test_failure.first_failed_build_id = build.build_id
    test_failure.failure_group_build_id = build.build_id
    test_failure.put()

    analysis = TestFailureAnalysis.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket='postsubmit',
        luci_builder='Linux Builder',
        build_id=build_id,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        last_passed_gitiles_id='last_passed_git_hash',
        last_passed_commit_position=65430,
        first_failed_gitiles_id='git_hash',
        first_failed_commit_position=65450,
        rerun_builder_id='chromeos/postsubmit/builder-bisect',
        test_failure_keys=[])
    analysis.status = analysis_status.RUNNING
    analysis.Save()

    responses = test_analysis.OnTestFailureAnalysisResultRequested(
        request, build)

    self.assertEqual(1, len(responses))
    self.assertEqual(0, len(responses[0].culprits))
    self.assertFalse(responses[0].is_finished)
    self.assertTrue(responses[0].is_supported)

  def testOnTestFailureAnalysisResultRequestedGetCulpritFromMergedFailure(self):
    build_id = 800000000123
    request = findit_result.BuildFailureAnalysisRequest(
        build_id=build_id, failed_steps=[self.test_step_name])

    culprit_id = 'git_hash_65432'
    culprit_commit_position = 65432
    culprit = Culprit.Create(
        self.context.gitiles_host, self.context.gitiles_project,
        self.context.gitiles_ref, culprit_id, culprit_commit_position)
    culprit.put()

    merge_failure = TestFailure.Create(
        ndb.Key(LuciFailedBuild, build_id), self.test_step_name, 'test7')
    merge_failure.culprit_commit_key = culprit.key
    merge_failure.first_failed_build_id = build_id
    merge_failure.failure_group_build_id = build_id
    merge_failure.put()

    analysis = TestFailureAnalysis.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket='postsubmit',
        luci_builder='Linux Builder',
        build_id=build_id,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        last_passed_gitiles_id='last_passed_git_hash',
        last_passed_commit_position=65430,
        first_failed_gitiles_id='git_hash',
        first_failed_commit_position=65450,
        rerun_builder_id='chromeos/postsubmit/builder-bisect',
        test_failure_keys=[merge_failure.key])
    analysis.status = analysis_status.COMPLETED
    analysis.Save()

    build = LuciFailedBuild.Create(
        luci_project='chromium',
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=800000000124,
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

    test_failure = TestFailure.Create(
        ndb.Key(LuciFailedBuild, 800000000124), self.test_step_name, 'test7')
    test_failure.merged_failure_key = merge_failure.key
    test_failure.first_failed_build_id = build.build_id
    test_failure.failure_group_build_id = build.build_id
    test_failure.put()

    responses = test_analysis.OnTestFailureAnalysisResultRequested(
        request, build)

    self.assertEqual(1, len(responses))
    self.assertEqual(1, len(responses[0].culprits))
    self.assertEqual(culprit_id, responses[0].culprits[0].commit.id)
    self.assertTrue(responses[0].is_finished)
    self.assertEqual('test7', responses[0].test_name)
