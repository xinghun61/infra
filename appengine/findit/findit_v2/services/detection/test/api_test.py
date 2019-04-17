# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build

from findit_v2.services.context import Context
from findit_v2.services.detection import api
from findit_v2.services.failure_type import StepTypeEnum
from findit_v2.services.project_api import ProjectAPI


class DummyProjectAPI(ProjectAPI):

  def ClassifyStepType(self, step):
    if step.name == 'compile':
      return StepTypeEnum.COMPILE
    return StepTypeEnum.INFRA

  def GetCompileFailures(self, *_):
    pass


_MOCKED_GERRIT_PROJECTS = {'project': {'project-api': DummyProjectAPI(),}}


class APITest(unittest.TestCase):

  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('findit_v2.services.analysis.compile_failure.compile_api.'
              'AnalyzeCompileFailure')
  def testNoValidFailure(self, mocked_AnalyzeCompileFailure, *_):
    build = Build()
    step = build.steps.add()
    step.name = 'compile'
    step.status = common_pb2.INFRA_FAILURE
    context = Context(
        luci_project_name='project',
        gitiles_host='gitiles.host.com',
        gitiles_project='project/name',
        gitiles_ref='ref/heads/master',
        gitiles_id='git_sha')
    self.assertFalse(api.OnBuildFailure(context, build))
    self.assertFalse(mocked_AnalyzeCompileFailure.called)

  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('findit_v2.services.analysis.compile_failure.compile_api.'
              'AnalyzeCompileFailure')
  def testTestFailure(self, mocked_AnalyzeCompileFailure, *_):
    build = Build()
    step = build.steps.add()
    step.name = 'test'
    step.status = common_pb2.FAILURE
    context = Context(
        luci_project_name='project',
        gitiles_host='gitiles.host.com',
        gitiles_project='project/name',
        gitiles_ref='ref/heads/master',
        gitiles_id='git_sha')
    self.assertFalse(api.OnBuildFailure(context, build))
    self.assertFalse(mocked_AnalyzeCompileFailure.called)

  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('findit_v2.services.analysis.compile_failure.compile_api.'
              'AnalyzeCompileFailure')
  def testCompileFailure(self, mocked_AnalyzeCompileFailure, *_):
    build = Build()
    step = build.steps.add()
    step.name = 'compile'
    step.status = common_pb2.FAILURE
    context = Context(
        luci_project_name='project',
        gitiles_host='gitiles.host.com',
        gitiles_project='project/name',
        gitiles_ref='ref/heads/master',
        gitiles_id='git_sha')
    self.assertTrue(api.OnBuildFailure(context, build))
    self.assertTrue(mocked_AnalyzeCompileFailure.called)
