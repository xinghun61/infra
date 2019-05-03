# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from buildbucket_proto.step_pb2 import Step

from findit_v2.model.compile_failure import CompileFailureAnalysis
from findit_v2.model.compile_failure import CompileRerunBuild
from findit_v2.services.analysis.compile_failure import compile_api
from findit_v2.services.chromium_api import ChromiumProjectAPI
from findit_v2.services.context import Context
from waterfall.test import wf_testcase


class CompileApiTest(wf_testcase.TestCase):

  def setUp(self):
    super(CompileApiTest, self).setUp()
    self.analyzed_build_id = 8000000000000
    self.context = Context(
        luci_project_name='chromium',
        gitiles_host='gitiles.host.com',
        gitiles_project='project/name',
        gitiles_ref='ref/heads/master',
        gitiles_id='git_sha')

    self.analysis = CompileFailureAnalysis.Create(
        luci_project=self.context.luci_project_name,
        luci_bucket='ci',
        luci_builder='Linux Builder',
        build_id=self.analyzed_build_id,
        gitiles_host=self.context.gitiles_host,
        gitiles_project=self.context.gitiles_project,
        gitiles_ref=self.context.gitiles_ref,
        last_passed_gitiles_id='last_passed_git_hash',
        last_passed_cp=65432,
        first_failed_gitiles_id=self.context.gitiles_id,
        first_failed_cp=65450,
        rerun_builder_id='findit_variables',
        compile_failure_keys=[])
    self.analysis.Save()

  @mock.patch.object(ChromiumProjectAPI, 'GetCompileFailures')
  def testProcessRerunBuildResult(self, mock_compile_failures):
    build_id = 8000000000123
    build_number = 123
    builder = BuilderID(
        project='chromium', bucket='findit', builder='findit-variable')
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
    step1 = Step(name='s1', status=common_pb2.SUCCESS)
    step2 = Step(name='compile', status=common_pb2.FAILURE)
    build.steps.extend([step1, step2])

    mock_compile_failures.return_value = {
        'compile': {
            'failures': {
                'target1 target2': {
                    'output_targets': ['target1.o', 'target2.o'],
                    'rule': 'CXX',
                    'first_failed_build': {
                        'id': build_id,
                        'number': build_number,
                        'commit_id': 'git_sha_6543221'
                    },
                    'last_passed_build': None
                },
            },
            'first_failed_build': {
                'id': build_id,
                'number': build_number,
                'commit_id': 'git_sha_6543221'
            },
            'last_passed_build': None
        },
    }

    CompileRerunBuild.Create(
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
        compile_api._ProcessAndSaveRerunBuildResult(self.context, build))
    rerun_build = CompileRerunBuild.get_by_id(
        build_id, parent=self.analysis.key)
    self.assertItemsEqual(['target1.o', 'target2.o'],
                          rerun_build.GetFailedTargets()['compile'])

  def testProcessRerunBuildResultNoAnalyzedBuildIdTag(self):
    build_id = 8000000000123
    build_number = 123
    builder = BuilderID(
        project='chromium', bucket='findit', builder='findit-variable')
    build = Build(
        id=build_id,
        builder=builder,
        number=build_number,
        status=common_pb2.FAILURE)
    self.assertFalse(
        compile_api.OnCompileRerunBuildCompletion(self.context, build))

  def testProcessRerunBuildResultNoEntity(self):
    build_id = 8000000000123
    build_number = 123
    builder = BuilderID(
        project='chromium', bucket='findit', builder='findit-variable')
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
        compile_api.OnCompileRerunBuildCompletion(self.context, build))

  @mock.patch.object(ChromiumProjectAPI, 'GetCompileFailures')
  def testProcessRerunBuildResultBuildPassed(self, mock_compile_failures):
    build_id = 8000000000123
    build_number = 123
    builder = BuilderID(
        project='chromium', bucket='findit', builder='findit-variable')
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
    step2 = Step(name='compile', status=common_pb2.SUCCESS)
    build.steps.extend([step1, step2])

    CompileRerunBuild.Create(
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
        compile_api.OnCompileRerunBuildCompletion(self.context, build))
    self.assertFalse(mock_compile_failures.called)
    rerun_build = CompileRerunBuild.get_by_id(
        build_id, parent=self.analysis.key)
    self.assertEqual({}, rerun_build.GetFailedTargets())
