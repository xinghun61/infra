# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.list_of_basestring import ListOfBasestring
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.flake.flake_try_job import FlakeTryJob
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForBuildParameters)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForBuildPipeline)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForCommitPositionParameters)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForCommitPositionPipeline)
from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobParameters)
from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobPipeline)
from services import swarmbot_util
from waterfall import build_util
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.build_info import BuildInfo
from waterfall.test.wf_testcase import WaterfallTestCase


class GetIsolateShaPipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(swarming_util, 'GetIsolatedShaForStep')
  def testGetIsolateShaForBuildPipeline(self, mocked_get_isolate_sha):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'

    get_build_sha_parameters = GetIsolateShaForBuildParameters(
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        step_name=step_name)

    pipeline_job = GetIsolateShaForBuildPipeline(get_build_sha_parameters)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(mocked_get_isolate_sha.called)

  @mock.patch.object(build_util, 'GetBoundingBuilds')
  def testGetIsolateShaForCommitPositionPipelineBuildLevel(
      self, mocked_build_info):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    requested_commit_position = 1000
    requested_revision = 'r1000'
    expected_sha = 'sha1'

    build = BuildInfo(master_name, builder_name, build_number)
    build.commit_position = requested_commit_position
    mocked_build_info.return_value = (None, build)

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    get_build_sha_parameters = GetIsolateShaForBuildParameters(
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        step_name=step_name)

    get_sha_input = GetIsolateShaForCommitPositionParameters(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        commit_position=requested_commit_position,
        revision=requested_revision)

    self.MockSynchronousPipeline(GetIsolateShaForBuildPipeline,
                                 get_build_sha_parameters, expected_sha)

    pipeline_job = GetIsolateShaForCommitPositionPipeline(get_sha_input)
    pipeline_job.start()
    self.execute_queued_tasks()

  @mock.patch.object(waterfall_config, 'GetTrybotDimensions')
  @mock.patch.object(swarmbot_util, 'GetCacheName')
  @mock.patch.object(build_util, 'GetBoundingBuilds')
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testGetIsolateShaForCommitPositionPipelineCommitLevel(
      self, mocked_reference_build, mocked_bounding_builds, mocked_cache,
      mocked_dimensions):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    dimensions = ['dimensions']
    requested_commit_position = 1000
    containing_build_commit_position = 1001
    requested_revision = 'r1000'
    expected_sha = 'sha1'
    cache_name = 'cache'
    mocked_cache.return_value = cache_name
    mocked_dimensions.return_value = dimensions

    build = BuildInfo(master_name, builder_name, build_number)
    build.commit_position = containing_build_commit_position
    mocked_reference_build.return_value = (None, build)
    mocked_bounding_builds.return_value = (None, build)

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, requested_revision)
    try_job.put()

    run_flake_try_job_parameters = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        revision=requested_revision,
        flake_cache_name=cache_name,
        dimensions=ListOfBasestring.FromSerializable(dimensions),
        urlsafe_try_job_key=try_job.key.urlsafe())

    get_sha_input = GetIsolateShaForCommitPositionParameters(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        commit_position=requested_commit_position,
        revision=requested_revision)

    self.MockAsynchronousPipeline(RunFlakeTryJobPipeline,
                                  run_flake_try_job_parameters, expected_sha)

    pipeline_job = GetIsolateShaForCommitPositionPipeline(get_sha_input)
    pipeline_job.start()
    self.execute_queued_tasks()
