# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from pipelines.compile_failure import analyze_compile_failure_pipeline
from pipelines.compile_failure import (identify_compile_failure_suspect_pipeline
                                       as suspect_pipeline)
from pipelines.compile_failure.analyze_compile_failure_pipeline import (
    AnalyzeCompileFailurePipeline)
from waterfall.test import wf_testcase


class AnalyzeCompileFailurePipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _SetupAnalysis(self,
             master_name,
             builder_name,
             build_number,
             status=analysis_status.PENDING,
             signals=None,
             failure_info=None):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = status
    analysis.failure_info = failure_info
    analysis.signals = signals
    analysis.put()

  def testBuildFailurePipelineFlow(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    current_failure_info = {}

    self._SetupAnalysis(master_name, builder_name, build_number)

    self.MockPipeline(
        analyze_compile_failure_pipeline.DetectFirstCompileFailurePipeline,
        'failure_info',
        expected_args=[current_failure_info],
        expected_kwargs={})
    self.MockPipeline(
        analyze_compile_failure_pipeline.ExtractSignalForCompilePipeline,
        'signals',
        expected_args=['failure_info'],
        expected_kwargs={})
    self.MockPipeline(
        suspect_pipeline.IdentifyCompileFailureSuspectPipeline,
        'heuristic_result',
        expected_args=['failure_info', 'signals', False],
        expected_kwargs={})
    self.MockPipeline(
        analyze_compile_failure_pipeline.StartCompileTryJobPipeline,
        'try_job_result',
        expected_args=[
            master_name, builder_name, build_number, 'failure_info', 'signals',
            'heuristic_result', False, False
        ],
        expected_kwargs={})

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, current_failure_info, False,
        False)
    root_pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  def testBuildFailurePipelineStartWithNoneResultStatus(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._SetupAnalysis(master_name, builder_name, build_number)

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, None, False, False)
    root_pipeline._ResetAnalysis(master_name, builder_name, build_number)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(analysis_status.RUNNING, analysis.status)
    self.assertIsNone(analysis.result_status)

  def testAnalyzeCompileFailurePipelineAbortedIfWithError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._SetupAnalysis(
        master_name, builder_name, build_number, status=analysis_status.RUNNING)

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, None, False, False)
    root_pipeline._HandleUnexpectedAborting(True)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(analysis_status.ERROR, analysis.status)
    self.assertIsNone(analysis.result_status)
    self.assertTrue(analysis.aborted)

  def testAnalyzeCompileFailurePipelineNotAbortedIfWithoutError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._SetupAnalysis(
        master_name,
        builder_name,
        build_number,
        status=analysis_status.COMPLETED)

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, None, False, False)
    root_pipeline._HandleUnexpectedAborting(True)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertNotEqual(analysis_status.ERROR, analysis.status)

  @mock.patch.object(analyze_compile_failure_pipeline,
                     'StartCompileTryJobPipeline')
  def testAnalyzeCompileFailurePipelineStartTryJob(self, mocked_pipeline):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    failure_info = {
        'compile': {
            'last_pass': 122,
            'current_failure': 123,
            'first_failure': 123
        }
    }

    self._SetupAnalysis(
        master_name,
        builder_name,
        build_number,
        status=analysis_status.RUNNING,
        signals={},
        failure_info=failure_info)

    root_pipeline = AnalyzeCompileFailurePipeline(
        master_name, builder_name, build_number, None, False, False)
    root_pipeline._HandleUnexpectedAborting(True)

    mocked_pipeline.assert_called_once_with(
        master_name, builder_name, build_number, failure_info, {},
        None, False, False)
    mocked_pipeline.assert_has_calls(
        [mock.call().start(queue_name=constants.WATERFALL_ANALYSIS_QUEUE)])
