# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dto.step_metadata import StepMetadata
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import pipeline
from libs import analysis_status
from libs.structured_object import StructuredObject
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForCommitPositionParameters)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForCommitPositionPipeline)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRateInput)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRatePipeline)
from pipelines.flake_failure.save_flakiness_verification_pipeline import (
    SaveFlakinessVerificationInput)
from pipelines.flake_failure.save_flakiness_verification_pipeline import (
    SaveFlakinessVerificationPipeline)
from services import step_util
from waterfall import build_util


class AnalyzeRecentFlakinessInput(StructuredObject):
  # The url-safe key to the MasterFlakeAnalysis to analyze recent flakines.
  analysis_urlsafe_key = basestring


class AnalyzeRecentFlakinessPipeline(GeneratorPipeline):
  """Analyzes flakiness at a recent commit for a MasterFlakeAnalysis."""
  input_type = AnalyzeRecentFlakinessInput

  def OnFinalized(self, parameters):
    analysis_urlsafe_key = parameters.analysis_urlsafe_key
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis, 'Analysis missing unexpetedly!'
    error = None

    if self.was_aborted:  # pragma: no branch
      error = analysis.GetError()

    status = analysis_status.ERROR if error else analysis_status.COMPLETED
    analysis.Update(
        analyze_recent_flakiness_error=error,
        analyze_recent_flakiness_status=status)

  def RunImpl(self, parameters):
    analysis_urlsafe_key = parameters.analysis_urlsafe_key
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis, 'Analysis missing unexpectedly!'

    step_metadata = (
        step_util.LegacyGetStepMetadata(
            analysis.master_name, analysis.builder_name, analysis.build_number,
            analysis.step_name) or step_util.LegacyGetStepMetadata(
                analysis.original_master_name, analysis.original_builder_name,
                analysis.original_build_number, analysis.original_step_name))

    step_metadata = StepMetadata.FromSerializable(step_metadata)

    recent_commit_position, recent_revision = (
        build_util.GetLatestCommitPositionAndRevision(
            analysis.master_name, analysis.builder_name,
            step_metadata.isolate_target_name))

    if (not analysis.data_points or
        analysis.data_points[0].commit_position >= recent_commit_position or
        ((analysis.flakiness_verification_data_points and
          analysis.flakiness_verification_data_points[-1].commit_position >=
          recent_commit_position))):
      # The analysis already has the most up-to-date info on recent commits.
      return

    with pipeline.InOrder():
      get_sha_output = yield GetIsolateShaForCommitPositionPipeline(
          self.CreateInputObjectInstance(
              GetIsolateShaForCommitPositionParameters,
              analysis_urlsafe_key=analysis_urlsafe_key,
              commit_position=recent_commit_position,
              dimensions=None,  # Not used.
              revision=recent_revision,
              step_metadata=step_metadata,
              upper_bound_build_number=analysis.build_number))

      # Determine approximate pass rate at the commit position/isolate sha.
      recent_flakiness = yield DetermineApproximatePassRatePipeline(
          self.CreateInputObjectInstance(
              DetermineApproximatePassRateInput,
              builder_name=analysis.builder_name,
              commit_position=recent_commit_position,
              flakiness_thus_far=None,
              get_isolate_sha_output=get_sha_output,
              previous_swarming_task_output=None,
              master_name=analysis.master_name,
              reference_build_number=analysis.build_number,
              revision=recent_revision,
              step_name=analysis.step_name,
              test_name=analysis.test_name))

      yield SaveFlakinessVerificationPipeline(
          self.CreateInputObjectInstance(
              SaveFlakinessVerificationInput,
              analysis_urlsafe_key=analysis_urlsafe_key,
              flakiness=recent_flakiness))
