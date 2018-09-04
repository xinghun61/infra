# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(crbug.com/810912): Refactor into services.

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from dto.step_metadata import StepMetadata
from dto.test_location import TestLocation
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import pipeline
from libs.structured_object import StructuredObject
from model.flake.analysis import triggering_sources
from model.flake.analysis.flake_analysis_request import FlakeAnalysisRequest
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRateInput)
from pipelines.flake_failure.determine_approximate_pass_rate_pipeline import (
    DetermineApproximatePassRatePipeline)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForCommitPositionParameters)
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaForCommitPositionPipeline)
from pipelines.flake_failure.save_flakiness_verification_pipeline import (
    SaveFlakinessVerificationInput)
from pipelines.flake_failure.save_flakiness_verification_pipeline import (
    SaveFlakinessVerificationPipeline)
from services import issue_tracking_service
from services import swarmed_test_util
from services import monitoring
from services import swarming
from services.flake_failure import flake_report_util
from services.flake_failure import pass_rate_util
from waterfall import build_util

# TODO(crbug.com/850661): Merge CreateBugForFlakePipeline and
# UpdateMonorailBugPipeline into a single bug handling piepline.

# TODO(crbug.com/783335): Allow these values to be configurable.
_ITERATIONS_TO_CONFIRM_FLAKE = 30  # 30 iterations.
_ITERATIONS_TO_CONFIRM_FLAKE_TIMEOUT = 60 * 60  # One hour.


class CreateBugForFlakeInput(StructuredObject):
  """Input object for creating bugs for a flake analysis."""
  # The url-safe key to a MasterFlakeAnalysis.
  analysis_urlsafe_key = basestring

  # The location of the flaky test.
  test_location = TestLocation

  # Step metadata about the step containing the flaky test.
  step_metadata = StepMetadata


class CreateBugInput(StructuredObject):
  """Input object for creating bugs directly."""
  analysis_urlsafe_key = basestring


class CreateBugForFlakePipeline(GeneratorPipeline):
  input_type = CreateBugForFlakeInput

  def RunImpl(self, parameters):
    """Creates a bug for a flake analysis.

    Creates a bug if certain conditions are satisfied. These conditions are
    logically unordered, and the ordering you see in the pipeline is to
    favor local operations over network requests. This pipeline shouldn't
    be retried since it files a bug with monorail. Instead a bit is set
    in MasterFlakeAnalysis before a filing is attempted `has_attemped_filing`
    in the event in a retry this pipeline will be abandoned entirely.
    """
    analysis_urlsafe_key = parameters.analysis_urlsafe_key
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    if not flake_report_util.ShouldFileBugForAnalysis(analysis):
      if not analysis.bug_id:  # pragma: no branch
        bug_id = issue_tracking_service.SearchOpenIssueIdForFlakyTest(
            analysis.test_name)
        analysis.Update(bug_id=bug_id)
      return

    most_recent_build_number = build_util.GetLatestBuildNumber(
        analysis.master_name, analysis.builder_name)

    if not most_recent_build_number:
      analysis.LogInfo('Bug not failed because latest build number not found.')
      return

    tasks = swarming.ListSwarmingTasksDataByTags(
        FinditHttpClient(), analysis.master_name, analysis.builder_name,
        most_recent_build_number, analysis.step_name)
    if not tasks:
      analysis.LogInfo('Bug not filed because no recent runs found.')
      return

    if not swarmed_test_util.IsTestEnabled(analysis.test_name, tasks):
      analysis.LogInfo('Bug not filed because test was fixed or disabled.')
      return

    _, most_recent_build_info = build_util.GetBuildInfo(
        analysis.master_name, analysis.builder_name, most_recent_build_number)

    if (not most_recent_build_info or
        most_recent_build_info.commit_position is None):
      analysis.LogInfo(
          'Bug not filed because no recent build\'s commit position')
      return

    most_recent_commit_position = most_recent_build_info.commit_position

    if analysis.FindMatchingDataPointWithCommitPosition(
        most_recent_commit_position):
      # In some corner cases, an analysis is triggered immediately after a
      # culprit lands and completes quickly before a new build cycle becomes
      # available. The commit position of the most recent build would thus be
      # that of the very first data point, which has already been analyzed to
      # be flaky and nothing has landed since, so a bug can be created directly.
      yield CreateBugPipeline(
          self.CreateInputObjectInstance(
              CreateBugInput, analysis_urlsafe_key=analysis_urlsafe_key))
    else:
      with pipeline.InOrder():
        # Get the isolate sha of the recent build.
        get_sha_output = yield GetIsolateShaForCommitPositionPipeline(
            self.CreateInputObjectInstance(
                GetIsolateShaForCommitPositionParameters,
                analysis_urlsafe_key=analysis_urlsafe_key,
                commit_position=most_recent_commit_position,
                dimensions=None,  # Not used.
                revision=most_recent_build_info.chromium_revision,
                step_metadata=parameters.step_metadata,
                upper_bound_build_number=most_recent_build_number))

        # Determine approximate pass rate at the commit position/isolate sha.
        recent_flakiness = yield DetermineApproximatePassRatePipeline(
            self.CreateInputObjectInstance(
                DetermineApproximatePassRateInput,
                builder_name=analysis.builder_name,
                commit_position=most_recent_commit_position,
                flakiness_thus_far=None,
                get_isolate_sha_output=get_sha_output,
                previous_swarming_task_output=None,
                master_name=analysis.master_name,
                reference_build_number=analysis.build_number,
                revision=most_recent_build_info.chromium_revision,
                step_name=analysis.step_name,
                test_name=analysis.test_name))

        yield SaveFlakinessVerificationPipeline(
            self.CreateInputObjectInstance(
                SaveFlakinessVerificationInput,
                analysis_urlsafe_key=analysis_urlsafe_key,
                flakiness=recent_flakiness))

        # Check for flakiness and file a bug accordingly.
        yield CreateBugIfStillFlakyPipeline(
            self.CreateInputObjectInstance(
                CreateBugInput, analysis_urlsafe_key=analysis_urlsafe_key))


