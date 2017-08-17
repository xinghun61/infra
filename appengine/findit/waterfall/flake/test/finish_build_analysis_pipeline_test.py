# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from libs import time_util
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake import confidence
from waterfall.flake import flake_constants
from waterfall.flake import finish_build_analysis_pipeline
from waterfall.flake.finish_build_analysis_pipeline import (
    FinishBuildAnalysisPipeline)
from waterfall.flake.initialize_flake_try_job_pipeline import (
    InitializeFlakeTryJobPipeline)
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


class FinishBuildAnalysisPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testFinishBuildAnalysisPipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'

    lower_bound = 1
    upper_bound = 10
    user_range = True
    iterations = 100

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.put()

    task = FlakeSwarmingTask.Create(master_name, builder_name, build_number,
                                    step_name, test_name)
    task.status = analysis_status.COMPLETED
    task.put()

    self.MockPipeline(
        UpdateFlakeBugPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    self.MockPipeline(
        InitializeFlakeTryJobPipeline,
        '',
        expected_args=[analysis.key.urlsafe(), iterations, user_range, False],
        expected_kwargs={})

    pipeline = FinishBuildAnalysisPipeline(analysis.key.urlsafe(), lower_bound,
                                           upper_bound, iterations, False)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(confidence, 'SteppinessForBuild', return_value=0.6)
  def testGetBuildConfidenceScore(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 124, 's', 't')
    analysis.data_points = [DataPoint.Create(pass_rate=0.7, build_number=123)]
    self.assertIsNone(
        finish_build_analysis_pipeline._GetBuildConfidenceScore(
            analysis, None, []))
    self.assertEqual(0.6,
                     finish_build_analysis_pipeline._GetBuildConfidenceScore(
                         analysis, 123, analysis.data_points))

  def testGetBuildConfidenceScoreIntroducedNewFlakyTest(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 124, 's', 't')
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.7, build_number=123),
        DataPoint.Create(
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND,
            build_number=122)
    ]
    self.assertEqual(1.0,
                     finish_build_analysis_pipeline._GetBuildConfidenceScore(
                         analysis, 123, analysis.data_points))

  def testUserSpecifiedRange(self):
    self.assertTrue(
        finish_build_analysis_pipeline._UserSpecifiedRange(123, 125))
    self.assertFalse(
        finish_build_analysis_pipeline._UserSpecifiedRange(None, 123))
    self.assertFalse(
        finish_build_analysis_pipeline._UserSpecifiedRange(123, None))
    self.assertFalse(
        finish_build_analysis_pipeline._UserSpecifiedRange(None, None))

  def testUpdateAnalysisResults(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.last_attempted_swarming_task_id = '12345'
    finish_build_analysis_pipeline._UpdateAnalysisResults(
        analysis, 100, analysis_status.COMPLETED, None)
    self.assertEqual(analysis.suspected_flake_build_number, 100)
    self.assertIsNone(analysis.last_attempted_swarming_task_id)

  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(2017, 6, 27))
  def testUpdateAnalysisResultsWithError(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.last_attempted_swarming_task_id = '12345'
    finish_build_analysis_pipeline._UpdateAnalysisResults(
        analysis, None, analysis_status.ERROR, {'error': 'error'})
    self.assertEqual(analysis_status.ERROR, analysis.status)
    self.assertEqual(datetime(2017, 6, 27), analysis.end_time)