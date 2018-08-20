# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
import mock

from dto.step_metadata import StepMetadata
from dto.test_location import TestLocation
from gae_libs.pipelines import pipeline_handlers
from infra_api_clients.swarming.swarming_task_data import SwarmingTaskData
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure import create_bug_for_flake_pipeline
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
from services import issue_tracking_service
from services import swarmed_test_util
from services import swarming
from services.flake_failure import flake_report_util
from waterfall import build_util
from waterfall.build_info import BuildInfo
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA
from waterfall.test.wf_testcase import WaterfallTestCase


class CreateBugForFlakePipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(swarmed_test_util, 'IsTestEnabled', return_value=True)
  @mock.patch.object(build_util, 'GetLatestBuildNumber')
  @mock.patch.object(swarming, 'ListSwarmingTasksDataByTags')
  @mock.patch.object(
      flake_report_util, 'ShouldFileBugForAnalysis', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testCreateBugForFlakePipeline(self, mocked_build_info, should_file_fn,
                                    list_swarming_fn, latest_build_number, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    recent_build_number = 200
    recent_commit_position = 2000
    step_name = 's'
    test_name = 't'
    recent_revision = 'r2000'

    list_swarming_fn.return_value = [SwarmingTaskData({'task_id': 'id'})]
    latest_build_number.return_value = recent_build_number

    recent_build_info = BuildInfo(master_name, builder_name,
                                  recent_build_number)
    recent_build_info.commit_position = recent_commit_position
    recent_build_info.chromium_revision = recent_revision
    mocked_build_info.return_value = 200, recent_build_info

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(
            commit_position=100, task_ids=['task_id'], pass_rate=0.9),
        DataPoint.Create(commit_position=99, pass_rate=1.0)
    ]
    analysis.Save()

    step_metadata = StepMetadata(
        canonical_step_name=None,
        dimensions=None,
        full_step_name=None,
        isolate_target_name='target',
        patched=True,
        swarm_task_ids=None,
        waterfall_buildername=None,
        waterfall_mastername=None)

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateBugForFlakePipelineInputObject(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        step_metadata=step_metadata,
        test_location=TestLocation(file='foo/bar', line=1))

    pipeline_job = CreateBugForFlakePipeline(create_bug_input)

    expected_isolate_sha_input = GetIsolateShaForCommitPositionParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=recent_commit_position,
        dimensions=None,
        revision=recent_revision,
        step_metadata=step_metadata,
        upper_bound_build_number=recent_build_number)

    get_sha_output = GetIsolateShaOutput(
        isolate_sha='sha1', build_url='url', try_job_url=None)

    expected_pass_rate_input = DetermineApproximatePassRateInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        commit_position=recent_commit_position,
        get_isolate_sha_output=get_sha_output,
        previous_swarming_task_output=None,
        revision=recent_revision)

    self.MockGeneratorPipeline(GetIsolateShaForCommitPositionPipeline,
                               expected_isolate_sha_input, get_sha_output)

    self.MockGeneratorPipeline(DetermineApproximatePassRatePipeline,
                               expected_pass_rate_input, None)

    self.MockGeneratorPipeline(DetermineApproximatePassRatePipeline,
                               expected_pass_rate_input, None)

    expected_input_object = (
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject(
            analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
            commit_position=recent_commit_position))

    self.MockGeneratorPipeline(
        create_bug_for_flake_pipeline._CreateBugIfStillFlaky,
        expected_input_object, True)

    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(should_file_fn.called)

  @mock.patch.object(swarmed_test_util, 'IsTestEnabled', return_value=True)
  @mock.patch.object(build_util, 'GetLatestBuildNumber')
  @mock.patch.object(swarming, 'ListSwarmingTasksDataByTags')
  @mock.patch.object(
      flake_report_util, 'ShouldFileBugForAnalysis', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo')
  def testCreateBugForFlakePipelineNewBuildIsTriggeringBuild(
      self, mocked_build_info, should_file_fn, list_swarming_fn,
      latest_build_number, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    most_recent_build_number = build_number
    most_recent_commit_position = 2000
    step_name = 's'
    test_name = 't'
    most_recent_revision = 'r2000'

    list_swarming_fn.return_value = [SwarmingTaskData({'task_id': 'id'})]
    latest_build_number.return_value = most_recent_build_number

    recent_build_info = BuildInfo(master_name, builder_name,
                                  most_recent_build_number)
    recent_build_info.commit_position = most_recent_commit_position
    recent_build_info.chromium_revision = most_recent_revision
    mocked_build_info.return_value = most_recent_build_number, recent_build_info

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(
            commit_position=most_recent_commit_position,
            task_ids=['task_id'],
            pass_rate=0.9),
        DataPoint.Create(commit_position=99, pass_rate=1.0)
    ]
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateBugForFlakePipelineInputObject(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        step_metadata=None,
        test_location=TestLocation(file='foo/bar', line=1))

    pipeline_job = CreateBugForFlakePipeline(create_bug_input)

    expected_input_object = (
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject(
            analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
            commit_position=most_recent_commit_position))

    self.MockGeneratorPipeline(
        create_bug_for_flake_pipeline._CreateBugIfStillFlaky,
        expected_input_object, True)

    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(should_file_fn.called)

  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=200)
  @mock.patch.object(swarmed_test_util, 'IsTestEnabled', return_value=False)
  @mock.patch.object(
      flake_report_util, 'ShouldFileBugForAnalysis', return_value=True)
  @mock.patch.object(swarming, 'ListSwarmingTasksDataByTags')
  def testCreateBugForFlakePipelineWhenNoTasksReturned(self, list_swarming_fn,
                                                       *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    list_swarming_fn.return_value = []

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(build_number=100, task_ids=['task_id'])
    ]
    analysis.suspected_flake_build_number = 100
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateBugForFlakePipelineInputObject(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        step_metadata=None,
        test_location=TestLocation(file='/foo/bar', line=2))
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()

    self.execute_queued_tasks()
    self.assertTrue(list_swarming_fn.called)

  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=200)
  @mock.patch.object(swarming, 'ListSwarmingTasksDataByTags')
  @mock.patch.object(swarmed_test_util, 'IsTestEnabled', return_value=False)
  @mock.patch.object(
      flake_report_util, 'ShouldFileBugForAnalysis', return_value=True)
  def testCreateBugForFlakePipelineIfTestDisabled(
      self, should_file_fn, test_enabled_fn, list_swarming_fn, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    list_swarming_fn.return_value = [SwarmingTaskData({'task_id': 'task_id'})]

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(build_number=100, task_ids=['task_id'])
    ]
    analysis.suspected_flake_build_number = 100
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateBugForFlakePipelineInputObject(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        step_metadata=None,
        test_location=TestLocation(file='/foo/bar', line=1))
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()

    self.execute_queued_tasks()
    self.assertTrue(should_file_fn.called)
    self.assertTrue(test_enabled_fn.called)

  @mock.patch.object(
      issue_tracking_service, 'GetExistingOpenBugIdForTest', return_value=None)
  @mock.patch.object(
      issue_tracking_service,
      'GetExistingBugIdForCustomizedField',
      return_value=None)
  @mock.patch.object(
      flake_report_util, 'ShouldFileBugForAnalysis', return_value=False)
  def testShouldFileBugReturnsFalse(
      self, should_file_fn, mock_bug_for_custom_field, mock_bug_for_test):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateBugForFlakePipelineInputObject(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        step_metadata=None,
        test_location=TestLocation(file='/foo/bar', line=1))
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(should_file_fn.called)
    self.assertFalse(analysis.has_attempted_filing)

    mock_bug_for_custom_field.assert_called('t', 'chromium')
    mock_bug_for_test.assert_called('t', 'chromium')

  @mock.patch.object(
      flake_report_util, 'ShouldFileBugForAnalysis', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'GetExistingOpenBugIdForTest', return_value=None)
  @mock.patch.object(
      issue_tracking_service,
      'GetExistingBugIdForCustomizedField',
      return_value=1234)
  def testShouldFileReturnsFalseWithBugForCustomizedField(
      self, mock_bug_for_custom_field, mock_bug_for_test, should_file_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateBugForFlakePipelineInputObject(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        step_metadata=None,
        test_location=TestLocation(file='/foo/bar', line=1))
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(should_file_fn.called)
    self.assertFalse(analysis.has_attempted_filing)
    self.assertEqual(1234, analysis.bug_id)

    mock_bug_for_custom_field.assert_called('t', 'chromium')
    mock_bug_for_test.assert_not_called()

  @mock.patch.object(
      flake_report_util, 'ShouldFileBugForAnalysis', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'GetExistingOpenBugIdForTest', return_value=1234)
  @mock.patch.object(
      issue_tracking_service,
      'GetExistingBugIdForCustomizedField',
      return_value=None)
  def testShouldFileReturnsFalseWithOpenBugForTest(
      self, mock_bug_for_custom_field, mock_bug_for_test, should_file_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateBugForFlakePipelineInputObject(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        step_metadata=None,
        test_location=TestLocation(file='/foo/bar', line=1))
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(should_file_fn.called)
    self.assertFalse(analysis.has_attempted_filing)
    self.assertEqual(1234, analysis.bug_id)

    mock_bug_for_custom_field.assert_called('t', 'chromium')
    mock_bug_for_test.assert_called('t', 'chromium')

  @mock.patch.object(swarmed_test_util, 'IsTestEnabled', return_value=True)
  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=None)
  @mock.patch.object(
      flake_report_util, 'ShouldFileBugForAnalysis', return_value=True)
  def testCreateBugForFlakePipelineWhenFailToGetLatestBuild(
      self, should_file_fn, latest_build_fn, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(build_number=100, pass_rate=.5, task_ids=['task_id'])
    ]
    analysis.suspected_flake_build_number = 100
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateBugForFlakePipelineInputObject(
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        step_metadata=None,
        test_location=TestLocation(file='/foo/bar', line=1))
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(should_file_fn.called)
    self.assertTrue(latest_build_fn.called)
    self.assertFalse(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'CreateBugForFlakeAnalyzer',
      return_value=123)  # 123 is the bug_number.
  def testCreateBugIfStillFlaky(self, create_bug_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    recent_commit_position = 200

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [
        DataPoint.Create(commit_position=recent_commit_position, pass_rate=.5)
    ]
    analysis.confidence_in_culprit = 1.0
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = (
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject(
            analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
            commit_position=recent_commit_position))
    pipeline_job = create_bug_for_flake_pipeline._CreateBugIfStillFlaky(
        create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(create_bug_fn.called)
    self.assertTrue(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'CreateBugForFlakeAnalyzer',
      return_value=123)  # 123 is the bug_number.
  def testCreateBugIfStillFlakyStablePointFound(self, create_bug_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    recent_commit_position = 1000

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = (
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject(
            analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
            commit_position=recent_commit_position))
    pipeline_job = create_bug_for_flake_pipeline._CreateBugIfStillFlaky(
        create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertFalse(create_bug_fn.called)
    self.assertFalse(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'CreateBugForFlakeAnalyzer',
      return_value=123)  # 123 is the bug_number.
  def testCreateBugIfStillFlakyNoDataPoint(self, create_bug_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    recent_commit_position = 1000

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = (
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject(
            analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
            commit_position=recent_commit_position))
    pipeline_job = create_bug_for_flake_pipeline._CreateBugIfStillFlaky(
        create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertFalse(create_bug_fn.called)
    self.assertFalse(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'CreateBugForFlakeAnalyzer', return_value=None)
  def testCreateBugIfStillFlakyCreateBugReturnsNone(self, create_bug_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    recent_commit_position = 200

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [
        DataPoint.Create(commit_position=recent_commit_position, pass_rate=.5)
    ]
    analysis.confidence_in_culprit = 1.0
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = (
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject(
            analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
            commit_position=recent_commit_position))
    pipeline_job = create_bug_for_flake_pipeline._CreateBugIfStillFlaky(
        create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(create_bug_fn.called)
    self.assertTrue(analysis.has_attempted_filing)

  def testGenerateSubjectAndBodyForBug(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    culprit = FlakeCulprit.Create('git', 'rev', 1)
    culprit.put()
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(commit_position=200, pass_rate=.5, git_hash='hash')
    ]
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.confidence_in_culprit = .5
    analysis.put()

    subject, body = create_bug_for_flake_pipeline._GenerateSubjectAndBodyForBug(
        analysis)
    self.assertEqual('t is Flaky', subject)
    self.assertTrue('(50.0% confidence)' in body)
    self.assertTrue('Test-Findit-Wrong' in body)