class CreateBugPipeline(GeneratorPipeline):
  input_type = CreateBugInput

  def RunImpl(self, parameters):
    """Files a bug pointing out a flaky test."""
    analysis = ndb.Key(urlsafe=parameters.analysis_urlsafe_key).get()
    assert analysis, 'Analysis unexpectedly missing!'

    # Log our attempt in analysis so we don't retry perpetually.
    analysis.Update(has_attempted_filing=True)

    issue_generator = flake_report_util.FlakeAnalysisIssueGenerator(analysis)
    issue_id = issue_tracking_service.CreateOrUpdateIssue(issue_generator)
    if not issue_id:
      analysis.LogError('Couldn\'t create bug!')
      return

    analysis.Update(bug_id=issue_id, has_filed_bug=True)

    flake_analysis_request = FlakeAnalysisRequest.GetVersion(
        key=analysis.test_name)
    assert flake_analysis_request, (
        'Flake analysis request unexpectedly missing!')
    flake_analysis_request.Update(
        bug_reported_by=triggering_sources.FINDIT_PIPELINE, bug_id=issue_id)


class CreateBugIfStillFlakyPipeline(GeneratorPipeline):
  input_type = CreateBugInput

  def RunImpl(self, parameters):
    """Files a bug if the recent check for flakiness is still flaky."""
    analysis = ndb.Key(urlsafe=parameters.analysis_urlsafe_key).get()
    assert analysis, 'Analysis unexpectedly missing!'

    assert analysis.flakiness_verification_data_points, (
        'Data points for recent flakiness unexpectedly missing!')

    recent_data_point = sorted(
        analysis.flakiness_verification_data_points,
        key=lambda x: x.commit_position,
        reverse=True)[0]

    if pass_rate_util.IsFullyStable(recent_data_point.pass_rate):
      analysis.LogInfo('Bug not filed because test is stable in latest commit.')
      return

    yield CreateBugPipeline(parameters)
