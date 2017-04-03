# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from common import constants
from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from model import analysis_status
from model.wf_analysis import WfAnalysis
from waterfall import analyze_build_failure_pipeline
from waterfall import buildbot
from waterfall import lock_util
from waterfall.analyze_build_failure_pipeline import AnalyzeBuildFailurePipeline
from waterfall.test import wf_testcase


class AnalyzeBuildFailurePipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _Setup(self, master_name, builder_name, build_number,
             status=analysis_status.PENDING):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = status
    analysis.put()

  def testBuildFailurePipelineFlow(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._Setup(master_name, builder_name, build_number)

    self.MockPipeline(analyze_build_failure_pipeline.DetectFirstFailurePipeline,
                      'failure_info',
                      expected_args=[master_name, builder_name, build_number],
                      expected_kwargs={})
    self.MockPipeline(analyze_build_failure_pipeline.PullChangelogPipeline,
                      'change_logs',
                      expected_args=['failure_info'],
                      expected_kwargs={})
    self.MockPipeline(analyze_build_failure_pipeline.ExtractDEPSInfoPipeline,
                      'deps_info',
                      expected_args=['failure_info', 'change_logs'],
                      expected_kwargs={})
    self.MockPipeline(analyze_build_failure_pipeline.ExtractSignalPipeline,
                      'signals',
                      expected_args=['failure_info'],
                      expected_kwargs={})
    self.MockPipeline(analyze_build_failure_pipeline.IdentifyCulpritPipeline,
                      'heuristic_result',
                      expected_args=[
                          'failure_info', 'change_logs', 'deps_info',
                          'signals', False],
                      expected_kwargs={})
    self.MockPipeline(
        analyze_build_failure_pipeline.TriggerSwarmingTasksPipeline,
        None,
        expected_args=[
            master_name, builder_name, build_number, 'failure_info'],
        expected_kwargs={})
    self.MockPipeline(
        analyze_build_failure_pipeline.StartTryJobOnDemandPipeline,
        'try_job_result',
        expected_args=[
            master_name, builder_name, build_number, 'failure_info', 'signals',
            'heuristic_result', False, False],
        expected_kwargs={})

    root_pipeline = AnalyzeBuildFailurePipeline(master_name,
                                                builder_name,
                                                build_number,
                                                False,
                                                False)
    root_pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  def testBuildFailurePipelineStartWithNoneResultStatus(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._Setup(master_name, builder_name, build_number)

    root_pipeline = AnalyzeBuildFailurePipeline(master_name,
                                                builder_name,
                                                build_number,
                                                False,
                                                False)
    root_pipeline._ResetAnalysis(master_name, builder_name, build_number)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(analysis_status.RUNNING, analysis.status)
    self.assertIsNone(analysis.result_status)

  def testAnalyzeBuildFailurePipelineAbortedIfWithError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._Setup(master_name, builder_name, build_number,
                status=analysis_status.RUNNING)

    root_pipeline = AnalyzeBuildFailurePipeline(master_name,
                                                builder_name,
                                                build_number,
                                                False,
                                                False)
    root_pipeline._LogUnexpectedAborting(True)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(analysis_status.ERROR, analysis.status)
    self.assertIsNone(analysis.result_status)
    self.assertTrue(analysis.aborted)

  def testAnalyzeBuildFailurePipelineNotAbortedIfWithoutError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._Setup(master_name, builder_name, build_number,
                status=analysis_status.COMPLETED)

    root_pipeline = AnalyzeBuildFailurePipeline(master_name,
                                                builder_name,
                                                build_number,
                                                False,
                                                False)
    root_pipeline._LogUnexpectedAborting(True)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertNotEqual(analysis_status.ERROR, analysis.status)
