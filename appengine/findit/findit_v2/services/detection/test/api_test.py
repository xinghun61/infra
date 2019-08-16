# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build

from findit_v2.services import constants
from findit_v2.services.analysis.compile_failure import compile_analysis
from findit_v2.services.analysis.test_failure import test_analysis
from findit_v2.services.context import Context
from findit_v2.services.detection import api
from findit_v2.services.failure_type import StepTypeEnum
from findit_v2.services.project_api import ProjectAPI


class DummyProjectAPI(ProjectAPI):  # pragma: no cover.

  def ClassifyStepType(self, _build, step):
    if step.name == 'compile':
      return StepTypeEnum.COMPILE
    if step.name == 'test':
      return StepTypeEnum.TEST
    return StepTypeEnum.INFRA

  def GetCompileFailures(self, *_):
    pass

  def GetRerunBuilderId(self, _):
    pass

  def GetTestFailures(self, *_):
    pass

  def GetCompileRerunBuildInputProperties(self, _):
    pass

  def GetTestRerunBuildInputProperties(self, _):
    pass


class APITest(unittest.TestCase):

  def setUp(self):
    super(APITest, self).setUp()
    self.context = Context(
        luci_project_name='project',
        gitiles_host='gitiles.host.com',
        gitiles_project='project/name',
        gitiles_ref='ref/heads/master',
        gitiles_id='git_sha')

  @mock.patch(
      'findit_v2.services.projects.GetProjectAPI',
      return_value=DummyProjectAPI())
  def testNoValidFailure(self, *_):
    build = Build()
    step = build.steps.add()
    step.name = 'compile'
    step.status = common_pb2.INFRA_FAILURE
    self.assertFalse(api.OnBuildFailure(self.context, build))

  @mock.patch(
      'findit_v2.services.projects.GetProjectAPI',
      return_value=DummyProjectAPI())
  @mock.patch.object(test_analysis, 'AnalyzeTestFailure')
  def testTestFailure(self, mock_analyzer, _):
    build = Build()
    step = build.steps.add()
    step.name = 'test'
    step.status = common_pb2.FAILURE
    self.assertTrue(api.OnBuildFailure(self.context, build))
    mock_analyzer.assert_called_once_with(
      self.context, build, [step])

  @mock.patch(
      'findit_v2.services.projects.GetProjectAPI',
      return_value=DummyProjectAPI())
  @mock.patch.object(compile_analysis, 'AnalyzeCompileFailure')
  def testCompileFailure(self, mock_analyzer, _):
    build = Build()
    step = build.steps.add()
    step.name = 'compile'
    step.status = common_pb2.FAILURE
    self.assertTrue(api.OnBuildFailure(self.context, build))
    mock_analyzer.assert_called_once_with(
        self.context, build, [step])

  @mock.patch.object(
      compile_analysis, 'OnCompileRerunBuildCompletion', return_value=True)
  def testOnRerunBuildCompletion(self, mock_build_result):
    build = Build(
        id=800000500,
        tags=[{
            'key': constants.RERUN_BUILD_PURPOSE_TAG_KEY,
            'value': constants.COMPILE_RERUN_BUILD_PURPOSE
        }, {
            'key': 'analyzed_build_id',
            'value': '800000000'
        }])
    self.assertTrue(api.OnRerunBuildCompletion(self.context, build))
    mock_build_result.assert_called_once_with(self.context, build)

  @mock.patch.object(
      test_analysis, 'OnTestRerunBuildCompletion', return_value=True)
  def testOnRerunBuildCompletionForTestFailure(self, mock_build_result):
    build = Build(
        id=800000500,
        tags=[{
            'key': constants.RERUN_BUILD_PURPOSE_TAG_KEY,
            'value': constants.TEST_RERUN_BUILD_PURPOSE
        }, {
            'key': 'analyzed_build_id',
            'value': '800000000'
        }])
    self.assertTrue(api.OnRerunBuildCompletion(self.context, build))
    mock_build_result.assert_called_once_with(self.context, build)

  def testOnRerunBuildCompletionNoPurpose(self):
    build = Build(id=800000501)
    self.assertFalse(api.OnRerunBuildCompletion(self.context, build))

  def testOnRerunBuildCompletionUnsupportedPurpose(self):
    build = Build(
        id=800000502,
        tags=[{
            'key': constants.RERUN_BUILD_PURPOSE_TAG_KEY,
            'value': 'some purpose'
        }, {
            'key': 'analyzed_build_id',
            'value': '800000000'
        }])
    self.assertFalse(api.OnRerunBuildCompletion(self.context, build))
