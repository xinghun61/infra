# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from dto.int_range import IntRange
from dto.step_metadata import StepMetadata
from dto.test_location import TestLocation
from gae_libs.pipeline_wrapper import pipeline_handlers
from infra_api_clients import crrev
from libs import analysis_status
from libs.list_of_basestring import ListOfBasestring
from model import result_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.delay_pipeline import DelayPipeline
from pipelines.flake_failure.analyze_flake_pipeline import AnalyzeFlakeInput
from pipelines.flake_failure.analyze_flake_pipeline import (
    AnalyzeFlakePipeline)
from pipelines.flake_failure.analyze_flake_pipeline import (
    RecursiveAnalyzeFlakePipeline)
from pipelines.flake_failure.create_and_submit_revert_pipeline import (
    CreateAndSubmitRevertInput)
from pipelines.flake_failure.create_and_submit_revert_pipeline import (
    CreateAndSubmitRevertPipeline)
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
from pipelines.flake_failure.get_isolate_sha_pipeline import (
    GetIsolateShaOutput)
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
from pipelines.report_event_pipeline import ReportAnalysisEventPipeline
from pipelines.report_event_pipeline import ReportEventInput
from services import swarmed_test_util
from services.flake_failure import confidence_score_util
from services.flake_failure import flake_analysis_util
from waterfall.test.wf_testcase import WaterfallTestCase


class AnalyzeFlakePipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testAnalyzeFlakePipelineAnalysisFinishedNoFindings(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    analyze_flake_input = AnalyzeFlakeInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        analyze_commit_position_parameters=NextCommitPositionOutput(
            next_commit_position=None, culprit_commit_position=None),
        commit_position_range=IntRange(lower=None, upper=None),
        dimensions=ListOfBasestring.FromSerializable([]),
        manually_triggered=False,
        retries=0,
        step_metadata=None)

    expected_report_event_input = ReportEventInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    self.MockGeneratorPipeline(ReportAnalysisEventPipeline,
                               expected_report_event_input, None)

    pipeline_job = AnalyzeFlakePipeline(analyze_flake_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertIsNone(analysis.culprit_urlsafe_key)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
    self.assertEqual(result_status.NOT_FOUND_UNTRIAGED, analysis.result_status)

  @mock.patch.object(crrev, 'RedirectByCommitPosition')
  @mock.patch.object(flake_analysis_util, 'UpdateCulprit')
  @mock.patch.object(confidence_score_util, 'CalculateCulpritConfidenceScore')
  @mock.patch.object(swarmed_test_util, 'GetTestLocation')
  def testAnalyzeFlakePipelineAnalysisFinishedWithCulprit(
      self, mocked_test_location, mocked_confidence, mocked_culprit,
      mocked_revision):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build_id = 'm/b/123'
    step_name = 's'
    test_name = 't'
    culprit_commit_position = 999

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(commit_position=culprit_commit_position)
    ]
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number
    analysis.original_step_name = step_name
    analysis.original_test_name = test_name
    analysis.Save()

    culprit_revision = 'r999'
    confidence_score = 0.85
    culprit = FlakeCulprit.Create('chromium', culprit_revision,
                                  culprit_commit_position)
    culprit.put()

    test_location = TestLocation(file='f', line=123)
    mocked_test_location.return_value = test_location
    mocked_revision.return_value = {'git_sha': culprit_revision}
    mocked_confidence.return_value = confidence_score
    mocked_culprit.return_value = culprit

    analyze_flake_input = AnalyzeFlakeInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        analyze_commit_position_parameters=NextCommitPositionOutput(
            next_commit_position=None,
            culprit_commit_position=culprit_commit_position),
        commit_position_range=IntRange(lower=None, upper=None),
        dimensions=ListOfBasestring.FromSerializable([]),
        manually_triggered=False,
        retries=0,
        step_metadata=None)

    expected_create_bug_input = CreateBugForFlakePipelineInputObject(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        step_metadata=None,
        test_location=test_location)
    expected_create_and_submit_revert_input = CreateAndSubmitRevertInput(
        analysis_urlsafe_key=analysis.key.urlsafe(), build_id=build_id)
    expected_update_bug_input = UpdateMonorailBugInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    expected_notify_culprit_input = NotifyCulpritInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    expected_report_event_input = ReportEventInput(
        analysis_urlsafe_key=analysis.key.urlsafe())

    self.MockGeneratorPipeline(CreateBugForFlakePipeline,
                               expected_create_bug_input, None)
    self.MockGeneratorPipeline(CreateAndSubmitRevertPipeline,
                               expected_create_and_submit_revert_input, True)
    self.MockGeneratorPipeline(UpdateMonorailBugPipeline,
                               expected_update_bug_input, True)
    self.MockGeneratorPipeline(NotifyCulpritPipeline,
                               expected_notify_culprit_input, True)
    self.MockGeneratorPipeline(ReportAnalysisEventPipeline,
                               expected_report_event_input, None)

    pipeline_job = AnalyzeFlakePipeline(analyze_flake_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertIsNotNone(analysis.culprit_urlsafe_key)
    self.assertTrue(mocked_culprit.called)
    self.assertEqual(confidence_score, analysis.confidence_in_culprit)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
    self.assertEqual(result_status.FOUND_UNTRIAGED, analysis.result_status)
    mocked_revision.assert_called_once_with(mock.ANY, 999)

  @mock.patch.object(
      flake_analysis_util, 'CanStartAnalysisImmediately', return_value=True)
  @mock.patch.object(crrev, 'RedirectByCommitPosition')
  def testAnalyzeFlakePipelineCanStartAnalysisImmediately(
      self, mocked_revision, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    start_commit_position = 1000
    start_revision = 'r1000'
    isolate_sha = 'sha1'
    next_commit_position = 999
    build_url = 'url'
    try_job_url = None

    get_sha_output = GetIsolateShaOutput(
        isolate_sha=isolate_sha, build_url=build_url, try_job_url=try_job_url)

    step_metadata = StepMetadata(
        canonical_step_name='s',
        dimensions=None,
        full_step_name='s',
        patched=False,
        swarm_task_ids=None,
        waterfall_buildername='b',
        waterfall_mastername='w',
        isolate_target_name='s')

    mocked_revision.return_value = {'git_sha': start_revision}

    analyze_flake_input = AnalyzeFlakeInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        analyze_commit_position_parameters=NextCommitPositionOutput(
            next_commit_position=start_commit_position,
            culprit_commit_position=None),
        commit_position_range=IntRange(lower=None, upper=None),
        dimensions=ListOfBasestring.FromSerializable(['os:testOS']),
        manually_triggered=False,
        retries=0,
        step_metadata=step_metadata)

    expected_isolate_sha_input = GetIsolateShaForCommitPositionParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=start_commit_position,
        dimensions=ListOfBasestring.FromSerializable(['os:testOS']),
        revision=start_revision,
        step_metadata=step_metadata,
        upper_bound_build_number=analysis.build_number)

    expected_pass_rate_input = DetermineApproximatePassRateInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=start_commit_position,
        get_isolate_sha_output=get_sha_output,
        previous_swarming_task_output=None,
        revision=start_revision)

    expected_next_commit_position_input = NextCommitPositionInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position_range=IntRange(lower=None, upper=None))

    expected_next_commit_position_output = NextCommitPositionOutput(
        next_commit_position=next_commit_position, culprit_commit_position=None)

    expected_recursive_analyze_flake_input = AnalyzeFlakeInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        analyze_commit_position_parameters=expected_next_commit_position_output,
        commit_position_range=IntRange(lower=None, upper=None),
        dimensions=ListOfBasestring.FromSerializable(['os:testOS']),
        manually_triggered=False,
        retries=0,
        step_metadata=step_metadata)

    self.MockGeneratorPipeline(GetIsolateShaForCommitPositionPipeline,
                               expected_isolate_sha_input, get_sha_output)

    self.MockGeneratorPipeline(DetermineApproximatePassRatePipeline,
                               expected_pass_rate_input, None)

    self.MockSynchronousPipeline(NextCommitPositionPipeline,
                                 expected_next_commit_position_input,
                                 expected_next_commit_position_output)

    self.MockGeneratorPipeline(RecursiveAnalyzeFlakePipeline,
                               expected_recursive_analyze_flake_input, None)

    pipeline_job = AnalyzeFlakePipeline(analyze_flake_input)
    pipeline_job.start()
    self.execute_queued_tasks()
    mocked_revision.assert_called_once_with(mock.ANY, 1000)

  @mock.patch.object(
      flake_analysis_util, 'CanStartAnalysisImmediately', return_value=False)
  @mock.patch.object(crrev, 'RedirectByCommitPosition')
  @mock.patch.object(flake_analysis_util, 'CalculateDelaySecondsBetweenRetries')
  def testAnalyzeFlakePipelineStartTaskAfterDelay(self, mocked_delay,
                                                  mocked_revision, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    # Random date in the past, for coverage.
    analysis.request_time = datetime.datetime(2015, 1, 1, 1, 1, 1)
    analysis.Save()

    start_commit_position = 1000
    start_revision = 'r1000'
    delay = 60

    step_metadata = StepMetadata(
        canonical_step_name='s',
        dimensions=None,
        full_step_name='s',
        patched=False,
        swarm_task_ids=None,
        waterfall_buildername='b',
        waterfall_mastername='w',
        isolate_target_name='s')

    mocked_revision.return_value = {'git_sha': start_revision}
    mocked_delay.return_value = delay

    analyze_flake_input = AnalyzeFlakeInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        analyze_commit_position_parameters=NextCommitPositionOutput(
            next_commit_position=start_commit_position,
            culprit_commit_position=None),
        commit_position_range=IntRange(lower=None, upper=None),
        dimensions=ListOfBasestring.FromSerializable(['os:testOS']),
        manually_triggered=False,
        retries=0,
        step_metadata=step_metadata)

    expected_retried_analyze_flake_input = AnalyzeFlakeInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        analyze_commit_position_parameters=NextCommitPositionOutput(
            next_commit_position=start_commit_position,
            culprit_commit_position=None),
        commit_position_range=IntRange(lower=None, upper=None),
        dimensions=ListOfBasestring.FromSerializable(['os:testOS']),
        manually_triggered=False,
        retries=1,
        step_metadata=step_metadata)

    self.MockAsynchronousPipeline(DelayPipeline, delay, delay)

    self.MockGeneratorPipeline(RecursiveAnalyzeFlakePipeline,
                               expected_retried_analyze_flake_input, None)

    pipeline_job = AnalyzeFlakePipeline(analyze_flake_input)
    pipeline_job.start()
    self.execute_queued_tasks()
    mocked_revision.assert_called_once_with(mock.ANY, 1000)

  def testOnFinalizedNoError(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    analyze_flake_input = AnalyzeFlakeInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        analyze_commit_position_parameters=NextCommitPositionOutput(
            next_commit_position=1000, culprit_commit_position=None),
        commit_position_range=IntRange(lower=None, upper=None),
        dimensions=ListOfBasestring.FromSerializable(['os:testOS']),
        manually_triggered=False,
        retries=0,
        step_metadata=None)

    pipeline_job = AnalyzeFlakePipeline(analyze_flake_input)
    pipeline_job.OnFinalized(analyze_flake_input)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)

  def testFinishAnalyzeFlakePipelineWithError(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.error = analysis.GetError()
    analysis.Save()

    analyze_flake_input = AnalyzeFlakeInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        analyze_commit_position_parameters=NextCommitPositionOutput(
            next_commit_position=1000, culprit_commit_position=None),
        commit_position_range=IntRange(lower=None, upper=None),
        dimensions=ListOfBasestring.FromSerializable(['os:testOS']),
        manually_triggered=False,
        retries=0,
        step_metadata=None)

    pipeline_job = AnalyzeFlakePipeline(analyze_flake_input)
    pipeline_job.OnFinalized(analyze_flake_input)
    self.assertEqual(analysis_status.ERROR, analysis.status)

  def testRecursiveAnalyzeFlakePipeline(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    analyze_flake_input = AnalyzeFlakeInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        analyze_commit_position_parameters=NextCommitPositionOutput(
            next_commit_position=1000, culprit_commit_position=None),
        commit_position_range=IntRange(lower=None, upper=None),
        dimensions=ListOfBasestring.FromSerializable([]),
        manually_triggered=False,
        retries=0,
        step_metadata=None)

    self.MockGeneratorPipeline(AnalyzeFlakePipeline, analyze_flake_input, None)

    pipeline_job = RecursiveAnalyzeFlakePipeline(analyze_flake_input)
    pipeline_job.start()
    self.execute_queued_tasks()
