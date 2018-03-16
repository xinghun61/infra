# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common import monitoring
from dto.int_range import IntRange
from dto.step_metadata import StepMetadata
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import pipeline
from libs import analysis_status
from libs import time_util
from libs.structured_object import StructuredObject
from pipelines.delay_pipeline import DelayPipeline
from pipelines.flake_failure.create_bug_for_flake_pipeline import (
    CreateBugForFlakePipeline)
from pipelines.flake_failure.create_bug_for_flake_pipeline import (
    CreateBugForFlakePipelineInputObject)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRateInput)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRatePipeline)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForCommitPositionParameters)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForCommitPositionPipeline)
from pipelines.flake_failure.next_commit_position_pipeline import (
    NextCommitPositionInput)
from pipelines.flake_failure.next_commit_position_pipeline import (
    NextCommitPositionOutput)
from pipelines.flake_failure.next_commit_position_pipeline import (
    NextCommitPositionPipeline)
from pipelines.flake_failure.notify_culprit_pipeline import NotifyCulpritInput
from pipelines.flake_failure.notify_culprit_pipeline import (
    NotifyCulpritPipeline)
from pipelines.flake_failure.update_monorail_bug_pipeline import (
    UpdateMonorailBugInput)
from pipelines.flake_failure.update_monorail_bug_pipeline import (
    UpdateMonorailBugPipeline)
from services import swarmed_test_util
from services.flake_failure import commit_position_util
from services.flake_failure import confidence_score_util
from services.flake_failure import flake_analysis_util


class AnalyzeFlakeInput(StructuredObject):
  # The urlsafe key to the MasterFlakeAnalysis in progress.
  analysis_urlsafe_key = basestring

  # The lower/upper bound commit positions not to exceed.
  commit_position_range = IntRange

  # Information on the exact commit position to analyze.
  analyze_commit_position_parameters = NextCommitPositionOutput

  # A flag indicating this pipeline was triggered by a human request.
  manually_triggered = bool

  # The number of times bots have been checked for availability.
  retries = int

  # Information about the test used to find bots that will run swarming tasks.
  step_metadata = StepMetadata


