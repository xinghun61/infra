# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
import mock

from gae_libs.pipelines import pipeline_handlers
from gae_libs.pipelines import CreateInputObjectInstance

from model.flake.flake_culprit import FlakeCulprit
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure import create_bug_for_flake_pipeline
from pipelines.flake_failure.create_bug_for_flake_pipeline import (
    CreateBugForFlakePipeline)
from pipelines.flake_failure.create_bug_for_flake_pipeline import (
    CreateBugForFlakePipelineInputObject)
from services.flake_failure import issue_tracking_service
from waterfall import swarming_util
from waterfall import build_util
from waterfall.flake.analyze_flake_for_build_number_pipeline import (
    AnalyzeFlakeForBuildNumberPipeline)
from waterfall.test.wf_testcase import WaterfallTestCase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class CreateBugForFlakePipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(swarming_util, 'IsTestEnabled', return_value=True)
  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=200)
  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags')
  @mock.patch.object(
      issue_tracking_service, 'ShouldFileBugForAnalysis', return_value=True)
  def testCreateBugForFlakePipeline(self, should_file_fn, list_swarming_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    list_swarming_fn.return_value = [{'task_id': 'id'}]

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

    create_bug_input = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)

    self.MockPipeline(
        AnalyzeFlakeForBuildNumberPipeline,
        True,
        expected_args=[analysis.key.urlsafe(), 200, 30, 3600, True])

    expected_input_object = CreateInputObjectInstance(
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        most_recent_build_number=200)
    self.MockGeneratorPipeline(
        create_bug_for_flake_pipeline._CreateBugIfStillFlaky,
        expected_input_object, True)

    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(should_file_fn.called)

  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=200)
  @mock.patch.object(swarming_util, 'IsTestEnabled', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'ShouldFileBugForAnalysis', return_value=True)
  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags')
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

    create_bug_input = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()

    self.execute_queued_tasks()
    self.assertTrue(list_swarming_fn.called)

  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=200)
  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags')
  @mock.patch.object(swarming_util, 'IsTestEnabled', return_value=False)
  @mock.patch.object(
      issue_tracking_service, 'ShouldFileBugForAnalysis', return_value=True)
  def testCreateBugForFlakePipelineIfTestDisabled(
      self, should_file_fn, test_enabled_fn, list_swarming_fn, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    list_swarming_fn.return_value = [{'task_id': 'task_id'}]

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

    create_bug_input = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()

    self.execute_queued_tasks()
    self.assertTrue(should_file_fn.called)
    self.assertTrue(test_enabled_fn.called)

  @mock.patch.object(swarming_util, 'IsTestEnabled', return_value=True)
  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=200)
  @mock.patch.object(
      issue_tracking_service, 'ShouldFileBugForAnalysis', return_value=True)
  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags')
  @mock.patch.object(
      issue_tracking_service, 'CreateBugForTest',
      return_value=123)  # 123 is the bug_number.
  def testCreateBugForFlakePipelineEndToEnd(
      self, create_bug_fn, list_swarming_fn, should_file_fn, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    list_swarming_fn.return_value = [{'task_id': 'id'}]

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [
        DataPoint.Create(build_number=200, pass_rate=.5),
        DataPoint.Create(build_number=100, pass_rate=.5, task_ids=['task_id'])
    ]
    analysis.suspected_flake_build_number = 100
    analysis.confidence_in_culprit = 1.0
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)

    self.MockPipeline(
        AnalyzeFlakeForBuildNumberPipeline,
        True,
        expected_args=[analysis.key.urlsafe(), 200, 30, 3600, True])

    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(should_file_fn.called)
    self.assertTrue(create_bug_fn.called)
    self.assertTrue(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'ShouldFileBugForAnalysis', return_value=False)
  def testCreateBugForFlakePipelineWhenShouldFileReturnsFalse(
      self, should_file_fn):
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

    create_bug_input = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(should_file_fn.called)
    self.assertFalse(analysis.has_attempted_filing)

  @mock.patch.object(swarming_util, 'IsTestEnabled', return_value=True)
  @mock.patch.object(build_util, 'GetLatestBuildNumber', return_value=None)
  @mock.patch.object(
      issue_tracking_service, 'ShouldFileBugForAnalysis', return_value=True)
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

    create_bug_input = CreateInputObjectInstance(
        CreateBugForFlakePipelineInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        test_location={'file': '/foo/bar',
                       'line': '1'})
    pipeline_job = CreateBugForFlakePipeline(create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(should_file_fn.called)
    self.assertTrue(latest_build_fn.called)
    self.assertFalse(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'CreateBugForTest',
      return_value=123)  # 123 is the bug_number.
  def testCreateBugIfStillFlaky(self, create_bug_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [DataPoint.Create(build_number=200, pass_rate=.5)]
    analysis.confidence_in_culprit = 1.0
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateInputObjectInstance(
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        most_recent_build_number=200)
    pipeline_job = create_bug_for_flake_pipeline._CreateBugIfStillFlaky(
        create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(create_bug_fn.called)
    self.assertTrue(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'CreateBugForTest',
      return_value=123)  # 123 is the bug_number.
  def testCreateBugIfStillFlakyStablePointFound(self, create_bug_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateInputObjectInstance(
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        most_recent_build_number=200)
    pipeline_job = create_bug_for_flake_pipeline._CreateBugIfStillFlaky(
        create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertFalse(create_bug_fn.called)
    self.assertFalse(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'CreateBugForTest',
      return_value=123)  # 123 is the bug_number.
  def testCreateBugIfStillFlakyNoDataPoint(self, create_bug_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateInputObjectInstance(
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        most_recent_build_number=200)
    pipeline_job = create_bug_for_flake_pipeline._CreateBugIfStillFlaky(
        create_bug_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertFalse(create_bug_fn.called)
    self.assertFalse(analysis.has_attempted_filing)

  @mock.patch.object(
      issue_tracking_service, 'CreateBugForTest', return_value=None)
  def testCreateBugIfStillFlakyCreateBugReturnsNone(self, create_bug_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    # Create a flake analysis with no bug.
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.algorithm_parameters = copy.deepcopy(
        DEFAULT_CONFIG_DATA['check_flake_settings'])
    analysis.data_points = [DataPoint.Create(build_number=200, pass_rate=.5)]
    analysis.confidence_in_culprit = 1.0
    analysis.Save()

    # Create a flake analysis request with no bug.
    request = FlakeAnalysisRequest.Create(test_name, False, None)
    request.Save()

    create_bug_input = CreateInputObjectInstance(
        create_bug_for_flake_pipeline._CreateBugIfStillFlakyInputObject,
        analysis_urlsafe_key=unicode(analysis.key.urlsafe()),
        most_recent_build_number=200)
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
        DataPoint.Create(
            build_number=200,
            pass_rate=.5,
            git_hash='hash',
            previous_build_git_hash='prev_hash')
    ]
    analysis.suspected_flake_build_number = 200
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.confidence_in_culprit = .5
    analysis.put()

    subject, body = create_bug_for_flake_pipeline._GenerateSubjectAndBodyForBug(
        analysis)
    self.assertEqual('t is Flaky', subject)
    self.assertTrue('(50.0% confidence)' in body)
    self.assertTrue(
        'Regression range: https://crrev.com/prev_hash..hash?pretty=fuller' in
        body)
    self.assertTrue(
        'If this result was incorrect, apply the label Findit-Incorrect-Result'
        in body)
