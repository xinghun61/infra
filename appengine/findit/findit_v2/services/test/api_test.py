# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from buildbucket_proto.build_pb2 import Build
from google.protobuf.field_mask_pb2 import FieldMask

from common.constants import DEFAULT_SERVICE_ACCOUNT
from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.model.messages import findit_result
from findit_v2.services import api
from findit_v2.services.analysis.compile_failure import compile_analysis
from findit_v2.services.context import Context
from findit_v2.services.failure_type import StepTypeEnum
from waterfall.test.wf_testcase import WaterfallTestCase

_MOCKED_LUCI_PROJECTS = {
    'project': {
        'ci': {
            'supported_builders': ['builder'],
            'rerun_builders': ['r_builder'],
            'supported_builder_pattern': r'.*-supported',
            'rerun_builder_pattern': r'.*-rerun',
        },
    }
}

_MOCKED_GERRIT_PROJECTS = {
    'project': {
        'name': 'project/name',
        'gitiles-host': 'gitiles.host.com',
    }
}


class APITest(WaterfallTestCase):

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  def testNoSupportedProject(self, *_):
    self.assertFalse(
        api.OnBuildCompletion('unsupported-project', 'ci', 'builder', 123,
                              'FAILURE'))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  def testNoSupportedBuilder(self, *_):
    self.assertFalse(
        api.OnBuildCompletion('project', 'ci', 'unsupported-builder', 123,
                              'FAILURE'))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  def testSkipNotFailedBuild(self, *_):
    self.assertFalse(
        api.OnBuildCompletion('project', 'ci', 'builder', 123, 'SUCCESS'))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('common.waterfall.buildbucket_client.GetV2Build')
  def testSkipFailedBuildNotMatchingGitilesProject(self, mocked_GetV2Build, *_):
    build = Build()
    build.input.gitiles_commit.host = 'wrong.host.com'
    build.input.gitiles_commit.project = 'wrong/project'
    mocked_GetV2Build.return_value = build
    self.assertFalse(
        api.OnBuildCompletion('project', 'ci', 'builder', 123, 'FAILURE'))
    mocked_GetV2Build.assert_called_once_with(
        123, fields=FieldMask(paths=['*']))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('common.waterfall.buildbucket_client.GetV2Build')
  @mock.patch('findit_v2.services.detection.api.OnBuildFailure')
  def testValidFailedBuild(self, mocked_OnBuildFailure, mocked_GetV2Build, *_):
    build = Build()
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'
    mocked_GetV2Build.return_value = build
    self.assertTrue(
        api.OnBuildCompletion('project', 'ci', 'builder', 123, 'FAILURE'))
    mocked_GetV2Build.assert_called_once_with(
        123, fields=FieldMask(paths=['*']))
    mocked_OnBuildFailure.assert_called_once_with(
        Context(
            luci_project_name='project',
            gitiles_host='gitiles.host.com',
            gitiles_project='project/name',
            gitiles_ref='ref/heads/master',
            gitiles_id='git_sha'), build)

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('common.waterfall.buildbucket_client.GetV2Build')
  @mock.patch('findit_v2.services.detection.api.OnRerunBuildCompletion')
  def testOnRerunBuildCompletion(self, mocked_OnRerunBuildCompletion,
                                 mocked_GetV2Build, *_):
    build = Build()
    build.created_by = 'user:{}'.format(DEFAULT_SERVICE_ACCOUNT)
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'
    mocked_GetV2Build.return_value = build
    self.assertTrue(
        api.OnBuildCompletion('project', 'ci', 'r_builder', 123, 'SUCCESS'))
    mocked_GetV2Build.assert_called_once_with(
        123, fields=FieldMask(paths=['*']))
    mocked_OnRerunBuildCompletion.assert_called_once_with(
        Context(
            luci_project_name='project',
            gitiles_host='gitiles.host.com',
            gitiles_project='project/name',
            gitiles_ref='ref/heads/master',
            gitiles_id='git_sha'), build)

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('common.waterfall.buildbucket_client.GetV2Build')
  def testOnRerunBuildCompletionNotTriggeredByFindit(self, mocked_GetV2Build,
                                                     *_):
    build = Build()
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'
    mocked_GetV2Build.return_value = build
    self.assertFalse(
        api.OnBuildCompletion('project', 'ci', 'builder-rerun', 123, 'SUCCESS'))
    mocked_GetV2Build.assert_called_once_with(
        123, fields=FieldMask(paths=['*']))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('common.waterfall.buildbucket_client.GetV2Build')
  @mock.patch('findit_v2.services.detection.api.OnRerunBuildCompletion')
  def testOnRerunBuildCompletionInvalidCommit(
      self, mocked_OnRerunBuildCompletion, mocked_GetV2Build, *_):
    build = Build()
    build.input.gitiles_commit.host = 'invalid.gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'
    mocked_GetV2Build.return_value = build
    self.assertFalse(
        api.OnBuildCompletion('project', 'ci', 'r_builder', 123, 'SUCCESS'))
    mocked_GetV2Build.assert_called_once_with(
        123, fields=FieldMask(paths=['*']))
    self.assertFalse(mocked_OnRerunBuildCompletion.called)

  @mock.patch(
      'common.waterfall.buildbucket_client.GetV2Build', return_value=None)
  def testGetBuildAndContextForAnalysisNoBuild(self, _):
    self.assertEqual((None, None),
                     api.GetBuildAndContextForAnalysis('chromium', 123))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('common.waterfall.buildbucket_client.GetV2Build')
  @mock.patch('findit_v2.services.detection.api.OnBuildFailure')
  def testValidFailedBuildWithBuilderMatchPattern(self, mocked_OnBuildFailure,
                                                  mocked_GetV2Build, *_):
    build = Build()
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'
    mocked_GetV2Build.return_value = build
    self.assertTrue(
        api.OnBuildCompletion('project', 'ci', 'builder-supported', 123,
                              'FAILURE'))
    mocked_GetV2Build.assert_called_once_with(
        123, fields=FieldMask(paths=['*']))
    mocked_OnBuildFailure.assert_called_once_with(
        Context(
            luci_project_name='project',
            gitiles_host='gitiles.host.com',
            gitiles_project='project/name',
            gitiles_ref='ref/heads/master',
            gitiles_id='git_sha'), build)

  @mock.patch.object(compile_analysis,
                     'OnCompileFailureAnalysisResultRequested')
  def testOnBuildFailureAnalysisResultRequestedNoBuildInDataStore(
      self, mock_compile_analysis):
    request = findit_result.BuildFailureAnalysisRequest(
        build_id=8000456, failed_steps=['compile'])
    self.assertEqual([], api.OnBuildFailureAnalysisResultRequested(request))
    self.assertFalse(mock_compile_analysis.called)

  @mock.patch.object(compile_analysis,
                     'OnCompileFailureAnalysisResultRequested')
  def testOnBuildFailureAnalysisResultRequestedNotSupport(
      self, mock_compile_analysis):
    build_id = 80004567
    build = LuciFailedBuild.Create(
        luci_project='chromium',
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=80004567,
        legacy_build_number=4567,
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

    request = findit_result.BuildFailureAnalysisRequest(
        build_id=build_id, failed_steps=['browser_tests'])
    self.assertEqual([], api.OnBuildFailureAnalysisResultRequested(request))
    self.assertFalse(mock_compile_analysis.called)

  @mock.patch.object(
      compile_analysis,
      'OnCompileFailureAnalysisResultRequested',
      return_value=['responses'])
  def testOnBuildFailureAnalysisResultRequested(self, mock_compile_analysis):
    luci_project = 'chromium'
    luci_bucket = 'ci'
    luci_builder = 'Linux Builder'
    build_number = 4567
    build = LuciFailedBuild.Create(
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        build_id=80004567,
        legacy_build_number=build_number,
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

    request = findit_result.BuildFailureAnalysisRequest(
        build_id=80004567, failed_steps=['compile'])
    self.assertEqual(['responses'],
                     api.OnBuildFailureAnalysisResultRequested(request))
    mock_compile_analysis.assert_called_once_with(request, build)