class AnalyzeFlakePipeline(GeneratorPipeline):
  """The main driving pipeline for flake analysis."""

  input_type = AnalyzeFlakeInput

  def OnAbort(self, parameters):
    analysis_urlsafe_key = parameters.analysis_urlsafe_key
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    flake_analysis_util.ReportError(analysis_urlsafe_key)
    analysis.Update(end_time=time_util.GetUTCNow())
    monitoring.aborted_pipelines.increment({'type': 'flake'})

  def RunImpl(self, parameters):
    analysis_urlsafe_key = parameters.analysis_urlsafe_key
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    commit_position_parameters = parameters.analyze_commit_position_parameters
    commit_position_to_analyze = commit_position_parameters.next_commit_position
    culprit_commit_position = (
        commit_position_parameters.culprit_commit_position)

    if commit_position_to_analyze is None:
      # No commit position to analyze. The analysis is finished.

      if culprit_commit_position is None:
        # No culprit was identified. No further action.
        analysis.LogInfo('Analysis completed with no findings')
        analysis.Update(
            end_time=time_util.GetUTCNow(), status=analysis_status.COMPLETED)
        return

      # Create a FlakeCulprit.
      culprit_revision = commit_position_util.GetRevisionFromCommitPosition(
          analysis.master_name, analysis.builder_name, analysis.step_name,
          culprit_commit_position)
      culprit = flake_analysis_util.UpdateCulprit(
          analysis_urlsafe_key, culprit_revision, culprit_commit_position)
      confidence_score = confidence_score_util.CalculateCulpritConfidenceScore(
          analysis, culprit_commit_position)

      # Update the analysis' fields to signfy completion.
      analysis.Update(
          confidence_in_culprit=confidence_score,
          culprit_urlsafe_key=culprit.key.urlsafe(),
          end_time=time_util.GetUTCNow(),
          status=analysis_status.COMPLETED)

      # Determine the test's location for filing bugs.
      culprit_data_point = analysis.FindMatchingDataPointWithCommitPosition(
          culprit_commit_position)
      assert culprit_data_point
      test_location = swarmed_test_util.GetTestLocation(
          culprit_data_point.GetSwarmingTaskId(), analysis.test_name)

      # Log a Monorail bug and notify the culprit review about findings.
      with pipeline.InOrder():
        create_bug_input = self.CreateInputObjectInstance(
            CreateBugForFlakePipelineInputObject,
            analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
            test_location=test_location)
        monorail_bug_input = self.CreateInputObjectInstance(
            UpdateMonorailBugInput, analysis_urlsafe_key=analysis_urlsafe_key)
        notify_culprit_input = self.CreateInputObjectInstance(
            NotifyCulpritInput, analysis_urlsafe_key=analysis_urlsafe_key)

        yield CreateBugForFlakePipeline(create_bug_input)
        yield UpdateMonorailBugPipeline(monorail_bug_input)
        yield NotifyCulpritPipeline(notify_culprit_input)
        return

    revision_to_analyze = commit_position_util.GetRevisionFromCommitPosition(
        analysis.master_name, analysis.builder_name, analysis.step_name,
        commit_position_to_analyze)

    # Check for bot availability. If this is a user rerun or the maximum retries
    # have been reached, continue regardless of bot availability.
    if flake_analysis_util.CanStartAnalysisImmediately(
        parameters.step_metadata, parameters.retries,
        parameters.manually_triggered):

      # Set analysis status to RUNNING if not already.
      analysis.InitializeRunning()

      analysis.LogInfo(
          'Analyzing commit position {}'.format(commit_position_to_analyze))

      with pipeline.InOrder():
        # Determine isolate sha to run swarming tasks on.
        get_isolate_sha_input = self.CreateInputObjectInstance(
            GetIsolateShaForCommitPositionParameters,
            analysis_urlsafe_key=analysis_urlsafe_key,
            commit_position=commit_position_to_analyze,
            revision=revision_to_analyze)
        isolate_sha = yield GetIsolateShaForCommitPositionPipeline(
            get_isolate_sha_input)

        # Determine approximate pass rate at the commit position/isolate sha.
        determine_approximate_pass_rate_input = self.CreateInputObjectInstance(
            DetermineApproximatePassRateInput,
            analysis_urlsafe_key=analysis_urlsafe_key,
            commit_position=commit_position_to_analyze,
            isolate_sha=isolate_sha,
            previous_swarming_task_output=None,
            revision=revision_to_analyze)
        yield DetermineApproximatePassRatePipeline(
            determine_approximate_pass_rate_input)

        # Determine the next commit position to analyze.
        next_commit_position_input = self.CreateInputObjectInstance(
            NextCommitPositionInput,
            analysis_urlsafe_key=analysis_urlsafe_key,
            commit_position_range=parameters.commit_position_range)
        next_commit_position_output = yield NextCommitPositionPipeline(
            next_commit_position_input)

        # Recurse on the new commit position.
        analyze_next_commit_position_input = self.CreateInputObjectInstance(
            AnalyzeFlakeInput,
            analysis_urlsafe_key=analysis_urlsafe_key,
            analyze_commit_position_parameters=next_commit_position_output,
            commit_position_range=parameters.commit_position_range,
            manually_triggered=parameters.manually_triggered,
            retries=0,
            step_metadata=parameters.step_metadata)

        yield RecursiveAnalyzeFlakePipeline(analyze_next_commit_position_input)
    else:
      # Can't start the analysis just yet, reschedule.
      parameters.retries += 1
      delay_seconds = flake_analysis_util.CalculateDelaySecondsBetweenRetries(
          analysis, parameters.retries, parameters.manually_triggered)
      delay = yield DelayPipeline(delay_seconds)

      with pipeline.After(delay):
        yield RecursiveAnalyzeFlakePipeline(parameters)


class RecursiveAnalyzeFlakePipeline(GeneratorPipeline):
  """A wrapper for AnalyzeFlakePipeline for testability only.

    Because AnalyzeFlakePipeline is recursive, in unit tests it is not possible
    to mock only the recursive call to validate its input independently of the
    original call.
  """
  input_type = AnalyzeFlakeInput

  def RunImpl(self, parameters):
    yield AnalyzeFlakePipeline(parameters)
