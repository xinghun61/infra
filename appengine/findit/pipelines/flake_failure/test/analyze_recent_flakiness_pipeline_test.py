# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.flakiness import Flakiness
from dto.step_metadata import StepMetadata
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.analyze_recent_flakiness_pipeline import (
    AnalyzeRecentFlakinessInput)
from pipelines.flake_failure.analyze_recent_flakiness_pipeline import (
    AnalyzeRecentFlakinessPipeline)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRateInput)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRatePipeline)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForCommitPositionParameters)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForCommitPositionPipeline)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaOutput)
from pipelines.flake_failure.save_flakiness_verification_pipeline import (
    SaveFlakinessVerificationInput)
from pipelines.flake_failure.save_flakiness_verification_pipeline import (
    SaveFlakinessVerificationPipeline)
from services import step_util
from waterfall import build_util
from waterfall.test.wf_testcase import WaterfallTestCase


class AnalyzeRecentFlakinessPipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(step_util, 'LegacyGetStepMetadata')
  @mock.patch.object(build_util, 'GetLatestCommitPositionAndRevision')
  def testAnalyzeRecentFlakinessPipeline(self, mocked_commit_position,
                                         mocked_step_metadata):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [DataPoint.Create(commit_position=999)]
    analysis.Save()
    isolate_sha = 'sha'
    latest_revision = 'r'
    latest_commit_position = 1000
    mocked_commit_position.return_value = (latest_commit_position,
                                           latest_revision)
    pass_rate = 0.5

    get_sha_output = GetIsolateShaOutput(
        isolate_sha=isolate_sha, build_url='url', try_job_url=None)

    step_metadata = StepMetadata(
        canonical_step_name=step_name,
        dimensions=None,
        full_step_name='s',
        patched=False,
        swarm_task_ids=None,
        waterfall_buildername=builder_name,
        waterfall_mastername=master_name,
        isolate_target_name=step_name)

    mocked_step_metadata.return_value = step_metadata.ToSerializable()

    expected_flakiness = Flakiness(
        build_url='url',
        commit_position=latest_commit_position,
        revision=latest_revision,
        pass_rate=pass_rate)

    analyze_recent_flakiness_input = AnalyzeRecentFlakinessInput(
        analysis_urlsafe_key=analysis.key.urlsafe())

    expected_isolate_sha_input = GetIsolateShaForCommitPositionParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=latest_commit_position,
        dimensions=None,
        revision=latest_revision,
        step_metadata=step_metadata,
        upper_bound_build_number=analysis.build_number)

    expected_pass_rate_input = DetermineApproximatePassRateInput(
        builder_name=analysis.builder_name,
        commit_position=latest_commit_position,
        flakiness_thus_far=None,
        get_isolate_sha_output=get_sha_output,
        master_name=analysis.master_name,
        previous_swarming_task_output=None,
        reference_build_number=analysis.build_number,
        revision=latest_revision,
        step_name=analysis.step_name,
        test_name=analysis.test_name)

    expected_save_flakiness_verification_input = SaveFlakinessVerificationInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        flakiness=expected_flakiness)

    self.MockGeneratorPipeline(GetIsolateShaForCommitPositionPipeline,
                               expected_isolate_sha_input, get_sha_output)

    self.MockGeneratorPipeline(DetermineApproximatePassRatePipeline,
                               expected_pass_rate_input, expected_flakiness)

    self.MockGeneratorPipeline(SaveFlakinessVerificationPipeline,
                               expected_save_flakiness_verification_input, None)

    pipeline_job = AnalyzeRecentFlakinessPipeline(
        analyze_recent_flakiness_input)
    pipeline_job.start()
    self.execute_queued_tasks()
    mocked_step_metadata.assert_called_with(master_name, builder_name,
                                            build_number, step_name)
    mocked_commit_position.assert_called_with(master_name, builder_name,
                                              step_name)

  @mock.patch.object(step_util, 'LegacyGetStepMetadata')
  @mock.patch.object(build_util, 'GetLatestCommitPositionAndRevision')
  def testAnalyzeRecentFlakinessPipelineAlreadyUpToDate(
      self, mocked_commit_position, mocked_step_metadata):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [DataPoint.Create(commit_position=1001)]
    analysis.Save()
    latest_revision = 'r'
    latest_commit_position = 1000
    mocked_commit_position.return_value = (latest_commit_position,
                                           latest_revision)

    step_metadata = StepMetadata(
        canonical_step_name=step_name,
        dimensions=None,
        full_step_name='s',
        patched=False,
        swarm_task_ids=None,
        waterfall_buildername=builder_name,
        waterfall_mastername=master_name,
        isolate_target_name=step_name)

    mocked_step_metadata.return_value = step_metadata.ToSerializable()

    analyze_recent_flakiness_input = AnalyzeRecentFlakinessInput(
        analysis_urlsafe_key=analysis.key.urlsafe())

    pipeline_job = AnalyzeRecentFlakinessPipeline(
        analyze_recent_flakiness_input)
    pipeline_job.start()
    self.execute_queued_tasks()
    self.assertEqual(analysis_status.COMPLETED,
                     analysis.analyze_recent_flakiness_status)
